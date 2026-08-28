from __future__ import annotations

import bisect
import sqlite3
import statistics
import uuid
from datetime import date, datetime

from backend.engine.factors import (
    InsufficientBacktestHistoryError,
    run_cross_sectional_momentum_backtest,
)
from backend.engine.factors.momentum_v2 import _pooled_ic_samples
from backend.engine.factors.types import Bar
from backend.engine.indicators import compute_macd, compute_rsi
from backend.engine.regime import InsufficientSeriesDataError, compute_regime_v3
from backend.engine.regime.scoring_v3 import CLUSTERS
from backend.engine.regime.types import SeriesObservation
from backend.engine.research import (
    FORWARD_HORIZON_TRADING_DAYS,
    MIN_SAMPLES,
    FactorSignificanceRun,
    benjamini_hochberg,
    compute_factor_symbol_significance,
    effective_number_of_bets,
    pairwise_correlation_matrix,
    pearson_significance,
    rank_information_coefficient,
    redundancy_pairs,
)
from backend.engine.timing import MACD_CROSSOVER, RSI_OVERBOUGHT_EXIT
from backend.pipeline.stages.common import SERIES_METADATA, _iso_z, _security_id_for

# Strategy families with a real "strategy"-level (whole, traded, realized)
# backtest today. Only strategies that produce something directly tradable
# belong here -- macro_regime_composite is deliberately absent: it is a
# classifier feeding the allocation layer, not something you buy, so
# "what is its CAGR" is not a meaningful question (it stays evaluated at
# component/ensemble level, via factor_significance_runs and
# signal-validation). Adding a new family means one new extraction +
# backtest call, same shape as SIGNAL_VALIDATION_FAMILIES below.
STRATEGY_BACKTEST_FAMILIES = ("cross_sectional_momentum",)

# Factor families with real signal-validation support today. Adding a new
# family means adding one extraction function here (which real DB columns
# -> which aligned series) -- the correlation/ENB/redundancy math and the
# DB write are already generic, not duplicated per family.
SIGNAL_VALIDATION_FAMILIES = ("macro_regime_composite", "cross_sectional_momentum")

REDUNDANCY_THRESHOLD = 0.7

# Milestone 4, step 1 (docs/engine-milestones.md): real macro-factor x
# staging-symbol significance testing, run on demand against an already
# sealed dataset snapshot -- never wedged into the 8-stage manual pipeline,
# which stays Milestone 3's "naive is fine" contract. This module owns the
# DB read/write; backend/engine/research/ owns the pure statistics.


class DatasetNotSealedError(ValueError):
    """The requested dataset snapshot doesn't exist or isn't sealed yet."""


def _latest_sealed_dataset_id(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def _macro_composite_score_series(
    factor_observations: dict[str, list[SeriesObservation]],
) -> list[SeriesObservation]:
    """Real, point-in-time composite regime score at each of CPIAUCSL's own
    observation dates (same anchor convention as _macro_factor_series):
    truncate every factor's history to what was actually available at that
    date, then run it through the real naive-v3 composite (compute_regime_v3)
    -- the same cluster-averaged z-score that drives the live regime label,
    not a re-derived approximation of it. This is what 0.20 named and left
    undone: every individual factor's forward-return correlation was
    tested, never the composite score itself. An anchor with too little
    trailing history for any one factor's z-score window is honestly
    skipped -- InsufficientSeriesDataError, not a fabricated value -- so
    the resulting series is real from its first computable point on, never
    padded."""

    anchor_dates = sorted({obs.observation_date for obs in factor_observations.get("CPIAUCSL", [])})
    composite_observations: list[SeriesObservation] = []
    for anchor in anchor_dates:
        truncated = {
            series_id: [obs for obs in observations if obs.observation_date <= anchor]
            for series_id, observations in factor_observations.items()
        }
        try:
            result = compute_regime_v3(truncated, date.fromisoformat(anchor))
        except InsufficientSeriesDataError:
            continue
        composite_score = sum(result.weights[factor.key] * factor.contribution for factor in result.factors)
        composite_observations.append(
            SeriesObservation(observation_date=anchor, value=composite_score, observed_at="", available_at="")
        )
    return composite_observations


def run_factor_significance_research(
    connection: sqlite3.Connection,
    now: datetime,
    dataset_snapshot_id: str | None = None,
) -> dict[str, object]:
    """Real Pearson-correlation significance testing (with Benjamini-Hochberg
    multiple-comparisons correction) between every fetched macro factor and
    every staging symbol's forward return, over one sealed dataset snapshot.
    Uses the latest sealed dataset when dataset_snapshot_id is omitted.
    """

    resolved_dataset_id = dataset_snapshot_id or _latest_sealed_dataset_id(connection)
    if resolved_dataset_id is None:
        raise DatasetNotSealedError("No sealed dataset snapshot is available to research.")
    dataset = connection.execute(
        "SELECT id, immutable FROM dataset_snapshots WHERE id = ?", (resolved_dataset_id,)
    ).fetchone()
    if dataset is None or not dataset["immutable"]:
        raise DatasetNotSealedError(f"Dataset snapshot {resolved_dataset_id!r} does not exist or is not sealed.")

    factor_observations: dict[str, list[SeriesObservation]] = {}
    for series_id in SERIES_METADATA:
        rows = connection.execute(
            """
            SELECT observation_date, value, observed_at, available_at FROM fred_observations
            WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL
            ORDER BY observation_date
            """,
            (resolved_dataset_id, series_id),
        ).fetchall()
        if rows:
            factor_observations[series_id] = [
                SeriesObservation(
                    observation_date=row["observation_date"],
                    value=row["value"],
                    observed_at=row["observed_at"],
                    available_at=row["available_at"],
                )
                for row in rows
            ]

    composite_series = _macro_composite_score_series(factor_observations)
    if composite_series:
        factor_observations["macro_regime_composite_score"] = composite_series

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols "
        "WHERE active = 1 AND category != 'macro_series' AND research_scope = 'general'"
    ).fetchall()
    symbol_bars: dict[str, list[Bar]] = {}
    for row in staging_rows:
        security_id = _security_id_for(row["symbol"], row["category"])
        bar_rows = connection.execute(
            "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? AND close IS NOT NULL",
            (resolved_dataset_id, security_id),
        ).fetchall()
        if bar_rows:
            symbol_bars[row["symbol"]] = [Bar(time=bar["time"], close=bar["close"]) for bar in bar_rows]

    run = compute_factor_symbol_significance(factor_observations, symbol_bars)

    run_id = f"factor-significance-{uuid.uuid4()}"
    timestamp = _iso_z(now)
    summary = (
        f"Tested {run.test_count} of {run.factor_count * run.symbol_count} (factor, symbol) pairs "
        f"({run.factor_count} factors x {run.symbol_count} symbols; the rest had fewer than "
        f"{run.min_samples} paired samples). {run.significant_count} pairs remained significant "
        f"after {run.correction_method} correction at alpha={run.alpha}."
    )
    connection.execute(
        """
        INSERT INTO factor_significance_runs (
            run_id, dataset_snapshot_id, method, forward_horizon_days, correction_method,
            alpha, min_samples, factor_count, symbol_count, test_count, significant_count,
            summary, started_at, finished_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, resolved_dataset_id, run.method, run.forward_horizon_days, run.correction_method,
            run.alpha, run.min_samples, run.factor_count, run.symbol_count, run.test_count,
            run.significant_count, summary, timestamp, timestamp,
        ),
    )
    _write_macro_regime_diagnostic(connection, run, summary, timestamp)

    connection.executemany(
        """
        INSERT INTO factor_significance_results (
            run_id, factor_key, symbol, sample_size, correlation, p_value,
            adjusted_p_value, significant, direction, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                run_id, result.factor_key, result.symbol, result.sample_size, result.correlation,
                result.p_value, result.adjusted_p_value, 1 if result.significant else 0,
                result.direction, result.status,
            )
            for result in run.results
        ],
    )

    return {
        "run_id": run_id,
        "dataset_snapshot_id": resolved_dataset_id,
        "method": run.method,
        "forward_horizon_days": run.forward_horizon_days,
        "correction_method": run.correction_method,
        "alpha": run.alpha,
        "min_samples": run.min_samples,
        "factor_count": run.factor_count,
        "symbol_count": run.symbol_count,
        "test_count": run.test_count,
        "significant_count": run.significant_count,
        "summary": summary,
        "started_at": timestamp,
        "finished_at": timestamp,
        "results": [
            {
                "factor_key": result.factor_key,
                "symbol": result.symbol,
                "sample_size": result.sample_size,
                "correlation": result.correlation,
                "p_value": result.p_value,
                "adjusted_p_value": result.adjusted_p_value,
                "significant": result.significant,
                "direction": result.direction,
                "status": result.status,
            }
            for result in run.results
        ],
    }


def _write_macro_regime_diagnostic(
    connection: sqlite3.Connection,
    run: FactorSignificanceRun,
    summary: str,
    timestamp: str,
) -> None:
    """Real, auto-updating link from this research run onto the strategy
    registry: 'last checked' becomes a real fact (MAX(as_of) across
    diagnostics), not a guess. Deliberately does NOT touch verification_status
    -- this run tests the 8 individual macro factors AND the composite regime
    score, each against each symbol independently, but one correlation
    surviving correction is not a walk-forward backtest, so flipping
    macro_regime_composite to 'verified' or 'not_significant' from this alone
    would overclaim. The honest move is a diagnostic fact, not a status the
    test doesn't support.
    """

    strategy = connection.execute(
        "SELECT current_version FROM strategies WHERE strategy_key = 'macro_regime_composite'"
    ).fetchone()
    if strategy is None or strategy["current_version"] is None:
        return
    connection.execute(
        """
        INSERT INTO strategy_diagnostics (
            strategy_key, version, metric_key, label, value, unit,
            status, window_label, as_of, description, sort_order
        ) VALUES ('macro_regime_composite', ?, 'factor_significance_summary',
            'Macro factor significance (vs. staging symbols)', ?, 'count_significant_of_tested',
            'ok', ?, ?, ?, 3)
        ON CONFLICT(strategy_key, version, metric_key) DO UPDATE SET
            value = excluded.value, status = excluded.status, window_label = excluded.window_label,
            as_of = excluded.as_of, description = excluded.description
        """,
        (
            strategy["current_version"],
            float(run.significant_count),
            f"{run.test_count} pairs tested",
            timestamp,
            (
                f"{summary} Tests each of the 8 macro factors, and the composite regime score itself, "
                "against each staging symbol individually -- this does not itself verify or invalidate "
                "macro_regime_composite; see Operations -> Research for the full pair-by-pair breakdown."
            ),
        ),
    )


def get_latest_factor_significance_run(connection: sqlite3.Connection) -> dict[str, object] | None:
    run_row = connection.execute(
        "SELECT * FROM factor_significance_runs ORDER BY started_at DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if run_row is None:
        return None
    result_rows = connection.execute(
        """
        SELECT factor_key, symbol, sample_size, correlation, p_value, adjusted_p_value,
               significant, direction, status
        FROM factor_significance_results WHERE run_id = ?
        ORDER BY factor_key, symbol
        """,
        (run_row["run_id"],),
    ).fetchall()
    return {
        "run_id": run_row["run_id"],
        "dataset_snapshot_id": run_row["dataset_snapshot_id"],
        "method": run_row["method"],
        "forward_horizon_days": run_row["forward_horizon_days"],
        "correction_method": run_row["correction_method"],
        "alpha": run_row["alpha"],
        "min_samples": run_row["min_samples"],
        "factor_count": run_row["factor_count"],
        "symbol_count": run_row["symbol_count"],
        "test_count": run_row["test_count"],
        "significant_count": run_row["significant_count"],
        "summary": run_row["summary"],
        "started_at": run_row["started_at"],
        "finished_at": run_row["finished_at"],
        "results": [
            {**dict(row), "significant": bool(row["significant"])} for row in result_rows
        ],
    }


class UnsupportedSignalValidationFamilyError(ValueError):
    """No real extraction is defined for this strategy_key yet."""


def _macro_factor_series(
    connection: sqlite3.Connection, dataset_snapshot_id: str
) -> dict[str, list[float]]:
    """Aligned exact-runtime transformed contributions for all 13 macro
    factors. Each CPI observation date truncates the stored history, calls
    the same compute_regime_v3 used by the application, and keeps an anchor
    only when all current factors are present. Research therefore measures
    the values the score actually consumes, not correlations among raw FRED
    levels with unrelated units and transformations."""

    factor_observations: dict[str, list[SeriesObservation]] = {}
    for series_id in SERIES_METADATA:
        rows = connection.execute(
            """
            SELECT observation_date, value, observed_at, available_at FROM fred_observations
            WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL
            ORDER BY observation_date
            """,
            (dataset_snapshot_id, series_id),
        ).fetchall()
        if rows:
            factor_observations[series_id] = [
                SeriesObservation(
                    observation_date=row["observation_date"],
                    value=row["value"],
                    observed_at=row["observed_at"],
                    available_at=row["available_at"],
                )
                for row in rows
            ]

    anchor_dates = sorted({obs.observation_date for obs in factor_observations.get("CPIAUCSL", [])})
    factor_keys = [member[0] for members in CLUSTERS.values() for member in members]
    series_by_key: dict[str, list[float]] = {key: [] for key in factor_keys}
    for anchor in anchor_dates:
        truncated = {
            series_id: [observation for observation in observations if observation.observation_date <= anchor]
            for series_id, observations in factor_observations.items()
        }
        try:
            result = compute_regime_v3(truncated, date.fromisoformat(anchor))
        except InsufficientSeriesDataError:
            continue
        contributions = {factor.key: factor.contribution for factor in result.factors}
        if not all(key in contributions for key in factor_keys):
            continue
        for key in factor_keys:
            series_by_key[key].append(contributions[key])
    return series_by_key


LITERATURE_MOMENTUM_LOOKBACK_DAYS = 252  # ~12 months of trading days
LITERATURE_MOMENTUM_SKIP_DAYS = 21  # ~1 month, skipped -- short-term reversal is a distinct effect


def _momentum_horizon_series(
    connection: sqlite3.Connection, dataset_snapshot_id: str
) -> dict[str, list[float]]:
    """Real, contemporaneous horizon-return samples pooled across every
    staging symbol's own real price history: at each sampled bar index,
    every horizon return is computed from the SAME (symbol, date) point, so
    the resulting series are aligned by construction, same pooling
    convention as momentum_v2.py's significance test.

    Includes this project's existing naive 1M/3M/6M blend AND, as one
    literature-classic addition proving how little new code a new candidate
    factor actually costs, Jegadeesh & Titman's (1993) original "12-1"
    specification: the trailing 12-month return with the most recent month
    skipped (short-term reversal is a real, distinct, separately documented
    effect from medium-term momentum -- conflating them would misrepresent
    both). Adding this required extending the lookback and one extra
    per-index computation; the correlation/ENB math, the DB write, and the
    UI below were already generic and needed no changes at all.
    """

    horizons = (("1m", 21), ("3m", 63), ("6m", 126))
    stride = 5
    max_lookback = max(LITERATURE_MOMENTUM_LOOKBACK_DAYS, *(lookback for _, lookback in horizons))
    series_by_key: dict[str, list[float]] = {horizon: [] for horizon, _ in horizons}
    series_by_key["12m_skip1m"] = []

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols "
        "WHERE active = 1 AND category != 'macro_series' AND research_scope = 'general'"
    ).fetchall()
    for row in staging_rows:
        security_id = _security_id_for(row["symbol"], row["category"])
        bar_rows = connection.execute(
            "SELECT close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? AND close IS NOT NULL ORDER BY time",
            (dataset_snapshot_id, security_id),
        ).fetchall()
        closes = [bar["close"] for bar in bar_rows]
        n = len(closes)
        for i in range(max_lookback, n, stride):
            row_values: dict[str, float] = {}
            for horizon, lookback in horizons:
                past_close = closes[i - lookback]
                if past_close == 0:
                    row_values = {}
                    break
                row_values[horizon] = (closes[i] - past_close) / abs(past_close)
            if row_values:
                twelve_month_ago = closes[i - LITERATURE_MOMENTUM_LOOKBACK_DAYS]
                one_month_ago = closes[i - LITERATURE_MOMENTUM_SKIP_DAYS]
                if twelve_month_ago == 0:
                    row_values = {}
                else:
                    row_values["12m_skip1m"] = (one_month_ago - twelve_month_ago) / abs(twelve_month_ago)
            if not row_values:
                continue
            for horizon, value in row_values.items():
                series_by_key[horizon].append(value)
    return series_by_key


def run_signal_validation_research(
    connection: sqlite3.Connection,
    now: datetime,
    strategy_key: str,
    dataset_snapshot_id: str | None = None,
) -> dict[str, object]:
    """Real pairwise-correlation, effective-number-of-bets, and redundancy
    research for a factor family -- "number of factors != number of
    independent bets" (Milestone 4, step 2), generalized as a reusable
    research pass rather than a one-off script. Currently supports the two
    factor families this project actually has: macro_regime_composite's 13
    factors and cross_sectional_momentum's 3 horizons. Adding a third means
    one new extraction function, not new math or new tables.
    """

    if strategy_key not in SIGNAL_VALIDATION_FAMILIES:
        raise UnsupportedSignalValidationFamilyError(
            f"No signal-validation extraction is defined for {strategy_key!r} yet. "
            f"Supported: {', '.join(SIGNAL_VALIDATION_FAMILIES)}."
        )

    resolved_dataset_id = dataset_snapshot_id or _latest_sealed_dataset_id(connection)
    if resolved_dataset_id is None:
        raise DatasetNotSealedError("No sealed dataset snapshot is available to research.")
    dataset = connection.execute(
        "SELECT id, immutable FROM dataset_snapshots WHERE id = ?", (resolved_dataset_id,)
    ).fetchone()
    if dataset is None or not dataset["immutable"]:
        raise DatasetNotSealedError(f"Dataset snapshot {resolved_dataset_id!r} does not exist or is not sealed.")

    strategy = connection.execute(
        "SELECT current_version FROM strategies WHERE strategy_key = ?", (strategy_key,)
    ).fetchone()
    if strategy is None or strategy["current_version"] is None:
        raise UnsupportedSignalValidationFamilyError(f"{strategy_key!r} has no current version registered.")
    strategy_version = strategy["current_version"]

    if strategy_key == "macro_regime_composite":
        series_by_key = _macro_factor_series(connection, resolved_dataset_id)
    else:
        series_by_key = _momentum_horizon_series(connection, resolved_dataset_id)
    series_by_key = {key: values for key, values in series_by_key.items() if len(values) >= 3}

    keys = sorted(series_by_key)
    matrix = pairwise_correlation_matrix(series_by_key)
    enb = effective_number_of_bets(keys, matrix)
    flags = redundancy_pairs(matrix, threshold=REDUNDANCY_THRESHOLD)
    flagged_pairs = {(flag.key_a, flag.key_b) for flag in flags}

    run_id = f"signal-validation-{uuid.uuid4()}"
    timestamp = _iso_z(now)
    sample_size = len(next(iter(series_by_key.values()))) if series_by_key else 0
    summary = (
        f"{len(keys)} real factors ({', '.join(keys)}), {sample_size} aligned real samples each -> "
        + (f"effective number of bets {enb:.2f}" if enb is not None else "effective number of bets not computable")
        + f". {len(flags)} pair(s) flagged redundant (|r| >= {REDUNDANCY_THRESHOLD})."
    )

    connection.execute(
        """
        INSERT INTO research_runs (
            research_run_id, strategy_key, strategy_version, dataset_snapshot_id,
            parameters_json, status, started_at, finished_at, summary
        ) VALUES (?, ?, ?, ?, ?, 'completed', ?, ?, ?)
        """,
        (
            run_id, strategy_key, strategy_version, resolved_dataset_id,
            f'{{"redundancy_threshold": {REDUNDANCY_THRESHOLD}}}', timestamp, timestamp, summary,
        ),
    )

    metric_rows: list[tuple] = []
    for (key_a, key_b), correlation in matrix.items():
        flagged = (key_a, key_b) in flagged_pairs
        metric_rows.append(
            (
                run_id, f"{key_a}|{key_b}", "factor_correlation", f"{key_a} vs {key_b}", correlation, "correlation",
                "ok",
                f"Real Pearson correlation over {sample_size} aligned real samples."
                + (f" Flagged redundant (|r| >= {REDUNDANCY_THRESHOLD})." if flagged else ""),
            )
        )
    metric_rows.append(
        (
            run_id, "_ensemble_", "effective_number_of_bets", f"Effective number of bets ({len(keys)} factors)",
            enb, "count", "ok" if enb is not None else "insufficient_data",
            f"PCA/inverse-Herfindahl over the {len(keys)}x{len(keys)} real correlation matrix above."
            if enb is not None
            else "At least one pairwise correlation could not be computed (too few aligned samples).",
        )
    )
    connection.executemany(
        """
        INSERT INTO research_run_metrics (
            research_run_id, subject_key, metric_key, label, value, unit, status, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        metric_rows,
    )

    return {
        "run_id": run_id,
        "strategy_key": strategy_key,
        "strategy_version": strategy_version,
        "dataset_snapshot_id": resolved_dataset_id,
        "sample_size": sample_size,
        "summary": summary,
        "started_at": timestamp,
        "finished_at": timestamp,
        "factor_correlations": [
            {"key_a": key_a, "key_b": key_b, "correlation": correlation, "flagged_redundant": (key_a, key_b) in flagged_pairs}
            for (key_a, key_b), correlation in sorted(matrix.items(), key=lambda item: -abs(item[1]))
        ],
        "effective_number_of_bets": enb,
        "factor_count": len(keys),
    }


def get_latest_signal_validation_run(
    connection: sqlite3.Connection, strategy_key: str
) -> dict[str, object] | None:
    run_row = connection.execute(
        """
        SELECT research_run_id, strategy_key, strategy_version, dataset_snapshot_id, summary, started_at, finished_at
        FROM research_runs
        WHERE strategy_key = ? AND research_run_id LIKE 'signal-validation-%'
        ORDER BY started_at DESC, rowid DESC LIMIT 1
        """,
        (strategy_key,),
    ).fetchone()
    if run_row is None:
        return None
    metric_rows = connection.execute(
        "SELECT subject_key, metric_key, label, value, unit, status, description FROM research_run_metrics WHERE research_run_id = ?",
        (run_row["research_run_id"],),
    ).fetchall()
    correlations = [dict(row) for row in metric_rows if row["metric_key"] == "factor_correlation"]
    enb_row = next((dict(row) for row in metric_rows if row["metric_key"] == "effective_number_of_bets"), None)
    factor_keys: set[str] = set()
    for row in correlations:
        key_a, key_b = row["subject_key"].split("|", 1)
        factor_keys.add(key_a)
        factor_keys.add(key_b)
    return {
        "run_id": run_row["research_run_id"],
        "strategy_key": run_row["strategy_key"],
        "strategy_version": run_row["strategy_version"],
        "dataset_snapshot_id": run_row["dataset_snapshot_id"],
        "summary": run_row["summary"],
        "started_at": run_row["started_at"],
        "finished_at": run_row["finished_at"],
        "factor_correlations": [
            {
                "key_a": row["subject_key"].split("|", 1)[0],
                "key_b": row["subject_key"].split("|", 1)[1],
                "correlation": row["value"],
                "flagged_redundant": "Flagged redundant" in (row["description"] or ""),
            }
            for row in correlations
        ],
        "effective_number_of_bets": enb_row["value"] if enb_row else None,
        "factor_count": len(factor_keys),
    }


class UnsupportedStrategyBacktestFamilyError(ValueError):
    """No real whole-strategy backtest is defined for this strategy_key."""


def _tradable_symbol_bars(connection: sqlite3.Connection, dataset_snapshot_id: str) -> dict[str, list[Bar]]:
    """Real price history for every staging symbol actually eligible to be
    bought -- excludes macro_series (not a security) and crypto_reference
    (BTC-USD is a research reference only, "never a position candidate" per
    this project's non-negotiable rules, see roadmap.md)."""

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols "
        "WHERE active = 1 AND category NOT IN ('macro_series', 'crypto_reference') AND research_scope = 'general'"
    ).fetchall()
    bars_by_symbol: dict[str, list[Bar]] = {}
    for row in staging_rows:
        security_id = _security_id_for(row["symbol"], row["category"])
        bar_rows = connection.execute(
            "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? AND close IS NOT NULL ORDER BY time",
            (dataset_snapshot_id, security_id),
        ).fetchall()
        if bar_rows:
            bars_by_symbol[row["symbol"]] = [Bar(time=bar["time"], close=bar["close"]) for bar in bar_rows]
    return bars_by_symbol


# (horizon key, lookback_days, skip_days) -- 1m/3m/6m match momentum_v2.py's
# live HORIZON_LOOKBACKS exactly; 12m_skip1m matches _momentum_horizon_series's
# literature constants above. Kept independent of both: this is a research
# test, not a change to either the live blend or the ensemble-correlation
# extraction.
MOMENTUM_HORIZONS_FOR_SIGNIFICANCE: tuple[tuple[str, int, int], ...] = (
    ("1m", 21, 0),
    ("3m", 63, 0),
    ("6m", 126, 0),
    ("12m_skip1m", LITERATURE_MOMENTUM_LOOKBACK_DAYS, LITERATURE_MOMENTUM_SKIP_DAYS),
)


def run_momentum_significance_research(
    connection: sqlite3.Connection,
    now: datetime,
    dataset_snapshot_id: str | None = None,
) -> dict[str, object]:
    """Real per-horizon forward-return significance test for
    cross_sectional_momentum's candidate horizons -- the gap 0.16 named and
    explicitly left open ("IC/Rank-IC against forward returns deliberately
    not run this pass"). Reuses the exact pooled (horizon-return,
    forward-return) pairing and Pearson+Benjamini-Hochberg correction already
    proven in momentum_v2.py's live blend-weight test (compute_horizon_weights),
    generalized to also cover 12m_skip1m (Jegadeesh & Titman's 12-1
    specification), plus each horizon's real Rank IC (Spearman) -- the
    factor_rank_ic catalog metric, never populated before. Deliberately does
    NOT touch compute_horizon_weights or HORIZON_LOOKBACKS: this is research
    evidence about a draft component (12m_skip1m, status='draft' in
    strategy_components), not a change to the live blend -- promotion out of
    draft stays a separate, deliberate decision.
    """

    resolved_dataset_id = dataset_snapshot_id or _latest_sealed_dataset_id(connection)
    if resolved_dataset_id is None:
        raise DatasetNotSealedError("No sealed dataset snapshot is available to research.")
    dataset = connection.execute(
        "SELECT id, immutable FROM dataset_snapshots WHERE id = ?", (resolved_dataset_id,)
    ).fetchone()
    if dataset is None or not dataset["immutable"]:
        raise DatasetNotSealedError(f"Dataset snapshot {resolved_dataset_id!r} does not exist or is not sealed.")

    strategy = connection.execute(
        "SELECT current_version FROM strategies WHERE strategy_key = 'cross_sectional_momentum'"
    ).fetchone()
    if strategy is None or strategy["current_version"] is None:
        raise UnsupportedSignalValidationFamilyError("cross_sectional_momentum has no current version registered.")
    strategy_version = strategy["current_version"]

    bars_by_symbol = _tradable_symbol_bars(connection, resolved_dataset_id)

    raw: list[dict[str, object]] = []
    for horizon, lookback_days, skip_days in MOMENTUM_HORIZONS_FOR_SIGNIFICANCE:
        x, y = _pooled_ic_samples(bars_by_symbol, lookback_days, skip_days=skip_days)
        if len(x) < MIN_SAMPLES:
            raw.append({"horizon": horizon, "sample_size": len(x), "status": "insufficient_data"})
            continue
        correlation, p_value = pearson_significance(x, y)
        rank_correlation, rank_p_value = rank_information_coefficient(x, y)
        raw.append(
            {
                "horizon": horizon,
                "sample_size": len(x),
                "correlation": correlation,
                "p_value": p_value,
                "rank_correlation": rank_correlation,
                "rank_p_value": rank_p_value,
                "status": "ok",
            }
        )

    testable = [item for item in raw if item["status"] == "ok"]
    p_values = [item["p_value"] for item in testable]  # type: ignore[misc]
    adjusted_p_values, significant_flags = benjamini_hochberg(p_values, alpha=0.05)
    for item, adjusted_p_value, is_significant in zip(testable, adjusted_p_values, significant_flags):
        item["adjusted_p_value"] = adjusted_p_value
        item["significant"] = is_significant

    run_id = f"momentum-significance-{uuid.uuid4()}"
    timestamp = _iso_z(now)
    significant_count = sum(1 for item in testable if item.get("significant"))
    summary = (
        f"Tested {len(testable)} of {len(MOMENTUM_HORIZONS_FOR_SIGNIFICANCE)} candidate horizons "
        f"({', '.join(item['horizon'] for item in raw)}) against real forward returns; "
        f"{significant_count} remained significant after benjamini_hochberg correction at alpha=0.05."
    )

    connection.execute(
        """
        INSERT INTO research_runs (
            research_run_id, strategy_key, strategy_version, dataset_snapshot_id,
            parameters_json, status, started_at, finished_at, summary
        ) VALUES (?, 'cross_sectional_momentum', ?, ?, '{}', 'completed', ?, ?, ?)
        """,
        (run_id, strategy_version, resolved_dataset_id, timestamp, timestamp, summary),
    )

    metric_rows: list[tuple] = []
    for item in raw:
        horizon = item["horizon"]
        if item["status"] == "insufficient_data":
            metric_rows.append(
                (
                    run_id, horizon, "factor_ic", f"{horizon} forward-return IC", None, "correlation",
                    "insufficient_data",
                    f"Only {item['sample_size']} paired samples; need at least {MIN_SAMPLES}.",
                )
            )
            continue
        is_significant = bool(item["significant"])
        metric_rows.append(
            (
                run_id, horizon, "factor_ic", f"{horizon} forward-return IC", item["correlation"], "correlation",
                "ok",
                f"Pearson r={item['correlation']:+.3f} over {item['sample_size']} real pooled samples, "
                f"adjusted p={item['adjusted_p_value']:.4f} "
                f"({'significant' if is_significant else 'not significant'} after Benjamini-Hochberg correction).",
            )
        )
        metric_rows.append(
            (
                run_id, horizon, "factor_rank_ic", f"{horizon} forward-return Rank IC", item["rank_correlation"],
                "correlation", "ok",
                f"Spearman rank correlation over {item['sample_size']} real pooled samples "
                f"(raw p={item['rank_p_value']:.4f}, not itself multiple-comparisons corrected).",
            )
        )
    connection.executemany(
        """
        INSERT INTO research_run_metrics (
            research_run_id, subject_key, metric_key, label, value, unit, status, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        metric_rows,
    )

    return {
        "run_id": run_id,
        "strategy_key": "cross_sectional_momentum",
        "strategy_version": strategy_version,
        "dataset_snapshot_id": resolved_dataset_id,
        "summary": summary,
        "started_at": timestamp,
        "finished_at": timestamp,
        "results": [
            {
                "horizon": item["horizon"],
                "sample_size": item["sample_size"],
                "status": item["status"],
                "correlation": item.get("correlation"),
                "p_value": item.get("p_value"),
                "adjusted_p_value": item.get("adjusted_p_value"),
                "rank_correlation": item.get("rank_correlation"),
                "rank_p_value": item.get("rank_p_value"),
                "significant": bool(item.get("significant", False)),
            }
            for item in raw
        ],
    }


def get_latest_momentum_significance_run(connection: sqlite3.Connection) -> dict[str, object] | None:
    run_row = connection.execute(
        """
        SELECT research_run_id, strategy_key, strategy_version, dataset_snapshot_id, summary, started_at, finished_at
        FROM research_runs WHERE research_run_id LIKE 'momentum-significance-%'
        ORDER BY started_at DESC, rowid DESC LIMIT 1
        """
    ).fetchone()
    if run_row is None:
        return None
    metric_rows = connection.execute(
        """
        SELECT subject_key, metric_key, value, status, description FROM research_run_metrics
        WHERE research_run_id = ? ORDER BY subject_key, metric_key
        """,
        (run_row["research_run_id"],),
    ).fetchall()
    by_horizon: dict[str, dict[str, object]] = {}
    for row in metric_rows:
        entry = by_horizon.setdefault(row["subject_key"], {"horizon": row["subject_key"]})
        if row["metric_key"] == "factor_ic":
            entry["correlation"] = row["value"]
            entry["status"] = row["status"]
        elif row["metric_key"] == "factor_rank_ic":
            entry["rank_correlation"] = row["value"]
    return {
        "run_id": run_row["research_run_id"],
        "strategy_key": run_row["strategy_key"],
        "strategy_version": run_row["strategy_version"],
        "dataset_snapshot_id": run_row["dataset_snapshot_id"],
        "summary": run_row["summary"],
        "started_at": run_row["started_at"],
        "finished_at": run_row["finished_at"],
        "results": list(by_horizon.values()),
    }


# Matches run_macd_rsi_backtest_v2's live defaults (backend/engine/timing/backtest_v2.py).
TIMING_RSI_PERIOD = 14
TIMING_RSI_OVERBOUGHT = 70.0
TIMING_MACD_FAST = 12
TIMING_MACD_SLOW = 26
TIMING_MACD_SIGNAL = 9


def run_timing_signal_significance_research(
    connection: sqlite3.Connection,
    now: datetime,
    dataset_snapshot_id: str | None = None,
) -> dict[str, object]:
    """Real event-study significance test for macd_rsi_single_name_timing's
    two components -- the piece 0.13's role-tagged design left untested: does
    a real MACD bullish crossover actually predict a positive forward return
    (the only registered entry trigger), and does a real RSI-overbought
    reading actually predict a negative one (one of two registered exit
    triggers)? MACD and RSI are role-tagged, sequential triggers, not
    co-equal weighted factors (see backtest_v2.py's own module docstring) --
    so this is deliberately NOT the same pairwise-correlation/ENB shape used
    for macro_regime_composite/cross_sectional_momentum. Each day across
    every tradable symbol's full history is one sample: a 0/1 event
    indicator (did this component fire today) paired with the real forward
    return -- point-biserial correlation, computed with the exact same
    pearson_significance used everywhere else in this file, since a
    binary-vs-continuous Pearson correlation is mathematically a two-sample
    mean-difference test. A validity check on the rule itself, not a change
    to it: compute_horizon_weights and run_macd_rsi_backtest_v2 are untouched.
    """

    resolved_dataset_id = dataset_snapshot_id or _latest_sealed_dataset_id(connection)
    if resolved_dataset_id is None:
        raise DatasetNotSealedError("No sealed dataset snapshot is available to research.")
    dataset = connection.execute(
        "SELECT id, immutable FROM dataset_snapshots WHERE id = ?", (resolved_dataset_id,)
    ).fetchone()
    if dataset is None or not dataset["immutable"]:
        raise DatasetNotSealedError(f"Dataset snapshot {resolved_dataset_id!r} does not exist or is not sealed.")

    strategy = connection.execute(
        "SELECT current_version FROM strategies WHERE strategy_key = 'macd_rsi_single_name_timing'"
    ).fetchone()
    if strategy is None or strategy["current_version"] is None:
        raise UnsupportedSignalValidationFamilyError("macd_rsi_single_name_timing has no current version registered.")
    strategy_version = strategy["current_version"]

    bars_by_symbol = _tradable_symbol_bars(connection, resolved_dataset_id)

    macd_x: list[float] = []
    macd_y: list[float] = []
    rsi_x: list[float] = []
    rsi_y: list[float] = []
    for bars in bars_by_symbol.values():
        ordered = sorted(bars, key=lambda bar: bar.time)
        closes = [bar.close for bar in ordered]
        n = len(closes)
        macd_line, signal_line, _histogram = compute_macd(
            closes, fast=TIMING_MACD_FAST, slow=TIMING_MACD_SLOW, signal=TIMING_MACD_SIGNAL
        )
        rsi = compute_rsi(closes, period=TIMING_RSI_PERIOD)
        for i in range(1, n - FORWARD_HORIZON_TRADING_DAYS):
            if closes[i] == 0:
                continue
            forward_return = (closes[i + FORWARD_HORIZON_TRADING_DAYS] - closes[i]) / abs(closes[i])
            if (
                macd_line[i] is not None
                and signal_line[i] is not None
                and macd_line[i - 1] is not None
                and signal_line[i - 1] is not None
            ):
                bullish_cross = macd_line[i - 1] <= signal_line[i - 1] and macd_line[i] > signal_line[i]
                macd_x.append(1.0 if bullish_cross else 0.0)
                macd_y.append(forward_return)
            if rsi[i] is not None:
                overbought = rsi[i] >= TIMING_RSI_OVERBOUGHT
                rsi_x.append(1.0 if overbought else 0.0)
                rsi_y.append(forward_return)

    raw: list[dict[str, object]] = []
    for component_key, x, y, event_label in (
        (MACD_CROSSOVER, macd_x, macd_y, "MACD bullish crossover"),
        (RSI_OVERBOUGHT_EXIT, rsi_x, rsi_y, "RSI(14) >= 70 (overbought)"),
    ):
        if len(x) < MIN_SAMPLES or sum(x) < 3 or (len(x) - sum(x)) < 3:
            raw.append({"component_key": component_key, "sample_size": len(x), "status": "insufficient_data"})
            continue
        correlation, p_value = pearson_significance(x, y)
        event_returns = [yi for xi, yi in zip(x, y) if xi == 1.0]
        non_event_returns = [yi for xi, yi in zip(x, y) if xi == 0.0]
        raw.append(
            {
                "component_key": component_key,
                "event_label": event_label,
                "sample_size": len(x),
                "event_count": int(sum(x)),
                "correlation": correlation,
                "p_value": p_value,
                "mean_forward_return_on_event": statistics.fmean(event_returns),
                "mean_forward_return_otherwise": statistics.fmean(non_event_returns),
                "status": "ok",
            }
        )

    testable = [item for item in raw if item["status"] == "ok"]
    p_values = [item["p_value"] for item in testable]  # type: ignore[misc]
    adjusted_p_values, significant_flags = benjamini_hochberg(p_values, alpha=0.05)
    for item, adjusted_p_value, is_significant in zip(testable, adjusted_p_values, significant_flags):
        item["adjusted_p_value"] = adjusted_p_value
        item["significant"] = is_significant

    run_id = f"timing-signal-significance-{uuid.uuid4()}"
    timestamp = _iso_z(now)
    significant_count = sum(1 for item in testable if item.get("significant"))
    summary = (
        f"Tested {len(testable)} of {len(raw)} registered timing components as real event studies "
        f"(pooled across every tradable symbol's full history, {FORWARD_HORIZON_TRADING_DAYS}-day forward return); "
        f"{significant_count} remained significant after benjamini_hochberg correction at alpha=0.05."
    )

    connection.execute(
        """
        INSERT INTO research_runs (
            research_run_id, strategy_key, strategy_version, dataset_snapshot_id,
            parameters_json, status, started_at, finished_at, summary
        ) VALUES (?, 'macd_rsi_single_name_timing', ?, ?, '{}', 'completed', ?, ?, ?)
        """,
        (run_id, strategy_version, resolved_dataset_id, timestamp, timestamp, summary),
    )

    metric_rows: list[tuple] = []
    for item in raw:
        component_key = item["component_key"]
        if item["status"] == "insufficient_data":
            metric_rows.append(
                (
                    run_id, component_key, "factor_ic", f"{component_key} event-study IC", None, "correlation",
                    "insufficient_data",
                    f"Only {item['sample_size']} paired samples, or too few real event days; need at least "
                    f"{MIN_SAMPLES} samples and 3 event days.",
                )
            )
            continue
        is_significant = bool(item["significant"])
        metric_rows.append(
            (
                run_id, component_key, "factor_ic", f"{item['event_label']} event-study IC", item["correlation"],
                "correlation", "ok",
                f"Point-biserial r={item['correlation']:+.3f} over {item['sample_size']} real pooled days "
                f"({item['event_count']} real event days), adjusted p={item['adjusted_p_value']:.4f} "
                f"({'significant' if is_significant else 'not significant'} after Benjamini-Hochberg correction). "
                f"Mean {FORWARD_HORIZON_TRADING_DAYS}-day forward return on event days "
                f"{item['mean_forward_return_on_event']:+.2%} vs. {item['mean_forward_return_otherwise']:+.2%} otherwise.",
            )
        )
    connection.executemany(
        """
        INSERT INTO research_run_metrics (
            research_run_id, subject_key, metric_key, label, value, unit, status, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        metric_rows,
    )

    return {
        "run_id": run_id,
        "strategy_key": "macd_rsi_single_name_timing",
        "strategy_version": strategy_version,
        "dataset_snapshot_id": resolved_dataset_id,
        "summary": summary,
        "started_at": timestamp,
        "finished_at": timestamp,
        "results": [
            {
                "component_key": item["component_key"],
                "event_label": item.get("event_label"),
                "sample_size": item["sample_size"],
                "event_count": item.get("event_count"),
                "status": item["status"],
                "correlation": item.get("correlation"),
                "p_value": item.get("p_value"),
                "adjusted_p_value": item.get("adjusted_p_value"),
                "mean_forward_return_on_event": item.get("mean_forward_return_on_event"),
                "mean_forward_return_otherwise": item.get("mean_forward_return_otherwise"),
                "significant": bool(item.get("significant", False)),
            }
            for item in raw
        ],
    }


def get_latest_timing_signal_significance_run(connection: sqlite3.Connection) -> dict[str, object] | None:
    run_row = connection.execute(
        """
        SELECT research_run_id, strategy_key, strategy_version, dataset_snapshot_id, summary, started_at, finished_at
        FROM research_runs WHERE research_run_id LIKE 'timing-signal-significance-%'
        ORDER BY started_at DESC, rowid DESC LIMIT 1
        """
    ).fetchone()
    if run_row is None:
        return None
    metric_rows = connection.execute(
        """
        SELECT subject_key, value, status, description FROM research_run_metrics
        WHERE research_run_id = ? AND metric_key = 'factor_ic' ORDER BY subject_key
        """,
        (run_row["research_run_id"],),
    ).fetchall()
    return {
        "run_id": run_row["research_run_id"],
        "strategy_key": run_row["strategy_key"],
        "strategy_version": run_row["strategy_version"],
        "dataset_snapshot_id": run_row["dataset_snapshot_id"],
        "summary": run_row["summary"],
        "started_at": run_row["started_at"],
        "finished_at": run_row["finished_at"],
        "results": [
            {
                "component_key": row["subject_key"],
                "correlation": row["value"],
                "status": row["status"],
                "description": row["description"],
            }
            for row in metric_rows
        ],
    }


def run_strategy_backtest_research(
    connection: sqlite3.Connection,
    now: datetime,
    strategy_key: str,
    dataset_snapshot_id: str | None = None,
    *,
    top_n: int = 5,
    rebalance_days: int = 21,
) -> dict[str, object]:
    """Real, whole-strategy walk-forward backtest -- the "strategy"
    granularity tier's first real content. Only strategies that produce
    something directly tradable belong here (see STRATEGY_BACKTEST_FAMILIES);
    a third family needs one new extraction function, not new math or new
    tables, same pattern as run_signal_validation_research.
    """

    if strategy_key not in STRATEGY_BACKTEST_FAMILIES:
        raise UnsupportedStrategyBacktestFamilyError(
            f"No strategy-level backtest is defined for {strategy_key!r} yet. "
            f"Supported: {', '.join(STRATEGY_BACKTEST_FAMILIES)}."
        )

    resolved_dataset_id = dataset_snapshot_id or _latest_sealed_dataset_id(connection)
    if resolved_dataset_id is None:
        raise DatasetNotSealedError("No sealed dataset snapshot is available to research.")
    dataset = connection.execute(
        "SELECT id, immutable FROM dataset_snapshots WHERE id = ?", (resolved_dataset_id,)
    ).fetchone()
    if dataset is None or not dataset["immutable"]:
        raise DatasetNotSealedError(f"Dataset snapshot {resolved_dataset_id!r} does not exist or is not sealed.")

    strategy = connection.execute(
        "SELECT current_version FROM strategies WHERE strategy_key = ?", (strategy_key,)
    ).fetchone()
    if strategy is None or strategy["current_version"] is None:
        raise UnsupportedStrategyBacktestFamilyError(f"{strategy_key!r} has no current version registered.")
    strategy_version = strategy["current_version"]

    bars_by_symbol = _tradable_symbol_bars(connection, resolved_dataset_id)
    backtest = run_cross_sectional_momentum_backtest(bars_by_symbol, top_n=top_n, rebalance_days=rebalance_days)

    run_id = f"strategy-backtest-{uuid.uuid4()}"
    timestamp = _iso_z(now)
    summary = (
        f"Naive-v1 walk-forward: top {backtest.top_n} of {len(bars_by_symbol)} tradable symbols, rebalanced every "
        f"{backtest.rebalance_days} trading days, {len(backtest.periods)} periods ({backtest.period_start} to "
        f"{backtest.period_end}). Total return {backtest.total_return:+.1%} vs. equal-weight universe benchmark "
        f"{backtest.benchmark_total_return:+.1%}. "
        + (f"CAGR {backtest.cagr:+.1%}. " if backtest.cagr is not None else "")
        + (f"Sharpe {backtest.sharpe_ratio:.2f}. " if backtest.sharpe_ratio is not None else "")
        + f"Max drawdown {backtest.max_drawdown:.1%}."
    )

    connection.execute(
        """
        INSERT INTO research_runs (
            research_run_id, strategy_key, strategy_version, dataset_snapshot_id,
            parameters_json, status, started_at, finished_at, summary
        ) VALUES (?, ?, ?, ?, ?, 'completed', ?, ?, ?)
        """,
        (
            run_id, strategy_key, strategy_version, resolved_dataset_id,
            f'{{"top_n": {top_n}, "rebalance_days": {rebalance_days}}}', timestamp, timestamp, summary,
        ),
    )

    subject_key = "_strategy_"
    metric_specs: list[tuple[str, str, float | None, str, str]] = [
        ("cagr", "CAGR", backtest.cagr, "fraction", "Annualized compound growth rate of the naive walk-forward equity curve."),
        ("annualized_volatility", "Annualized volatility", backtest.annualized_volatility, "fraction", "Standard deviation of rebalance-period returns, annualized."),
        ("sharpe_ratio", "Sharpe ratio", backtest.sharpe_ratio, "ratio", "Annualized mean return divided by annualized volatility; no risk-free rate subtracted (naive)."),
        ("max_drawdown", "Maximum drawdown", backtest.max_drawdown, "fraction", "Largest peak-to-trough decline in the equity curve."),
        ("calmar_ratio", "Calmar ratio", backtest.calmar_ratio, "ratio", "CAGR divided by |maximum drawdown|."),
        ("portfolio_turnover", "Turnover", backtest.portfolio_turnover, "fraction", "Mean fraction of the top-N holdings that change at each rebalance."),
    ]
    connection.executemany(
        """
        INSERT INTO research_run_metrics (
            research_run_id, subject_key, metric_key, label, value, unit, status, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (run_id, subject_key, metric_key, label, value, unit, "ok" if value is not None else "not_computable", description)
            for metric_key, label, value, unit, description in metric_specs
        ],
    )

    return {
        "run_id": run_id,
        "strategy_key": strategy_key,
        "strategy_version": strategy_version,
        "dataset_snapshot_id": resolved_dataset_id,
        "top_n": backtest.top_n,
        "rebalance_days": backtest.rebalance_days,
        "period_start": backtest.period_start,
        "period_end": backtest.period_end,
        "period_count": len(backtest.periods),
        "total_return": backtest.total_return,
        "benchmark_total_return": backtest.benchmark_total_return,
        "cagr": backtest.cagr,
        "annualized_volatility": backtest.annualized_volatility,
        "sharpe_ratio": backtest.sharpe_ratio,
        "max_drawdown": backtest.max_drawdown,
        "calmar_ratio": backtest.calmar_ratio,
        "portfolio_turnover": backtest.portfolio_turnover,
        "win_rate": backtest.win_rate,
        "summary": summary,
        "started_at": timestamp,
        "finished_at": timestamp,
    }


def get_latest_strategy_backtest_run(
    connection: sqlite3.Connection, strategy_key: str
) -> dict[str, object] | None:
    run_row = connection.execute(
        """
        SELECT research_run_id, strategy_key, strategy_version, dataset_snapshot_id, summary, started_at, finished_at
        FROM research_runs
        WHERE strategy_key = ? AND research_run_id LIKE 'strategy-backtest-%'
        ORDER BY started_at DESC, rowid DESC LIMIT 1
        """,
        (strategy_key,),
    ).fetchone()
    if run_row is None:
        return None
    metric_rows = connection.execute(
        "SELECT metric_key, value, status FROM research_run_metrics WHERE research_run_id = ? AND subject_key = '_strategy_'",
        (run_row["research_run_id"],),
    ).fetchall()
    metrics_by_key = {row["metric_key"]: row["value"] for row in metric_rows}
    return {
        "run_id": run_row["research_run_id"],
        "strategy_key": run_row["strategy_key"],
        "strategy_version": run_row["strategy_version"],
        "dataset_snapshot_id": run_row["dataset_snapshot_id"],
        "summary": run_row["summary"],
        "started_at": run_row["started_at"],
        "finished_at": run_row["finished_at"],
        "cagr": metrics_by_key.get("cagr"),
        "annualized_volatility": metrics_by_key.get("annualized_volatility"),
        "sharpe_ratio": metrics_by_key.get("sharpe_ratio"),
        "max_drawdown": metrics_by_key.get("max_drawdown"),
        "calmar_ratio": metrics_by_key.get("calmar_ratio"),
        "portfolio_turnover": metrics_by_key.get("portfolio_turnover"),
    }
