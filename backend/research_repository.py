from __future__ import annotations

import bisect
import sqlite3
import uuid
from datetime import datetime

from backend.engine.factors.types import Bar
from backend.engine.regime.types import SeriesObservation
from backend.engine.research import (
    FORWARD_HORIZON_TRADING_DAYS,
    MIN_SAMPLES,
    FactorSignificanceRun,
    compute_factor_symbol_significance,
    effective_number_of_bets,
    pairwise_correlation_matrix,
    redundancy_pairs,
)
from backend.pipeline.stages.common import SERIES_METADATA, _iso_z, _security_id_for

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

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols WHERE active = 1 AND category != 'macro_series'"
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
    -- this run tests each macro factor against each symbol individually, not
    the regime composite as one unit, so flipping macro_regime_composite to
    'verified' or 'not_significant' from this alone would overclaim. The
    honest move is a diagnostic fact, not a status the test doesn't support.
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
                f"{summary} Tests each of the 8 macro factors against each staging symbol individually, "
                "not the regime composite as a single unit -- this does not itself verify or invalidate "
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
    """Real, point-in-time-aligned series for all 8 macro factors: for each
    of CPIAUCSL's own real monthly observation dates (the anchor -- any
    always-present monthly series would do), take every factor's nearest
    real observation at or before that date (same "nearest available, never
    future" rule already used in factor_symbol_correlation.py). An anchor
    is dropped entirely if any one factor has no observation yet at that
    point -- every returned series has the same length, corresponding to
    the exact same real dates, by construction rather than by trimming."""

    factor_observations: dict[str, list[SeriesObservation]] = {}
    for series_id in SERIES_METADATA:
        rows = connection.execute(
            """
            SELECT observation_date, value FROM fred_observations
            WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL
            ORDER BY observation_date
            """,
            (dataset_snapshot_id, series_id),
        ).fetchall()
        if rows:
            factor_observations[series_id] = [
                SeriesObservation(observation_date=row["observation_date"], value=row["value"], observed_at="", available_at="")
                for row in rows
            ]

    anchor_dates = sorted({obs.observation_date for obs in factor_observations.get("CPIAUCSL", [])})
    lookup = {
        series_id: (
            [obs.observation_date for obs in sorted(observations, key=lambda o: o.observation_date)],
            [obs.value for obs in sorted(observations, key=lambda o: o.observation_date)],
        )
        for series_id, observations in factor_observations.items()
    }

    series_by_key: dict[str, list[float]] = {series_id: [] for series_id in factor_observations}
    for anchor in anchor_dates:
        row_values: dict[str, float] = {}
        for series_id, (dates, values) in lookup.items():
            idx = bisect.bisect_right(dates, anchor) - 1
            if idx < 0:
                break
            row_values[series_id] = values[idx]
        if len(row_values) != len(lookup):
            continue
        for series_id, value in row_values.items():
            series_by_key[series_id].append(value)
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
        "SELECT symbol, category FROM staging_symbols WHERE active = 1 AND category != 'macro_series'"
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
    factor families this project actually has: macro_regime_composite's 8
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
    }
