from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Any

from backend.engine.factors import Bar, InsufficientPriceDataError, compute_cross_section_v3, suggested_weight
from backend.engine.factors.momentum_v3 import MIN_SAMPLES as MOMENTUM_MIN_SAMPLES
from backend.engine.instruments import conviction_from_composite
from backend.engine.timing import (
    BacktestBar,
    BacktestResultV3,
    InsufficientBacktestDataError,
    aggregate_backtests,
    run_reversal_rsi_backtest_v3,
)
from backend.pipeline.stages.common import (
    PRICE_SOFT_MAX_AGE_DAYS,
    StageOutcome,
    _asset_type_for,
    _iso_z,
    _security_id_for,
)

# Cross-sectional ranking (engine/factors/) AND per-symbol timing/backtest
# (engine/timing/) both live in this one stage for now — a known, stated
# simplification. This project's own non-negotiable rule is that these two
# layers stay "separately revisioned and evaluated"; splitting them into
# their own pipeline stage is future work, not pretended-away here.


def run_factor_engine_stage(
    connection: sqlite3.Connection,
    now: datetime,
    dataset_snapshot_id: str | None,
    desk_snapshot_id: str | None,
    engine_mode: str,
) -> StageOutcome:
    """Rank the staging universe by naive-v3 IC-weighted cross-sectional momentum AND run a
    naive per-symbol reversal-entry/RSI-exit backtest (naive-v3), attaching both to the
    still-open desk/dataset snapshots regime_filter and fetch_data created.
    """

    if not dataset_snapshot_id or not desk_snapshot_id:
        return StageOutcome(
            status="blocked",
            message="No dataset or open desk snapshot is available for factor scoring.",
            error_code="no_snapshot_to_score",
        )
    desk = connection.execute(
        "SELECT id FROM desk_snapshots WHERE id = ? AND immutable = 0",
        (desk_snapshot_id,),
    ).fetchone()
    if desk is None:
        return StageOutcome(
            status="blocked",
            message="The desk snapshot from regime_filter is missing or already sealed; cannot attach cross-sectional results.",
            error_code="desk_not_open",
            dataset_snapshot_id=dataset_snapshot_id,
            desk_snapshot_id=desk_snapshot_id,
        )

    staging_rows = connection.execute(
        "SELECT symbol, name, category FROM staging_symbols WHERE active = 1 AND category != 'macro_series' ORDER BY sort_order"
    ).fetchall()
    bars_by_symbol: dict[str, list[Bar]] = {}
    security_id_by_symbol: dict[str, str] = {}
    for row in staging_rows:
        security_id = _security_id_for(row["symbol"], row["category"])
        security_id_by_symbol[row["symbol"]] = security_id
        bar_rows = connection.execute(
            "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? AND close IS NOT NULL",
            (dataset_snapshot_id, security_id),
        ).fetchall()
        if bar_rows:
            bars_by_symbol[row["symbol"]] = [Bar(time=bar["time"], close=bar["close"]) for bar in bar_rows]

    # Single-name timing components are DB-driven and independently
    # retireable (schema.sql strategy_components) -- a real per-run read,
    # never a hand-typed set. 'watching' still counts as active for
    # computation (that verification_status/lifecycle state is about review
    # attention, not a kill switch); only 'retired'/'draft' are excluded.
    timing_component_rows = connection.execute(
        """
        SELECT component_key FROM strategy_components
        WHERE strategy_key = 'macd_rsi_single_name_timing' AND version = 'naive-v3'
          AND status IN ('active', 'watching')
        """
    ).fetchall()
    active_timing_components = frozenset(row["component_key"] for row in timing_component_rows)

    try:
        ranked, horizon_weights = compute_cross_section_v3(bars_by_symbol)
    except InsufficientPriceDataError as error:
        return StageOutcome(
            status="failed",
            message=f"Cross-sectional scoring failed: {error}",
            error_code="insufficient_price_data",
            dataset_snapshot_id=dataset_snapshot_id,
            desk_snapshot_id=desk_snapshot_id,
        )

    timestamp = _iso_z(now)
    category_by_symbol = {row["symbol"]: row["category"] for row in staging_rows}
    name_by_symbol = {row["symbol"]: row["name"] for row in staging_rows}
    universe_size = len(ranked)
    base_weight = 1.0 / sum(1 for row in staging_rows if row["category"] != "crypto_reference")

    horizon_labels = {"1m": "1M momentum", "3m": "3M momentum", "6m": "6M momentum", "12m_skip1m": "12-1 momentum"}
    factor_dimension_rows = [
        (
            desk_snapshot_id,
            f"momentum_{item.horizon}",
            horizon_labels.get(item.horizon, f"{item.horizon.upper()} momentum"),
            "return_fraction",
            (
                f"Trailing ~{item.lookback_days} trading day return. naive-v3: weight is real, computed this run "
                f"from a pooled Pearson IC test against {item.sample_size} paired (horizon-return, 21d-forward-return) "
                "samples across the staging universe, Benjamini-Hochberg corrected. "
                + (
                    f"r={item.correlation:+.3f}, adjusted p={item.adjusted_p_value:.3f} "
                    f"({'significant' if item.significant else 'not significant'} at alpha=0.05); "
                    "weight is proportional to |r| among significant horizons."
                    if item.status == "ok"
                    else f"Only {item.sample_size} samples (need {MOMENTUM_MIN_SAMPLES}); naive equal-weight fallback."
                )
                + (
                    " No horizon cleared correction this run, so every horizon falls back to equal weight."
                    if item.status == "ok" and not item.significant and not any(w.significant for w in horizon_weights)
                    else ""
                )
            ),
            item.weight,
            {"1m": 1, "3m": 2, "6m": 3, "12m_skip1m": 4}[item.horizon],
        )
        for item in horizon_weights
    ]
    connection.executemany(
        """
        INSERT INTO factor_dimensions (snapshot_id, factor_key, label, unit, description, weight, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        factor_dimension_rows,
    )

    symbol_rows: list[tuple[Any, ...]] = []
    cross_section_row_values: list[tuple[Any, ...]] = []
    factor_value_rows: list[tuple[Any, ...]] = []
    signal_rows: list[tuple[Any, ...]] = []
    recommendation_rows: list[tuple[Any, ...]] = []
    event_rows: list[tuple[Any, ...]] = []
    metric_rows: list[tuple[Any, ...]] = []
    backtest_results: list[BacktestResultV3] = []
    backtests_run = 0

    for item in ranked:
        symbol = item.symbol
        security_id = security_id_by_symbol[symbol]
        category = category_by_symbol[symbol]
        age_days = (now.date() - date.fromisoformat(item.last_date)).days
        freshness_status = "current" if age_days <= PRICE_SOFT_MAX_AGE_DAYS else "stale"
        symbol_rows.append(
            (
                desk_snapshot_id,
                security_id,
                symbol,
                name_by_symbol[symbol],
                _asset_type_for(category),
                None,
                None,
                "USD",
                "ranked",
                f"Rank {item.rank} of {universe_size} in the naive-v3 IC-weighted cross-sectional momentum ranking; composite score {item.composite_score:+.2f}.",
                item.last_close,
                f"{item.last_date}T00:00:00Z",
                item.composite_score,
                item.rank,
                freshness_status,
                f"{item.last_date}T00:00:00Z",
                f"Latest close is {age_days} day(s) old as of this run.",
            )
        )
        cross_section_row_values.append(
            (
                desk_snapshot_id,
                symbol,
                item.composite_score,
                conviction_from_composite(item.composite_score),
                item.rank,
                "ranked",
                f"IC-weighted 1M/3M/6M/12-1 momentum blend {item.blended_return:+.2%} (naive-v3: horizon weights from this run's own significance test, not hand-picked), cross-sectional z-score composite {item.composite_score:+.2f}.",
            )
        )
        horizon_by_key = {ret.horizon: ret for ret in item.returns}
        for factor_key, horizon in (
            ("momentum_1m", "1m"),
            ("momentum_3m", "3m"),
            ("momentum_6m", "6m"),
            ("momentum_12m_skip1m", "12m_skip1m"),
        ):
            horizon_return = horizon_by_key.get(horizon)
            value = horizon_return.value if horizon_return else None
            factor_value_rows.append(
                (
                    desk_snapshot_id,
                    symbol,
                    factor_key,
                    value,
                    "ok" if value is not None else "missing",
                    "yahoo",
                    None,
                    f"{item.last_date}T00:00:00Z",
                    f"{item.last_date}T00:00:00Z",
                    timestamp,
                )
            )
        signal_status = "candidate" if item.strength > 0.3 else "watch" if item.strength > 0.1 else "none"
        signal_rows.append(
            (
                desk_snapshot_id,
                symbol,
                signal_status,
                item.direction,
                item.strength,
                f"{item.direction.capitalize()} - rank {item.rank} of {universe_size}",
                f"Naive-v3 IC-weighted 1M/3M/6M/12-1 momentum of {item.blended_return:+.2%} ranks {item.rank} of {universe_size} peers "
                f"(cross-sectional composite {item.composite_score:+.2f}). Not the same as the single-name timing "
                "backtest below — this is cross-sectional standing, that is historical entry/exit timing.",
                None,
                f"{item.last_date}T00:00:00Z",
                f"{item.last_date}T00:00:00Z",
                timestamp,
            )
        )
        if category != "crypto_reference":
            target = suggested_weight(item.composite_score, base_weight=base_weight)
            confidence = max(0.1, min(0.9, 0.5 + item.strength * 0.4))
            recommendation_rows.append(
                (
                    desk_snapshot_id,
                    symbol,
                    "not_available" if item.direction == "neutral" else f"Naive {item.direction} tilt vs. equal-weight baseline",
                    f"Equal-weight baseline is {base_weight:.2%} (1 / {universe_size - 1} non-reference staging symbols); "
                    f"naive-v3 IC-weighted momentum tilt suggests {target:.2%} ({(target - base_weight):+.2%} vs. baseline). "
                    "No real position is tracked yet — this is a research signal, not an executed or held position.",
                    confidence,
                    base_weight,
                    target,
                    target - base_weight,
                    None,
                    "signal_only_no_execution",
                )
            )

        # Independent single-name timing: a real reversal-entry/RSI-exit
        # backtest over this symbol's full fetched history, not derived from
        # the cross-sectional score above.
        backtest_bars = [BacktestBar(time=bar.time, close=bar.close) for bar in bars_by_symbol.get(symbol, [])]
        try:
            backtest = run_reversal_rsi_backtest_v3(symbol, backtest_bars, active_components=active_timing_components)
        except InsufficientBacktestDataError:
            continue
        backtests_run += 1
        backtest_results.append(backtest)

        for trade_index, trade in enumerate(backtest.trades, 1):
            event_rows.append(
                (
                    dataset_snapshot_id,
                    security_id,
                    f"backtest-{symbol.lower()}-entry-{trade_index}",
                    trade.entry_date,
                    "backtest_entry_fill",
                    "executed",
                    f"Backtest entry — {symbol}",
                    trade.entry_price,
                    trade.entry_reason,
                    "engine_backtest",
                    f"{trade.entry_date}T00:00:00Z",
                    f"{trade.entry_date}T00:00:00Z",
                    timestamp,
                )
            )
            if trade.exit_date is not None:
                event_rows.append(
                    (
                        dataset_snapshot_id,
                        security_id,
                        f"backtest-{symbol.lower()}-exit-{trade_index}",
                        trade.exit_date,
                        "backtest_exit_fill",
                        "executed",
                        f"Backtest exit — {symbol} ({trade.return_fraction:+.1%})",
                        trade.exit_price,
                        trade.exit_reason,
                        "engine_backtest",
                        f"{trade.exit_date}T00:00:00Z",
                        f"{trade.exit_date}T00:00:00Z",
                        timestamp,
                    )
                )

        # Current timing state, as of the latest fetched bar -- distinct from
        # the entry/exit fill events above (a historical trade ledger) and
        # from the cross-sectional symbol_signals row (relative standing, not
        # timing). Answers "is now the right time," not "how did this do
        # historically": is a position currently open with no exit trigger
        # yet, flat with no new entry trigger yet, or has no entry signal
        # fired at all in this window. One row per symbol per snapshot
        # (event_status='signal_state', matching symbol_events' own
        # vocabulary for a non-executed, current-state read).
        latest_close = backtest_bars[-1].close if backtest_bars else None
        if backtest.status == "no_entry_signal_active":
            timing_label = f"No entry signal active — {symbol}"
            timing_detail = backtest.methodology
        elif not backtest.trades:
            timing_label = f"No entry signal yet — {symbol}"
            timing_detail = (
                f"No qualifying pullback (trailing-return entry threshold) has fired for {symbol} in this "
                f"window ({backtest.period_start} to {backtest.period_end})."
            )
        elif backtest.trades[-1].exit_date is None:
            open_trade = backtest.trades[-1]
            timing_label = f"Holding — {symbol}"
            timing_detail = (
                f"Entered {open_trade.entry_date} ({open_trade.entry_reason}). Position remains open as of "
                f"{backtest.period_end}; no RSI-overbought exit trigger has fired since."
            )
        else:
            last_trade = backtest.trades[-1]
            timing_label = f"Flat — {symbol}"
            timing_detail = (
                f"Last exited {last_trade.exit_date} ({last_trade.exit_reason}). No new qualifying pullback "
                f"has fired as of {backtest.period_end}."
            )
        event_rows.append(
            (
                dataset_snapshot_id,
                security_id,
                f"timing-signal-{symbol.lower()}",
                backtest.period_end,
                "timing_signal",
                "signal_state",
                timing_label,
                latest_close,
                timing_detail,
                "engine_backtest",
                f"{backtest.period_end}T00:00:00Z",
                f"{backtest.period_end}T00:00:00Z",
                timestamp,
            )
        )

        metric_specs = [
            (
                "total_return",
                "Strategy return",
                backtest.total_return,
                "fraction",
                f"Naive reversal-entry/RSI-exit backtest, {backtest.period_start} to {backtest.period_end}.",
                1,
            ),
            (
                "buy_hold_return",
                "Buy & hold return",
                backtest.buy_hold_return,
                "fraction",
                f"Simple buy-and-hold over the same {backtest.period_start} to {backtest.period_end} window, for comparison.",
                2,
            ),
            (
                "trade_count",
                "Closed trades",
                float(backtest.trade_count),
                "count",
                "Number of completed entry/exit round trips in the backtest window.",
                3,
            ),
            (
                "win_rate",
                "Win rate",
                backtest.win_rate,
                "fraction",
                "Share of closed trades with a positive return.",
                4,
            ),
            (
                "sharpe_ratio",
                "Sharpe ratio",
                backtest.sharpe_ratio,
                "ratio",
                "Annualized, from the strategy's daily equity-curve returns (252 trading days/year).",
                5,
            ),
            (
                "max_drawdown",
                "Max drawdown",
                backtest.max_drawdown,
                "fraction",
                "Largest peak-to-trough decline in the strategy's equity curve over the window.",
                6,
            ),
        ]
        for metric_key, label, value, unit, description, sort_order in metric_specs:
            metric_rows.append(
                (
                    desk_snapshot_id,
                    symbol,
                    metric_key,
                    label,
                    None if value is None else _metric_json(value),
                    unit,
                    "ok" if value is not None else "not_computable",
                    f"{description} {backtest.methodology}",
                    sort_order,
                )
            )

    aggregate = aggregate_backtests(backtest_results, symbols_tested=universe_size)
    desk_backtest_metric_rows: list[tuple[Any, ...]] = []
    if aggregate is not None:
        connection.execute(
            """
            INSERT INTO backtests (
                snapshot_id, label, status, is_available, summary, methodology,
                period_start, period_end, information_cutoff_policy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                desk_snapshot_id,
                "Desk-level backtest aggregate (equal-weighted across staging symbols)",
                "completed",
                1,
                (
                    f"Real reversal-entry/RSI-exit backtests ran for {aggregate.symbols_backtested} of {aggregate.symbols_tested} "
                    f"staging symbols ({aggregate.total_trades} total closed trades, {aggregate.period_start} to "
                    f"{aggregate.period_end}). Mean strategy return {aggregate.mean_total_return:+.1%} vs. mean "
                    f"buy-and-hold {aggregate.mean_buy_hold_return:+.1%} over the same per-symbol windows "
                    f"({aggregate.mean_excess_return:+.1%} average excess). This is an equal-weighted aggregate of "
                    "independent single-name results, not a compounded desk-level equity curve."
                ),
                aggregate.methodology,
                aggregate.period_start,
                aggregate.period_end,
                "Each symbol's backtest only uses that symbol's own price history up to its own last fetched bar; "
                "no cross-symbol or future information is used.",
            ),
        )
        desk_backtest_metric_rows = [
            (desk_snapshot_id, "symbols_backtested", "Symbols backtested", _metric_json(float(aggregate.symbols_backtested)), "count", "ok",
             f"Of {aggregate.symbols_tested} staging symbols scored this run.", 1),
            (desk_snapshot_id, "total_trades", "Total closed trades", _metric_json(float(aggregate.total_trades)), "count", "ok",
             "Sum of closed entry/exit round trips across all backtested symbols.", 2),
            (desk_snapshot_id, "mean_total_return", "Mean strategy return", _metric_json(aggregate.mean_total_return), "fraction", "ok",
             "Equal-weighted mean of each symbol's own-history strategy return.", 3),
            (desk_snapshot_id, "median_total_return", "Median strategy return", _metric_json(aggregate.median_total_return), "fraction", "ok",
             "Median across symbols; less sensitive to any single outlier than the mean.", 4),
            (desk_snapshot_id, "mean_buy_hold_return", "Mean buy & hold return", _metric_json(aggregate.mean_buy_hold_return), "fraction", "ok",
             "Equal-weighted mean of each symbol's own simple buy-and-hold return over the same window.", 5),
            (desk_snapshot_id, "mean_excess_return", "Mean excess vs. buy & hold", _metric_json(aggregate.mean_excess_return), "fraction", "ok",
             "Mean strategy return minus mean buy-and-hold return; positive means the naive rule beat holding on average.", 6),
            (desk_snapshot_id, "mean_win_rate", "Mean win rate", None if aggregate.mean_win_rate is None else _metric_json(aggregate.mean_win_rate),
             "fraction", "ok" if aggregate.mean_win_rate is not None else "not_computable",
             "Mean of each symbol's own win rate, over symbols with at least one closed trade.", 7),
            (desk_snapshot_id, "mean_sharpe_ratio", "Mean Sharpe ratio", None if aggregate.mean_sharpe_ratio is None else _metric_json(aggregate.mean_sharpe_ratio),
             "ratio", "ok" if aggregate.mean_sharpe_ratio is not None else "not_computable",
             "Mean of each symbol's own annualized Sharpe ratio, over symbols where it was computable.", 8),
            (desk_snapshot_id, "mean_max_drawdown", "Mean max drawdown", _metric_json(aggregate.mean_max_drawdown), "fraction", "ok",
             "Equal-weighted mean of each symbol's own peak-to-trough max drawdown.", 9),
            (desk_snapshot_id, "best_symbol_return", "Best performer", _metric_json(aggregate.best_symbol_return), "fraction", "ok",
             f"{aggregate.best_symbol} had the highest strategy return of the {aggregate.symbols_backtested} backtested symbols.", 10),
            (desk_snapshot_id, "worst_symbol_return", "Worst performer", _metric_json(aggregate.worst_symbol_return), "fraction", "ok",
             f"{aggregate.worst_symbol} had the lowest strategy return of the {aggregate.symbols_backtested} backtested symbols.", 11),
        ]
    else:
        connection.execute(
            """
            INSERT INTO backtests (
                snapshot_id, label, status, is_available, summary, methodology,
                period_start, period_end, information_cutoff_policy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                desk_snapshot_id,
                "Desk-level backtest aggregate (equal-weighted across staging symbols)",
                "not_available",
                0,
                f"No staging symbol had at least the required minimum bars to run a backtest this run "
                f"(0 of {universe_size} symbols scored).",
                "Reserved for the naive reversal-entry/RSI-exit single-name backtest "
                "(backend/engine/timing/backtest_v3.py); requires at least 60 daily bars of real fetched "
                "price history per symbol.",
                None,
                None,
                "Each symbol's backtest only uses that symbol's own price history up to its own last fetched bar; "
                "no cross-symbol or future information is used.",
            ),
        )

    connection.executemany(
        """
        INSERT INTO symbols (
            snapshot_id, security_id, symbol, name, asset_type, sector, exchange, currency,
            status, summary, last_price, price_as_of, composite_score, rank,
            freshness_status, freshness_as_of, freshness_summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        symbol_rows,
    )
    connection.executemany(
        """
        INSERT INTO cross_section_rows (snapshot_id, symbol, composite_score, conviction, rank, status, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        cross_section_row_values,
    )
    connection.executemany(
        """
        INSERT INTO factor_values (
            snapshot_id, symbol, factor_key, value, quality_status, source_key,
            source_record_id, observed_at, available_at, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        factor_value_rows,
    )
    connection.executemany(
        """
        INSERT INTO symbol_signals (
            snapshot_id, symbol, status, direction, strength, label, rationale,
            source_node_id, observed_at, available_at, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        signal_rows,
    )
    connection.executemany(
        """
        INSERT INTO symbol_recommendations (
            snapshot_id, symbol, posture, summary, confidence, current_weight,
            target_weight, delta_weight, next_review_at, actionability
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        recommendation_rows,
    )
    if event_rows:
        connection.executemany(
            """
            INSERT OR IGNORE INTO symbol_events (
                dataset_snapshot_id, security_id, event_id, time, event_type,
                event_status, label, price, detail, source_key, observed_at,
                available_at, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            event_rows,
        )
    if metric_rows:
        connection.executemany(
            """
            INSERT INTO symbol_metrics (
                snapshot_id, symbol, metric_key, label, value_json, unit,
                status, description, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            metric_rows,
        )
    if desk_backtest_metric_rows:
        connection.executemany(
            """
            INSERT INTO backtest_metrics (
                snapshot_id, metric_key, label, value_json, unit,
                status, description, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            desk_backtest_metric_rows,
        )

    written = (
        len(factor_dimension_rows)
        + len(symbol_rows)
        + len(cross_section_row_values)
        + len(factor_value_rows)
        + len(signal_rows)
        + len(recommendation_rows)
        + len(event_rows)
        + len(metric_rows)
        + 1
        + len(desk_backtest_metric_rows)
    )
    return StageOutcome(
        status="completed",
        message=(
            f"Ranked {universe_size} staging symbols by naive-v3 IC-weighted cross-sectional momentum "
            f"and ran a real reversal-entry/RSI-exit backtest for {backtests_run} of them "
            f"({sum(1 for row in event_rows if row[4] == 'backtest_entry_fill')} entries logged). "
            + (
                f"Desk-level aggregate: mean return {aggregate.mean_total_return:+.1%} vs. mean buy-and-hold "
                f"{aggregate.mean_buy_hold_return:+.1%}."
                if aggregate is not None
                else "Desk-level aggregate not available (no symbol had enough bars to backtest)."
            )
        ),
        records_read=sum(len(bars) for bars in bars_by_symbol.values()),
        records_written=written,
        dataset_snapshot_id=dataset_snapshot_id,
        desk_snapshot_id=desk_snapshot_id,
    )


def _metric_json(value: float) -> str:
    return json.dumps(value)
