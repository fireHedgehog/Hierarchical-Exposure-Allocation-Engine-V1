from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.database import connect, initialize_database
from backend.main import create_app
from backend.seed import DEMO_DATASET_ID, DEMO_SNAPSHOT_ID, seed_demo


@pytest.fixture
def empty_database(tmp_path: Path) -> Path:
    return tmp_path / "empty" / "desk.db"


@pytest.fixture
def seeded_database(tmp_path: Path) -> Path:
    path = tmp_path / "seeded" / "desk.db"
    _, created = seed_demo(path)
    assert created is True
    return path


@pytest.fixture
def empty_client(empty_database: Path, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(empty_database, frontend_dist=tmp_path / "missing-dist")
    with TestClient(app) as client:
        yield client


@pytest.fixture
def seeded_client(seeded_database: Path, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(seeded_database, frontend_dist=tmp_path / "missing-dist")
    with TestClient(app) as client:
        yield client


def test_empty_database_boots_without_inventing_a_snapshot(empty_client: TestClient) -> None:
    health = empty_client.get("/api/health")
    assert health.status_code == 200
    assert health.headers["cache-control"] == "no-store"
    assert health.json()["status"] == "ok"
    assert health.json()["data_status"] == "empty"
    assert health.json()["snapshot"] is None
    assert health.json()["seed_policy"] == "explicit_opt_in_only"

    assert empty_client.get("/api/v1/desk/latest").status_code == 404
    assert empty_client.get("/api/v1/cross-section/latest").status_code == 404
    assert empty_client.get("/api/v1/symbols").json() == {
        "snapshot": None,
        "symbols": [],
        "scope": "watchlist",
    }
    assert empty_client.get("/api/v1/symbols/SPY").status_code == 404


def test_desk_contract_is_structured_and_explicitly_synthetic(
    seeded_client: TestClient,
) -> None:
    response = seeded_client.get("/api/v1/desk/latest")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "snapshot",
        "philosophy",
        "regime",
        "recommendation",
        "decision_graph",
        "metrics",
        "backtest",
        "position_candidates",
        "data_sources",
    }
    assert payload["snapshot"]["mode"] == "demo"
    assert payload["snapshot"]["data_classification"] == "synthetic"
    assert payload["snapshot"]["is_live"] is False
    assert payload["snapshot"]["is_demo"] is True
    assert payload["snapshot"]["immutable"] is True
    assert "DEMO / SYNTHETIC / NOT LIVE" in payload["snapshot"]["disclaimer"]

    sections = payload["philosophy"]["sections"]
    assert sections
    assert set(sections[0]) == {"key", "title", "body", "principle"}

    regime = payload["regime"]
    assert isinstance(regime["filters"], list)
    assert isinstance(regime["weights"], list)
    assert isinstance(regime["contributions"][0]["evidence"], list)
    assert {
        "observed_at",
        "available_at",
        "ingested_at",
    } <= set(regime["filters"][0])

    graph = payload["decision_graph"]
    assert isinstance(graph["observations"][0], dict)
    assert {"id", "node_id", "value", "status", "observed_at"} <= set(
        graph["observations"][0]
    )
    assert {"id", "parent_id", "type", "summary", "constraints"} <= set(
        graph["nodes"][0]
    )
    assert {"id", "from", "to", "relation", "rationale"} <= set(graph["edges"][0])
    overlay_edges = [
        edge
        for edge in graph["edges"]
        if edge["from"] == "convex_family"
        and edge["relation"] == "funds_defined_risk_overlay"
    ]
    assert {edge["to"] for edge in overlay_edges} == {"iwm_spread", "tlt_spread"}

    recommendation = payload["recommendation"]
    assert recommendation["current_net_exposure"] == 0.61
    assert recommendation["target_net_exposure"] == 0.55
    assert recommendation["delta_net_exposure"] == -0.06
    assert recommendation["rationale"]
    assert recommendation["invalidation"]

    live_feed_metric = next(
        metric for metric in payload["metrics"] if metric["key"] == "live_feeds_connected"
    )
    assert live_feed_metric["value"] == 0
    assert isinstance(live_feed_metric["value"], int)
    assert payload["backtest"]["is_available"] is False
    assert all(metric["value"] is None for metric in payload["backtest"]["metrics"])
    assert all(isinstance(source["coverage"], str) for source in payload["data_sources"])


def test_position_contract_preserves_nulls_false_and_blocker_objects(
    seeded_client: TestClient,
) -> None:
    candidates = seeded_client.get("/api/v1/desk/latest").json()[
        "position_candidates"
    ]
    candidate = next(item for item in candidates if item["id"] == "iwm-call-spread")
    assert candidate["actionability"] == "blocked"
    assert candidate["market_data_complete"] is False
    assert candidate["allocation_basis"] == "premium_budget"
    assert candidate["input_completeness_scope"] == "live_market_data"
    assert candidate["max_loss"] is None
    assert candidate["max_profit"] is None
    assert candidate["breakeven_low"] is None
    assert candidate["breakeven_high"] is None
    assert candidate["net_debit_credit"] is None
    assert set(candidate["blockers"][0]) == {
        "key",
        "label",
        "detail",
        "required",
        "resolved",
    }
    assert candidate["blockers"][0]["required"] is True
    assert candidate["blockers"][0]["resolved"] is False
    assert candidate["greeks"]["delta"] == {
        "value": None,
        "unit": "per_contract",
    }
    assert {
        "bid",
        "ask",
        "mid",
        "multiplier",
        "dte",
        "open_interest",
        "volume",
        "implied_volatility",
        "delta",
        "gamma",
        "theta",
        "vega",
    } <= set(candidate["legs"][0])
    assert candidate["legs"][0]["bid"] is None

    simulation = next(item for item in candidates if item["id"] == "tlt-call-spread")
    assert simulation["status"] == "synthetic_simulation_ready"
    assert simulation["actionability"] == "simulation_ready"
    assert simulation["market_data_complete"] is True
    assert simulation["allocation_basis"] == "premium_budget"
    assert simulation["input_completeness_scope"] == "synthetic_simulation_inputs"
    assert simulation["blockers"] == []
    assert simulation["max_loss"] == 285.0
    assert simulation["max_profit"] == 715.0
    assert simulation["net_debit_credit"] == 285.0
    assert simulation["legs"][0]["expiry"] == "2026-12-18"
    assert simulation["legs"][0]["option_type"] == "call"
    assert simulation["legs"][0]["ask"] == 5.8
    assert simulation["greeks"]["delta"] == {
        "value": 23.0,
        "unit": "delta_equivalent_shares",
    }
    assert simulation["source_key"] == "synthetic_options_fixture"
    assert simulation["available_at"] is not None


def test_cross_section_contract_includes_nullable_values_and_provenance(
    seeded_client: TestClient,
) -> None:
    response = seeded_client.get("/api/v1/cross-section/latest")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["legend"], list)
    assert set(payload["legend"][0]) == {"legend_key", "label", "description"}
    assert all(
        {"key", "label", "unit", "description", "weight"} == set(column)
        for column in payload["dimensions"]["columns"]
    )
    tlt = next(row for row in payload["rows"] if row["symbol"] == "TLT")
    assert tlt["values"]["valuation"] is None
    assert tlt["values"]["quality"] is None
    assert tlt["quality"]["valuation"] == "unavailable"
    assert tlt["provenance"]["valuation"]["observed_at"] is None
    assert tlt["values"]["momentum"] == 0.37
    assert tlt["provenance"]["momentum"]["available_at"] is not None


def test_symbol_list_and_detail_contract(seeded_client: TestClient) -> None:
    # scope=all: this test is about the general listing/detail contract shape,
    # not the watchlist dashboard filter -- the seed fixture's symbols (e.g.
    # IWM) aren't in staging_symbols' curated watchlist set.
    listing = seeded_client.get("/api/v1/symbols?scope=all")
    assert listing.status_code == 200
    assert len(listing.json()["symbols"]) == 6
    assert listing.json()["symbols"][0]["security_id"].startswith("us-etf-")

    response = seeded_client.get("/api/v1/symbols/iwm")
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "IWM"
    assert len(payload["hierarchy_trace"]) == 7
    assert [step["level"] for step in payload["hierarchy_trace"]] == [
        "desk",
        "state",
        "risk_budget",
        "allocation_family",
        "exposure",
        "funding_family",
        "instrument",
    ]
    assert {
        "level",
        "node_id",
        "parent_node_id",
        "parent_label",
        "incoming_edges",
        "current_value",
        "target_value",
        "delta_value",
        "value_unit",
        "constraints",
    } <= set(payload["hierarchy_trace"][0])
    instrument = payload["hierarchy_trace"][-1]
    assert instrument["parent_node_id"] == "small_cap"
    assert {edge["from_node_id"] for edge in instrument["incoming_edges"]} == {
        "small_cap",
        "convex_family",
    }
    assert payload["recommendation"]["current_weight"] == 0.06
    assert payload["recommendation"]["target_weight"] == 0.07
    assert payload["recommendation"]["delta_weight"] == 0.01
    assert payload["freshness"]["status"] == "synthetic_fixture"
    assert len(payload["bars"]) == 8
    assert {"time", "open", "high", "low", "close", "volume"} <= set(
        payload["bars"][0]
    )
    assert {"observed_at", "available_at", "ingested_at"} <= set(payload["bars"][0])
    assert {"time", "type", "label", "price", "detail"} <= set(payload["events"][0])
    assert payload["position_candidates"][0]["blockers"]
    assert payload["data_sources"]

    missing = seeded_client.get("/api/v1/symbols/NOT-A-SYMBOL")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "symbol_not_found"


def test_api_exposes_no_mutating_routes(seeded_client: TestClient) -> None:
    assert seeded_client.post("/api/v1/desk/latest", json={}).status_code == 405
    assert seeded_client.put("/api/v1/symbols/SPY", json={}).status_code == 405
    assert seeded_client.delete("/api/v1/symbols/SPY").status_code == 405


def test_frontend_dist_is_served_with_spa_fallback(
    empty_database: Path, tmp_path: Path
) -> None:
    dist = tmp_path / "frontend-dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>HEAE shell</html>", encoding="utf-8")
    (dist / "asset.txt").write_text("asset", encoding="utf-8")
    app = create_app(empty_database, frontend_dist=dist)
    with TestClient(app) as client:
        assert "HEAE shell" in client.get("/desk/SPY").text
        asset = client.get("/asset.txt")
        assert asset.text == "asset"
        assert asset.headers.get("cache-control") != "no-store"
        missing_api = client.get("/api/does-not-exist")
        assert missing_api.status_code == 404
        assert missing_api.headers["cache-control"] == "no-store"


def test_seed_is_idempotent(seeded_database: Path) -> None:
    _, created = seed_demo(seeded_database)
    assert created is False
    with connect(seeded_database, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM desk_snapshots").fetchone()[0] == 1


def _assert_integrity_error(connection: sqlite3.Connection, sql: str, values: tuple) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(sql, values)
    connection.rollback()


def test_published_desk_and_dataset_children_are_immutable(seeded_database: Path) -> None:
    with connect(seeded_database) as connection:
        _assert_integrity_error(
            connection,
            "UPDATE philosophy_sections SET body = ? WHERE snapshot_id = ?",
            ("mutated", DEMO_SNAPSHOT_ID),
        )
        _assert_integrity_error(
            connection,
            "DELETE FROM factor_values WHERE snapshot_id = ? AND symbol = ?",
            (DEMO_SNAPSHOT_ID, "SPY"),
        )
        _assert_integrity_error(
            connection,
            """
            INSERT INTO desk_metrics (
                snapshot_id, metric_key, label, value_json, sort_order
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (DEMO_SNAPSHOT_ID, "late", "Late insert", "1", 999),
        )
        _assert_integrity_error(
            connection,
            "UPDATE symbol_bars SET close = ? WHERE dataset_snapshot_id = ?",
            (1.0, DEMO_DATASET_ID),
        )
        _assert_integrity_error(
            connection,
            "DELETE FROM symbol_events WHERE dataset_snapshot_id = ?",
            (DEMO_DATASET_ID,),
        )
        _assert_integrity_error(
            connection,
            "UPDATE desk_snapshots SET title = ? WHERE id = ?",
            ("mutated", DEMO_SNAPSHOT_ID),
        )


def test_schema_allows_non_demo_snapshots(empty_database: Path) -> None:
    initialize_database(empty_database)
    with connect(empty_database) as connection:
        connection.execute(
            """
            INSERT INTO dataset_snapshots (
                id, as_of, created_at, mode, data_classification, is_live,
                is_demo, status, immutable, source_manifest_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("live-data-1", "2026-08-24T00:00:00Z", "2026-08-24T00:01:00Z", "live", "real", 1, 0, "ready", 0, "{}"),
        )
        connection.execute(
            """
            INSERT INTO desk_snapshots (
                id, dataset_snapshot_id, as_of, created_at, mode,
                data_classification, is_live, is_demo, status, immutable,
                seed_revision, title, subtitle, disclaimer, regime_label,
                regime_summary, recommendation_posture,
                recommendation_summary, change_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "live-desk-1",
                "live-data-1",
                "2026-08-24T00:00:00Z",
                "2026-08-24T00:01:00Z",
                "live",
                "real",
                1,
                0,
                "ready",
                0,
                "live-ingestion-v1",
                "Live desk",
                "Non-demo schema proof",
                "Operator-provided disclosure",
                "Unclassified",
                "No state conclusion published.",
                "observe",
                "No recommendation published.",
                "No change published.",
            ),
        )
        row = connection.execute(
            "SELECT mode, data_classification, is_live, is_demo FROM desk_snapshots"
        ).fetchone()
        assert tuple(row) == ("live", "real", 1, 0)
