from __future__ import annotations

import json
import sqlite3
from typing import Any


class SnapshotNotFoundError(LookupError):
    pass


class SymbolNotFoundError(LookupError):
    pass


def _json_value(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


def _latest_snapshot(connection: sqlite3.Connection) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT desk.*
        FROM desk_snapshots AS desk
        LEFT JOIN dataset_snapshots AS dataset
          ON dataset.id = desk.dataset_snapshot_id
        WHERE desk.immutable = 1
          AND desk.dataset_snapshot_id IS NOT NULL
          AND dataset.immutable = 1
        ORDER BY desk.as_of DESC, desk.created_at DESC, desk.rowid DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        raise SnapshotNotFoundError
    return row


def _snapshot_meta(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "dataset_snapshot_id": row["dataset_snapshot_id"],
        "as_of": row["as_of"],
        "created_at": row["created_at"],
        "mode": row["mode"],
        "data_classification": row["data_classification"],
        "is_live": bool(row["is_live"]),
        "is_demo": bool(row["is_demo"]),
        "status": row["status"],
        "immutable": bool(row["immutable"]),
        "seed_revision": row["seed_revision"],
        "title": row["title"],
        "subtitle": row["subtitle"],
        "disclaimer": row["disclaimer"],
    }


def get_latest_snapshot_meta(connection: sqlite3.Connection) -> dict[str, Any] | None:
    try:
        return _snapshot_meta(_latest_snapshot(connection))
    except SnapshotNotFoundError:
        return None


def _metrics(
    connection: sqlite3.Connection,
    table: str,
    snapshot_id: str,
    *,
    symbol: str | None = None,
) -> list[dict[str, Any]]:
    where = "snapshot_id = ?"
    parameters: list[Any] = [snapshot_id]
    if symbol is not None:
        where += " AND symbol = ?"
        parameters.append(symbol)
    rows = connection.execute(
        f"""
        SELECT metric_key, label, value_json, unit, status, description
        FROM {table}
        WHERE {where}
        ORDER BY sort_order, metric_key
        """,
        parameters,
    ).fetchall()
    return [
        {
            "key": row["metric_key"],
            "label": row["label"],
            "value": _json_value(row["value_json"]),
            "unit": row["unit"],
            "status": row["status"],
            "description": row["description"],
        }
        for row in rows
    ]


def _data_sources(
    connection: sqlite3.Connection,
    snapshot_id: str,
    *,
    symbol: str | None = None,
) -> list[dict[str, Any]]:
    join = ""
    where = "ds.snapshot_id = ?"
    parameters: list[Any] = [snapshot_id]
    if symbol is not None:
        join = """
            JOIN symbol_data_sources sds
              ON sds.snapshot_id = ds.snapshot_id
             AND sds.source_key = ds.source_key
        """
        where += " AND sds.symbol = ?"
        parameters.append(symbol)
    rows = connection.execute(
        f"""
        SELECT ds.source_key, ds.name, ds.category, ds.status, ds.is_live,
               ds.coverage, ds.source_url, ds.source_record_id, ds.observed_at,
               ds.available_at, ds.ingested_at, ds.latency_seconds, ds.detail
        FROM data_sources ds
        {join}
        WHERE {where}
        ORDER BY ds.sort_order, ds.source_key
        """,
        parameters,
    ).fetchall()
    return [
        {
            "key": row["source_key"],
            "name": row["name"],
            "category": row["category"],
            "status": row["status"],
            "is_live": bool(row["is_live"]),
            "coverage": row["coverage"],
            "source_url": row["source_url"],
            "source_record_id": row["source_record_id"],
            "observed_at": row["observed_at"],
            "available_at": row["available_at"],
            "ingested_at": row["ingested_at"],
            "latency_seconds": row["latency_seconds"],
            "detail": row["detail"],
        }
        for row in rows
    ]


def _position_candidates(
    connection: sqlite3.Connection,
    snapshot_id: str,
    *,
    symbol: str | None = None,
) -> list[dict[str, Any]]:
    where = "snapshot_id = ?"
    parameters: list[Any] = [snapshot_id]
    if symbol is not None:
        where += " AND symbol = ?"
        parameters.append(symbol)
    candidates = connection.execute(
        f"""
        SELECT * FROM position_candidates
        WHERE {where}
        ORDER BY sort_order, candidate_id
        """,
        parameters,
    ).fetchall()

    result: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        legs = connection.execute(
            """
            SELECT action, quantity, instrument_type, symbol, expiry, strike,
                   option_type, bid, ask, mid, multiplier, dte, open_interest,
                   volume, implied_volatility, delta, gamma, theta, vega
            FROM position_legs
            WHERE snapshot_id = ? AND candidate_id = ?
            ORDER BY leg_order
            """,
            (snapshot_id, candidate_id),
        ).fetchall()
        points = connection.execute(
            """
            SELECT point_type, text FROM position_points
            WHERE snapshot_id = ? AND candidate_id = ?
            ORDER BY point_type, sort_order
            """,
            (snapshot_id, candidate_id),
        ).fetchall()
        blockers = connection.execute(
            """
            SELECT blocker_key, label, detail, required, resolved
            FROM position_blockers
            WHERE snapshot_id = ? AND candidate_id = ?
            ORDER BY sort_order, blocker_key
            """,
            (snapshot_id, candidate_id),
        ).fetchall()
        greeks = connection.execute(
            """
            SELECT greek_key, value, unit FROM position_greeks
            WHERE snapshot_id = ? AND candidate_id = ?
            ORDER BY greek_key
            """,
            (snapshot_id, candidate_id),
        ).fetchall()
        result.append(
            {
                "id": candidate_id,
                "symbol": candidate["symbol"],
                "name": candidate["name"],
                "side": candidate["side"],
                "structure_type": candidate["structure_type"],
                "legs": [dict(row) for row in legs],
                "target_weight": candidate["target_weight"],
                "current_weight": candidate["current_weight"],
                "delta_weight": candidate["delta_weight"],
                "allocation_basis": candidate["allocation_basis"],
                "confidence": candidate["confidence"],
                "max_loss": candidate["max_loss"],
                "max_profit": candidate["max_profit"],
                "breakeven_low": candidate["breakeven_low"],
                "breakeven_high": candidate["breakeven_high"],
                "net_debit_credit": candidate["net_debit_credit"],
                "cost_estimate": candidate["cost_estimate"],
                "cost_unit": candidate["cost_unit"],
                "horizon": candidate["horizon"],
                "status": candidate["status"],
                "actionability": candidate["actionability"],
                "market_data_complete": bool(candidate["market_data_complete"]),
                "input_completeness_scope": candidate["input_completeness_scope"],
                "source_key": candidate["source_key"],
                "observed_at": candidate["observed_at"],
                "available_at": candidate["available_at"],
                "ingested_at": candidate["ingested_at"],
                "rationale": [row["text"] for row in points if row["point_type"] == "rationale"],
                "risks": [row["text"] for row in points if row["point_type"] == "risk"],
                "blockers": [
                    {
                        "key": row["blocker_key"],
                        "label": row["label"],
                        "detail": row["detail"],
                        "required": bool(row["required"]),
                        "resolved": bool(row["resolved"]),
                    }
                    for row in blockers
                ],
                "greeks": {
                    row["greek_key"]: {"value": row["value"], "unit": row["unit"]}
                    for row in greeks
                },
            }
        )
    return result


def get_latest_desk(connection: sqlite3.Connection) -> dict[str, Any]:
    snapshot = _latest_snapshot(connection)
    snapshot_id = snapshot["id"]

    philosophy_rows = connection.execute(
        """
        SELECT section_key, title, body, principle
        FROM philosophy_sections
        WHERE snapshot_id = ?
        ORDER BY sort_order, section_key
        """,
        (snapshot_id,),
    ).fetchall()

    filter_rows = connection.execute(
        """
        SELECT filter_key, name, value_json, threshold_json, status, explanation,
               observed_at, available_at, ingested_at, source_key
        FROM regime_filters
        WHERE snapshot_id = ?
        ORDER BY sort_order, filter_key
        """,
        (snapshot_id,),
    ).fetchall()
    weight_rows = connection.execute(
        """
        SELECT weight_key, name, value, unit
        FROM regime_weights
        WHERE snapshot_id = ?
        ORDER BY sort_order, weight_key
        """,
        (snapshot_id,),
    ).fetchall()
    contribution_rows = connection.execute(
        """
        SELECT contribution_key, name, value, unit, direction, explanation
        FROM regime_contributions
        WHERE snapshot_id = ?
        ORDER BY sort_order, contribution_key
        """,
        (snapshot_id,),
    ).fetchall()
    contributions = []
    for contribution in contribution_rows:
        evidence = connection.execute(
            """
            SELECT evidence_key, label, value_json, detail, observed_at,
                   available_at, ingested_at
            FROM regime_evidence
            WHERE snapshot_id = ? AND contribution_key = ?
            ORDER BY sort_order, evidence_key
            """,
            (snapshot_id, contribution["contribution_key"]),
        ).fetchall()
        contributions.append(
            {
                "key": contribution["contribution_key"],
                "name": contribution["name"],
                "value": contribution["value"],
                "unit": contribution["unit"],
                "direction": contribution["direction"],
                "explanation": contribution["explanation"],
                "evidence": [
                    {
                        "key": row["evidence_key"],
                        "label": row["label"],
                        "value": _json_value(row["value_json"]),
                        "detail": row["detail"],
                        "observed_at": row["observed_at"],
                        "available_at": row["available_at"],
                        "ingested_at": row["ingested_at"],
                    }
                    for row in evidence
                ],
            }
        )

    recommendation_points = connection.execute(
        """
        SELECT point_type, text FROM recommendation_points
        WHERE snapshot_id = ?
        ORDER BY point_type, sort_order
        """,
        (snapshot_id,),
    ).fetchall()

    node_rows = connection.execute(
        """
        SELECT node_id, parent_node_id, node_type, label, status, summary,
               confidence, current_value, target_value, delta_value, value_unit,
               contribution, constraints_json, x, y
        FROM decision_nodes
        WHERE snapshot_id = ?
        ORDER BY sort_order, node_id
        """,
        (snapshot_id,),
    ).fetchall()
    edge_rows = connection.execute(
        """
        SELECT edge_id, from_node_id, to_node_id, relation, weight, rationale
        FROM decision_edges
        WHERE snapshot_id = ?
        ORDER BY sort_order, edge_id
        """,
        (snapshot_id,),
    ).fetchall()
    observation_rows = connection.execute(
        """
        SELECT observation_id, node_id, label, value_json, unit, status, detail,
               source_key, source_record_id, observed_at, available_at, ingested_at
        FROM decision_observations
        WHERE snapshot_id = ?
        ORDER BY sort_order, observation_id
        """,
        (snapshot_id,),
    ).fetchall()

    backtest_row = connection.execute(
        "SELECT * FROM backtests WHERE snapshot_id = ?", (snapshot_id,)
    ).fetchone()
    backtest = None
    if backtest_row is not None:
        backtest = {
            "label": backtest_row["label"],
            "status": backtest_row["status"],
            "is_available": bool(backtest_row["is_available"]),
            "summary": backtest_row["summary"],
            "methodology": backtest_row["methodology"],
            "period_start": backtest_row["period_start"],
            "period_end": backtest_row["period_end"],
            "information_cutoff_policy": backtest_row["information_cutoff_policy"],
            "metrics": _metrics(connection, "backtest_metrics", snapshot_id),
        }

    return {
        "snapshot": _snapshot_meta(snapshot),
        "philosophy": {
            "sections": [
                {
                    "key": row["section_key"],
                    "title": row["title"],
                    "body": row["body"],
                    "principle": row["principle"],
                }
                for row in philosophy_rows
            ]
        },
        "regime": {
            "label": snapshot["regime_label"],
            "confidence": snapshot["regime_confidence"],
            "as_of": snapshot["as_of"],
            "summary": snapshot["regime_summary"],
            "filters": [
                {
                    "key": row["filter_key"],
                    "name": row["name"],
                    "value": _json_value(row["value_json"]),
                    "threshold": _json_value(row["threshold_json"]),
                    "status": row["status"],
                    "explanation": row["explanation"],
                    "source_key": row["source_key"],
                    "observed_at": row["observed_at"],
                    "available_at": row["available_at"],
                    "ingested_at": row["ingested_at"],
                }
                for row in filter_rows
            ],
            "weights": [
                {
                    "key": row["weight_key"],
                    "name": row["name"],
                    "value": row["value"],
                    "unit": row["unit"],
                }
                for row in weight_rows
            ],
            "contributions": contributions,
        },
        "recommendation": {
            "posture": snapshot["recommendation_posture"],
            "summary": snapshot["recommendation_summary"],
            "confidence": snapshot["recommendation_confidence"],
            "current_net_exposure": snapshot["current_net_exposure"],
            "current_gross_exposure": snapshot["current_gross_exposure"],
            "target_net_exposure": snapshot["target_net_exposure"],
            "target_gross_exposure": snapshot["target_gross_exposure"],
            "delta_net_exposure": snapshot["delta_net_exposure"],
            "delta_gross_exposure": snapshot["delta_gross_exposure"],
            "change_summary": snapshot["change_summary"],
            "rationale": [row["text"] for row in recommendation_points if row["point_type"] == "rationale"],
            "invalidation": [row["text"] for row in recommendation_points if row["point_type"] == "invalidation"],
            "next_review_at": snapshot["next_review_at"],
        },
        "decision_graph": {
            "nodes": [
                {
                    "id": row["node_id"],
                    "parent_id": row["parent_node_id"],
                    "type": row["node_type"],
                    "label": row["label"],
                    "status": row["status"],
                    "summary": row["summary"],
                    "confidence": row["confidence"],
                    "current_value": row["current_value"],
                    "target_value": row["target_value"],
                    "delta_value": row["delta_value"],
                    "value_unit": row["value_unit"],
                    "contribution": row["contribution"],
                    "constraints": _json_value(row["constraints_json"]),
                    "x": row["x"],
                    "y": row["y"],
                }
                for row in node_rows
            ],
            "edges": [
                {
                    "id": row["edge_id"],
                    "from": row["from_node_id"],
                    "to": row["to_node_id"],
                    "relation": row["relation"],
                    "weight": row["weight"],
                    "rationale": row["rationale"],
                }
                for row in edge_rows
            ],
            "observations": [
                {
                    "id": row["observation_id"],
                    "node_id": row["node_id"],
                    "label": row["label"],
                    "value": _json_value(row["value_json"]),
                    "unit": row["unit"],
                    "status": row["status"],
                    "detail": row["detail"],
                    "source_key": row["source_key"],
                    "source_record_id": row["source_record_id"],
                    "observed_at": row["observed_at"],
                    "available_at": row["available_at"],
                    "ingested_at": row["ingested_at"],
                }
                for row in observation_rows
            ],
        },
        "metrics": _metrics(connection, "desk_metrics", snapshot_id),
        "backtest": backtest,
        "position_candidates": _position_candidates(connection, snapshot_id),
        "data_sources": _data_sources(connection, snapshot_id),
    }


def get_latest_cross_section(connection: sqlite3.Connection) -> dict[str, Any]:
    snapshot = _latest_snapshot(connection)
    snapshot_id = snapshot["id"]
    dimensions = connection.execute(
        """
        SELECT factor_key, label, unit, description, weight
        FROM factor_dimensions
        WHERE snapshot_id = ?
        ORDER BY sort_order, factor_key
        """,
        (snapshot_id,),
    ).fetchall()
    row_records = connection.execute(
        """
        SELECT csr.symbol, s.security_id, s.name, s.sector, csr.composite_score,
               csr.rank, csr.status, csr.summary
        FROM cross_section_rows csr
        JOIN symbols s ON s.snapshot_id = csr.snapshot_id AND s.symbol = csr.symbol
        WHERE csr.snapshot_id = ?
        ORDER BY csr.rank IS NULL, csr.rank, csr.symbol
        """,
        (snapshot_id,),
    ).fetchall()
    rows: list[dict[str, Any]] = []
    factor_keys = [row["factor_key"] for row in dimensions]
    for record in row_records:
        factor_rows = connection.execute(
            """
            SELECT factor_key, value, quality_status, source_key, source_record_id,
                   observed_at, available_at, ingested_at
            FROM factor_values
            WHERE snapshot_id = ? AND symbol = ?
            """,
            (snapshot_id, record["symbol"]),
        ).fetchall()
        by_key = {row["factor_key"]: row for row in factor_rows}
        rows.append(
            {
                "security_id": record["security_id"],
                "symbol": record["symbol"],
                "name": record["name"],
                "sector": record["sector"],
                "values": {
                    key: by_key[key]["value"] if key in by_key else None
                    for key in factor_keys
                },
                "quality": {
                    key: by_key[key]["quality_status"] if key in by_key else "not_recorded"
                    for key in factor_keys
                },
                "provenance": {
                    key: (
                        {
                            "source_key": by_key[key]["source_key"],
                            "source_record_id": by_key[key]["source_record_id"],
                            "observed_at": by_key[key]["observed_at"],
                            "available_at": by_key[key]["available_at"],
                            "ingested_at": by_key[key]["ingested_at"],
                        }
                        if key in by_key
                        else None
                    )
                    for key in factor_keys
                },
                "composite_score": record["composite_score"],
                "rank": record["rank"],
                "status": record["status"],
                "summary": record["summary"],
            }
        )
    legend_rows = connection.execute(
        """
        SELECT legend_key, label, description FROM cross_section_legend
        WHERE snapshot_id = ? ORDER BY sort_order, legend_key
        """,
        (snapshot_id,),
    ).fetchall()
    return {
        "snapshot": _snapshot_meta(snapshot),
        "dimensions": {
            "columns": [
                {
                    "key": row["factor_key"],
                    "label": row["label"],
                    "unit": row["unit"],
                    "description": row["description"],
                    "weight": row["weight"],
                }
                for row in dimensions
            ]
        },
        "rows": rows,
        "legend": [dict(row) for row in legend_rows],
    }


def list_latest_symbols(connection: sqlite3.Connection) -> dict[str, Any]:
    try:
        snapshot = _latest_snapshot(connection)
    except SnapshotNotFoundError:
        return {"snapshot": None, "symbols": []}
    snapshot_id = snapshot["id"]
    rows = connection.execute(
        """
        SELECT s.security_id, s.symbol, s.name, s.asset_type, s.sector, s.exchange,
               s.currency, s.status, s.summary, s.last_price, s.price_as_of,
               s.composite_score, s.rank, s.freshness_status, s.freshness_as_of,
               COUNT(pc.candidate_id) AS candidate_count
        FROM symbols s
        LEFT JOIN position_candidates pc
          ON pc.snapshot_id = s.snapshot_id AND pc.symbol = s.symbol
        WHERE s.snapshot_id = ?
        GROUP BY s.snapshot_id, s.symbol
        ORDER BY s.rank IS NULL, s.rank, s.symbol
        """,
        (snapshot_id,),
    ).fetchall()
    return {
        "snapshot": _snapshot_meta(snapshot),
        "symbols": [
            {
                **dict(row),
                "candidate_count": int(row["candidate_count"]),
            }
            for row in rows
        ],
    }


def get_latest_symbol(connection: sqlite3.Connection, symbol: str) -> dict[str, Any]:
    snapshot = _latest_snapshot(connection)
    snapshot_id = snapshot["id"]
    normalized_symbol = symbol.strip().upper()
    row = connection.execute(
        "SELECT * FROM symbols WHERE snapshot_id = ? AND symbol = ?",
        (snapshot_id, normalized_symbol),
    ).fetchone()
    if row is None:
        raise SymbolNotFoundError(normalized_symbol)

    hierarchy = connection.execute(
        """
        SELECT hierarchy.level, hierarchy.label, hierarchy.node_id,
               hierarchy.current_value, hierarchy.target_value,
               hierarchy.delta_value, hierarchy.value_unit,
               hierarchy.contribution, hierarchy.constraints_json,
               node.parent_node_id, parent.label AS parent_label
        FROM symbol_hierarchy AS hierarchy
        LEFT JOIN decision_nodes AS node
          ON node.snapshot_id = hierarchy.snapshot_id
         AND node.node_id = hierarchy.node_id
        LEFT JOIN decision_nodes AS parent
          ON parent.snapshot_id = node.snapshot_id
         AND parent.node_id = node.parent_node_id
        WHERE hierarchy.snapshot_id = ? AND hierarchy.symbol = ?
        ORDER BY hierarchy.step_order
        """,
        (snapshot_id, normalized_symbol),
    ).fetchall()
    incoming_edges = connection.execute(
        """
        SELECT edge.to_node_id, edge.from_node_id,
               source.label AS from_label, edge.relation,
               edge.weight, edge.rationale
        FROM decision_edges AS edge
        LEFT JOIN decision_nodes AS source
          ON source.snapshot_id = edge.snapshot_id
         AND source.node_id = edge.from_node_id
        WHERE edge.snapshot_id = ?
        ORDER BY edge.sort_order, edge.edge_id
        """,
        (snapshot_id,),
    ).fetchall()
    incoming_by_node: dict[str, list[dict[str, Any]]] = {}
    for edge in incoming_edges:
        incoming_by_node.setdefault(edge["to_node_id"], []).append(
            {
                "from_node_id": edge["from_node_id"],
                "from_label": edge["from_label"],
                "relation": edge["relation"],
                "weight": edge["weight"],
                "rationale": edge["rationale"],
            }
        )
    recommendation = connection.execute(
        """
        SELECT posture, summary, confidence, current_weight, target_weight,
               delta_weight, next_review_at, actionability
        FROM symbol_recommendations
        WHERE snapshot_id = ? AND symbol = ?
        """,
        (snapshot_id, normalized_symbol),
    ).fetchone()
    recommendation_points = connection.execute(
        """
        SELECT point_type, text FROM symbol_recommendation_points
        WHERE snapshot_id = ? AND symbol = ?
        ORDER BY point_type, sort_order
        """,
        (snapshot_id, normalized_symbol),
    ).fetchall()
    bars = connection.execute(
        """
        SELECT time, open, high, low, close, volume, source_key, observed_at,
               available_at, ingested_at
        FROM symbol_bars
        WHERE dataset_snapshot_id = ? AND security_id = ?
        ORDER BY time
        """,
        (snapshot["dataset_snapshot_id"], row["security_id"]),
    ).fetchall()
    events = connection.execute(
        """
        SELECT event_id, time, event_type, event_status, label, price, detail,
               source_key, observed_at,
               available_at, ingested_at
        FROM symbol_events
        WHERE dataset_snapshot_id = ? AND security_id = ?
        ORDER BY time, event_id
        """,
        (snapshot["dataset_snapshot_id"], row["security_id"]),
    ).fetchall()
    signal = connection.execute(
        """
        SELECT status, direction, strength, label, rationale, source_node_id,
               observed_at, available_at, ingested_at
        FROM symbol_signals
        WHERE snapshot_id = ? AND symbol = ?
        """,
        (snapshot_id, normalized_symbol),
    ).fetchone()

    recommendation_payload = None
    if recommendation is not None:
        recommendation_payload = {
            **dict(recommendation),
            "rationale": [item["text"] for item in recommendation_points if item["point_type"] == "rationale"],
            "invalidation": [item["text"] for item in recommendation_points if item["point_type"] == "invalidation"],
        }

    return {
        "snapshot": _snapshot_meta(snapshot),
        "security_id": row["security_id"],
        "symbol": row["symbol"],
        "name": row["name"],
        "asset_type": row["asset_type"],
        "sector": row["sector"],
        "exchange": row["exchange"],
        "currency": row["currency"],
        "status": row["status"],
        "summary": row["summary"],
        "last_price": row["last_price"],
        "price_as_of": row["price_as_of"],
        "composite_score": row["composite_score"],
        "rank": row["rank"],
        "freshness": {
            "status": row["freshness_status"],
            "as_of": row["freshness_as_of"],
            "summary": row["freshness_summary"],
        },
        "hierarchy_trace": [
            {
                "level": item["level"],
                "label": item["label"],
                "node_id": item["node_id"],
                "parent_node_id": item["parent_node_id"],
                "parent_label": item["parent_label"],
                "incoming_edges": incoming_by_node.get(item["node_id"], []),
                "current_value": item["current_value"],
                "target_value": item["target_value"],
                "delta_value": item["delta_value"],
                "value_unit": item["value_unit"],
                "contribution": item["contribution"],
                "constraints": _json_value(item["constraints_json"]),
            }
            for item in hierarchy
        ],
        "recommendation": recommendation_payload,
        "current_signal": dict(signal) if signal is not None else None,
        "bars": [dict(item) for item in bars],
        "events": [
            {
                "id": item["event_id"],
                "time": item["time"],
                "type": item["event_type"],
                "status": item["event_status"],
                "label": item["label"],
                "price": item["price"],
                "detail": item["detail"],
                "source_key": item["source_key"],
                "observed_at": item["observed_at"],
                "available_at": item["available_at"],
                "ingested_at": item["ingested_at"],
            }
            for item in events
        ],
        "metrics": _metrics(connection, "symbol_metrics", snapshot_id, symbol=normalized_symbol),
        "position_candidates": _position_candidates(connection, snapshot_id, symbol=normalized_symbol),
        "data_sources": _data_sources(connection, snapshot_id, symbol=normalized_symbol),
    }
