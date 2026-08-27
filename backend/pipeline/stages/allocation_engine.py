from __future__ import annotations

import sqlite3
from datetime import datetime

from backend.engine.allocation import (
    InsufficientAllocationDataError,
    SymbolAllocationInput,
    compute_risk_envelope_v2 as compute_risk_envelope,
)
from backend.pipeline.stages.common import StageOutcome, _iso_z


def _humanize(category: str) -> str:
    return category.replace("_", " ").title()


def run_allocation_engine_stage(
    connection: sqlite3.Connection,
    now: datetime,
    dataset_snapshot_id: str | None,
    desk_snapshot_id: str | None,
) -> StageOutcome:
    """Real top-down risk envelope: regime confidence (already computed by
    regime_filter) scales gross exposure; factor_engine's per-symbol tilts
    roll up into sleeve targets. Updates the still-open desk snapshot in
    place (does not insert a new one) and adds the decision graph
    (desk -> risk envelope -> sleeves).
    """

    if not dataset_snapshot_id or not desk_snapshot_id:
        return StageOutcome(
            status="blocked",
            message="No dataset or open desk snapshot is available for allocation.",
            error_code="no_snapshot_to_allocate",
        )
    desk = connection.execute(
        "SELECT id, regime_confidence FROM desk_snapshots WHERE id = ? AND immutable = 0",
        (desk_snapshot_id,),
    ).fetchone()
    if desk is None:
        return StageOutcome(
            status="blocked",
            message="The desk snapshot from regime_filter is missing or already sealed.",
            error_code="desk_not_open",
            dataset_snapshot_id=dataset_snapshot_id,
            desk_snapshot_id=desk_snapshot_id,
        )
    if desk["regime_confidence"] is None:
        return StageOutcome(
            status="blocked",
            message="No regime confidence is recorded on this snapshot yet.",
            error_code="regime_confidence_missing",
            dataset_snapshot_id=dataset_snapshot_id,
            desk_snapshot_id=desk_snapshot_id,
        )

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols "
        "WHERE active = 1 AND category != 'macro_series' AND research_scope = 'general'"
    ).fetchall()
    category_by_symbol = {row["symbol"]: row["category"] for row in staging_rows}

    cross_section = connection.execute(
        "SELECT symbol, composite_score FROM cross_section_rows WHERE snapshot_id = ?",
        (desk_snapshot_id,),
    ).fetchall()
    recommendation_by_symbol = {
        row["symbol"]: row["target_weight"]
        for row in connection.execute(
            "SELECT symbol, target_weight FROM symbol_recommendations WHERE snapshot_id = ?",
            (desk_snapshot_id,),
        ).fetchall()
    }

    non_crypto_count = sum(1 for row in staging_rows if row["category"] != "crypto_reference")
    base_weight = 1.0 / non_crypto_count if non_crypto_count else 0.0

    symbol_inputs: list[SymbolAllocationInput] = []
    for row in cross_section:
        symbol = row["symbol"]
        category = category_by_symbol.get(symbol)
        target_weight = recommendation_by_symbol.get(symbol)
        if category is None or category == "crypto_reference" or target_weight is None:
            continue
        symbol_inputs.append(SymbolAllocationInput(symbol, category, row["composite_score"], base_weight, target_weight))

    try:
        envelope = compute_risk_envelope(desk["regime_confidence"], symbol_inputs)
    except InsufficientAllocationDataError as error:
        return StageOutcome(
            status="failed",
            message=f"Allocation failed: {error}",
            error_code="insufficient_allocation_data",
            dataset_snapshot_id=dataset_snapshot_id,
            desk_snapshot_id=desk_snapshot_id,
        )

    timestamp = _iso_z(now)
    delta_net = envelope.target_net_exposure - envelope.current_net_exposure
    delta_gross = envelope.target_gross_exposure - envelope.current_gross_exposure
    posture = (
        "Risk-on: above-baseline gross exposure"
        if envelope.gross_multiplier > 1.05
        else "Risk-off: below-baseline gross exposure"
        if envelope.gross_multiplier < 0.95
        else "Neutral: baseline gross exposure"
    )
    connection.execute(
        """
        UPDATE desk_snapshots
        SET recommendation_posture = ?, recommendation_summary = ?, recommendation_confidence = ?,
            current_net_exposure = ?, current_gross_exposure = ?, target_net_exposure = ?,
            target_gross_exposure = ?, delta_net_exposure = ?, delta_gross_exposure = ?,
            change_summary = ?
        WHERE id = ?
        """,
        (
            posture,
            envelope.summary,
            desk["regime_confidence"],
            envelope.current_net_exposure,
            envelope.current_gross_exposure,
            envelope.target_net_exposure,
            envelope.target_gross_exposure,
            delta_net,
            delta_gross,
            f"Gross exposure moves {delta_gross:+.1%} from the equal-weight baseline; net moves {delta_net:+.1%}. "
            "Naive long-only model — net always equals gross here.",
            desk_snapshot_id,
        ),
    )

    node_rows: list[tuple] = [
        (
            desk_snapshot_id, "desk", None, "desk", "Desk", "computed",
            f"Gross exposure target {envelope.target_gross_exposure:.0%} ({envelope.gross_multiplier:.2f}x the equal-weight baseline).",
            desk["regime_confidence"], envelope.current_gross_exposure, envelope.target_gross_exposure, delta_gross,
            "fraction", None, "[]", 0.0, 0.0, 1,
        ),
        (
            desk_snapshot_id, "risk_envelope", "desk", "risk_budget", "Risk envelope", "computed",
            envelope.summary, desk["regime_confidence"], envelope.current_gross_exposure, envelope.target_gross_exposure,
            delta_gross, "fraction", envelope.gross_multiplier, "[]", 0.0, 100.0, 2,
        ),
    ]
    edge_rows: list[tuple] = [
        (desk_snapshot_id, "desk_to_risk_envelope", "desk", "risk_envelope", "funds", 1.0,
         "The desk root funds the risk envelope before any sleeve is considered.", 1),
    ]
    sleeve_count = len(envelope.sleeves)
    for index, sleeve in enumerate(envelope.sleeves, 1):
        node_id = f"sleeve_{sleeve.category}"
        x = (index - (sleeve_count + 1) / 2) * 150.0
        node_rows.append(
            (
                desk_snapshot_id, node_id, "risk_envelope", "sleeve", _humanize(sleeve.category), "computed",
                f"{len(sleeve.symbols)} staging symbols; average cross-sectional composite {sleeve.avg_composite_score:+.2f}.",
                None, sleeve.base_weight_sum, sleeve.target_weight_sum, sleeve.target_weight_sum - sleeve.base_weight_sum,
                "fraction", sleeve.avg_composite_score, "[]", x, 200.0, 2 + index,
            )
        )
        edge_rows.append(
            (
                desk_snapshot_id, f"risk_envelope_to_{node_id}", "risk_envelope", node_id, "allocates",
                sleeve.target_weight_sum, f"Sleeve target {sleeve.target_weight_sum:.1%} of the risk envelope.", 1 + index,
            )
        )

    connection.executemany(
        """
        INSERT INTO decision_nodes (
            snapshot_id, node_id, parent_node_id, node_type, label, status, summary,
            confidence, current_value, target_value, delta_value, value_unit,
            contribution, constraints_json, x, y, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        node_rows,
    )
    connection.executemany(
        """
        INSERT INTO decision_edges (snapshot_id, edge_id, from_node_id, to_node_id, relation, weight, rationale, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        edge_rows,
    )

    best_sleeve = max(envelope.sleeves, key=lambda item: item.avg_composite_score)
    worst_sleeve = min(envelope.sleeves, key=lambda item: item.avg_composite_score)
    point_rows = [
        (desk_snapshot_id, "rationale",
         f"Regime confidence {desk['regime_confidence']:.0%} sets a {envelope.gross_multiplier:.2f}x gross-exposure multiplier against the equal-weight baseline.", 1),
        (desk_snapshot_id, "rationale",
         f"Strongest sleeve by average cross-sectional composite: {_humanize(best_sleeve.category)} ({best_sleeve.avg_composite_score:+.2f}).", 2),
        (desk_snapshot_id, "rationale",
         f"Weakest sleeve: {_humanize(worst_sleeve.category)} ({worst_sleeve.avg_composite_score:+.2f}).", 3),
        (desk_snapshot_id, "invalidation",
         "Reassess if regime confidence crosses back through 50% (the neutral multiplier point) or the composite regime score flips sign.", 1),
    ]
    connection.executemany(
        "INSERT INTO recommendation_points (snapshot_id, point_type, text, sort_order) VALUES (?, ?, ?, ?)",
        point_rows,
    )

    written = len(node_rows) + len(edge_rows) + len(point_rows) + 1
    return StageOutcome(
        status="completed",
        message=(
            f"Computed risk envelope: {envelope.gross_multiplier:.2f}x multiplier, target gross "
            f"{envelope.target_gross_exposure:.0%}, {sleeve_count} sleeves."
        ),
        records_read=len(cross_section),
        records_written=written,
        dataset_snapshot_id=dataset_snapshot_id,
        desk_snapshot_id=desk_snapshot_id,
    )
