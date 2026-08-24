from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

from backend.pipeline.stages.common import (
    CLOCK_SKEW_TOLERANCE_SECONDS,
    PRICE_HARD_MAX_AGE_DAYS,
    PRICE_SOFT_MAX_AGE_DAYS,
    SERIES_METADATA,
    StageOutcome,
)


def run_validate_data_stage(
    connection: sqlite3.Connection,
    now: datetime,
    dataset_snapshot_id: str | None,
) -> StageOutcome:
    """Validate freshness/completeness of macro series and price bars.

    Does NOT seal the dataset — factor_engine still needs to write dataset-
    scoped symbol_events (the backtest trade log) after this stage runs.
    run_pipeline seals both the dataset and the desk snapshot once, together,
    after the last stage that actually runs this pass — the dispatch loop's
    own blocking logic (this stage's outcome gates whether regime_filter even
    runs) is what regime_filter now trusts instead of re-checking `immutable`.
    """

    if not dataset_snapshot_id:
        return StageOutcome(
            status="blocked",
            message="No dataset snapshot was produced by fetch_data to validate.",
            error_code="no_dataset_to_validate",
        )
    rows = connection.execute(
        """
        SELECT series_id, observation_date, value, available_at
        FROM fred_observations WHERE dataset_snapshot_id = ?
        """,
        (dataset_snapshot_id,),
    ).fetchall()
    by_series: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_series.setdefault(row["series_id"], []).append(row)

    hard_failures: list[str] = []
    warnings: list[str] = []
    future_limit = now + timedelta(seconds=CLOCK_SKEW_TOLERANCE_SECONDS)
    for series_id, meta in SERIES_METADATA.items():
        series_rows = [row for row in by_series.get(series_id, []) if row["value"] is not None]
        if not series_rows:
            hard_failures.append(f"{series_id}: no non-null observation stored.")
            continue
        latest = max(series_rows, key=lambda row: row["observation_date"])
        available_at = datetime.fromisoformat(latest["available_at"].replace("Z", "+00:00"))
        if available_at > future_limit:
            hard_failures.append(f"{series_id}: latest observation is future-dated.")
            continue
        age_days = (now.date() - date.fromisoformat(latest["observation_date"])).days
        max_age_days = meta["max_age_days"]
        if age_days > max_age_days * 2:
            hard_failures.append(
                f"{series_id}: latest observation is {age_days} days old (hard limit {max_age_days * 2})."
            )
        elif age_days > max_age_days:
            warnings.append(
                f"{series_id}: latest observation is {age_days} days old (soft limit {max_age_days})."
            )

    bar_rows = connection.execute(
        """
        SELECT security_id, MAX(time) AS latest_date, COUNT(*) AS bar_count
        FROM symbol_bars WHERE dataset_snapshot_id = ?
        GROUP BY security_id
        """,
        (dataset_snapshot_id,),
    ).fetchall()
    if not bar_rows:
        hard_failures.append("no price bars were stored for any staging symbol.")
    for row in bar_rows:
        if row["bar_count"] < 22:
            hard_failures.append(f"{row['security_id']}: only {row['bar_count']} bars stored, need at least 22.")
            continue
        latest_date = date.fromisoformat(row["latest_date"])
        if datetime(latest_date.year, latest_date.month, latest_date.day, tzinfo=timezone.utc) > future_limit:
            hard_failures.append(f"{row['security_id']}: latest bar is future-dated.")
            continue
        age_days = (now.date() - latest_date).days
        if age_days > PRICE_HARD_MAX_AGE_DAYS:
            hard_failures.append(f"{row['security_id']}: latest bar is {age_days} days old (hard limit {PRICE_HARD_MAX_AGE_DAYS}).")
        elif age_days > PRICE_SOFT_MAX_AGE_DAYS:
            warnings.append(f"{row['security_id']}: latest bar is {age_days} days old (soft limit {PRICE_SOFT_MAX_AGE_DAYS}).")

    if hard_failures:
        return StageOutcome(
            status="blocked",
            message="Validation failed: " + "; ".join(hard_failures),
            error_code="validation_failed",
            records_read=len(rows) + sum(row["bar_count"] for row in bar_rows),
            dataset_snapshot_id=dataset_snapshot_id,
        )

    connection.execute(
        "UPDATE dataset_snapshots SET status = 'validated' WHERE id = ?",
        (dataset_snapshot_id,),
    )
    message = (
        "Validation passed with warnings: " + "; ".join(warnings)
        if warnings
        else "All required series and staging symbols passed freshness and completeness checks."
    )
    return StageOutcome(
        status="completed_with_warnings" if warnings else "completed",
        message=message,
        records_read=len(rows) + sum(row["bar_count"] for row in bar_rows),
        dataset_snapshot_id=dataset_snapshot_id,
    )
