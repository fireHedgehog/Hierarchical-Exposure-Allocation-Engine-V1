from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from backend.engine.factors.types import Bar
from backend.engine.regime.types import SeriesObservation
from backend.engine.research import FORWARD_HORIZON_TRADING_DAYS, MIN_SAMPLES, compute_factor_symbol_significance
from backend.pipeline.stages.common import SERIES_METADATA, _iso_z, _security_id_for

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
