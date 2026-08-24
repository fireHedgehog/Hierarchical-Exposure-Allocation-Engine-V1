from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from backend.engine.regime import InsufficientSeriesDataError, SeriesObservation, compute_regime
from backend.pipeline.stages.common import StageOutcome, _iso_z, _json


def run_regime_filter_stage(
    connection: sqlite3.Connection,
    now: datetime,
    dataset_snapshot_id: str | None,
    engine_mode: str,
) -> StageOutcome:
    """Score the validated dataset into a real, still-open regime desk snapshot.

    Deliberately does NOT seal the dataset or the desk snapshot — factor_engine
    still needs to write dataset-scoped symbol_events (the backtest trade log)
    and desk-scoped cross-sectional results after this stage runs.
    run_pipeline seals both once, together, after the last stage that
    actually runs this pass. This stage only checks the dataset exists; the
    dispatch loop already guarantees validate_data succeeded before
    dispatching here (a blocked/failed validate_data prevents this stage from
    running at all), so re-checking `immutable` here would be redundant and
    would actually be wrong now that sealing happens later.
    """

    if not dataset_snapshot_id:
        return StageOutcome(
            status="blocked",
            message="No validated dataset snapshot is available to score.",
            error_code="no_dataset_to_score",
        )
    dataset = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE id = ?",
        (dataset_snapshot_id,),
    ).fetchone()
    if dataset is None:
        return StageOutcome(
            status="blocked",
            message="The dataset for this run could not be found; refusing to publish a decision from missing inputs.",
            error_code="dataset_missing",
            dataset_snapshot_id=dataset_snapshot_id,
        )
    rows = connection.execute(
        """
        SELECT series_id, observation_date, value, observed_at, available_at
        FROM fred_observations
        WHERE dataset_snapshot_id = ? AND value IS NOT NULL
        """,
        (dataset_snapshot_id,),
    ).fetchall()
    series: dict[str, list[SeriesObservation]] = {}
    for row in rows:
        series.setdefault(row["series_id"], []).append(
            SeriesObservation(
                observation_date=row["observation_date"],
                value=row["value"],
                observed_at=row["observed_at"],
                available_at=row["available_at"],
            )
        )

    try:
        regime = compute_regime(series, now.date())
    except InsufficientSeriesDataError as error:
        return StageOutcome(
            status="failed",
            message=f"Regime scoring failed: {error}",
            error_code="insufficient_series_data",
            dataset_snapshot_id=dataset_snapshot_id,
        )

    desk_id = f"real-regime-{uuid.uuid4()}"
    timestamp = _iso_z(now)
    connection.execute(
        """
        INSERT INTO desk_snapshots (
            id, dataset_snapshot_id, as_of, created_at, mode, data_classification,
            is_live, is_demo, status, immutable, seed_revision, title, subtitle,
            disclaimer, regime_label, regime_confidence, regime_summary,
            recommendation_posture, recommendation_summary, recommendation_confidence,
            current_net_exposure, current_gross_exposure, target_net_exposure,
            target_gross_exposure, delta_net_exposure, delta_gross_exposure,
            change_summary, next_review_at, engine_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            desk_id,
            dataset_snapshot_id,
            timestamp,
            timestamp,
            "research",
            "real",
            0,
            0,
            "engine_in_progress",
            0,
            "regime-engine-v1",
            "Hierarchical desk decision snapshot",
            "Real regime + cross-sectional state computed from free data; allocation/instrument stages not yet implemented.",
            "REAL DATA, NAIVE FIRST-PASS FORMULAS. Downstream allocation and instrument stages are not implemented. "
            "No recommendation, weight, or trade should be treated as investment advice or an executable order.",
            regime.label,
            regime.confidence,
            regime.summary,
            "not_available",
            "Allocation and instrument stages are not implemented yet; regime and cross-sectional symbol signals are real in this snapshot.",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "Regime and factor engines are not yet connected to a portfolio allocation engine.",
            None,
            engine_mode,
        ),
    )

    filter_rows = [
        (
            desk_id,
            factor.key,
            factor.name,
            _json(factor.raw_value),
            _json(factor.threshold),
            factor.filter_status,
            factor.filter_explanation,
            timestamp,
            timestamp,
            timestamp,
            "fred",
            order,
        )
        for order, factor in enumerate(regime.factors, 1)
    ]
    connection.executemany(
        """
        INSERT INTO regime_filters (
            snapshot_id, filter_key, name, value_json, threshold_json, status,
            explanation, observed_at, available_at, ingested_at, source_key, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        filter_rows,
    )

    weight_rows = [
        (desk_id, key, key.capitalize(), value, "fraction", order)
        for order, (key, value) in enumerate(regime.weights.items(), 1)
    ]
    connection.executemany(
        """
        INSERT INTO regime_weights (snapshot_id, weight_key, name, value, unit, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        weight_rows,
    )

    contribution_rows = [
        (
            desk_id,
            factor.key,
            factor.name,
            factor.contribution,
            "score",
            factor.direction,
            factor.contribution_explanation,
            order,
        )
        for order, factor in enumerate(regime.factors, 1)
    ]
    connection.executemany(
        """
        INSERT INTO regime_contributions (
            snapshot_id, contribution_key, name, value, unit, direction, explanation, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        contribution_rows,
    )

    evidence_rows = [
        (
            desk_id,
            factor.key,
            item.key,
            item.label,
            _json(item.value),
            item.detail,
            item.observed_at,
            item.available_at,
            timestamp,
            evidence_order,
        )
        for factor in regime.factors
        for evidence_order, item in enumerate(factor.evidence, 1)
    ]
    connection.executemany(
        """
        INSERT INTO regime_evidence (
            snapshot_id, contribution_key, evidence_key, label, value_json, detail,
            observed_at, available_at, ingested_at, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        evidence_rows,
    )

    written = 1 + len(filter_rows) + len(weight_rows) + len(contribution_rows) + len(evidence_rows)
    return StageOutcome(
        status="completed",
        message=f"Published real regime state {desk_id}: {regime.label} (confidence {regime.confidence:.2f}).",
        records_read=len(rows),
        records_written=written,
        dataset_snapshot_id=dataset_snapshot_id,
        desk_snapshot_id=desk_id,
    )
