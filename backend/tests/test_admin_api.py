from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.database import connect, initialize_database
from backend.main import create_app
from backend.providers import VerificationResult
from backend.providers.fred import FredObservation, FredV2Verifier
from backend.providers.yahoo import PriceBar
from backend.secrets import (
    KeyringEnvironmentSecretStore,
    SecretStoreUnavailable,
    SecretValue,
)
from backend.seed import DEMO_DATASET_ID, DEMO_SNAPSHOT_ID, seed_demo


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
ORIGIN = "http://127.0.0.1:8000"


@dataclass
class MemorySecretStore:
    values: dict[str, SecretValue] = field(default_factory=dict)
    set_calls: list[tuple[str, str]] = field(default_factory=list)
    delete_calls: list[str] = field(default_factory=list)
    fail_set: bool = False
    fail_delete: bool = False

    def get(self, credential_name: str, environment_variable: str | None) -> SecretValue | None:
        return self.values.get(credential_name)

    def set(self, credential_name: str, secret: str) -> None:
        self.set_calls.append((credential_name, secret))
        if self.fail_set:
            raise SecretStoreUnavailable("Injected credential-store write failure.")
        self.values[credential_name] = SecretValue(secret, "keyring", True)

    def delete(self, credential_name: str) -> bool:
        self.delete_calls.append(credential_name)
        if self.fail_delete:
            raise SecretStoreUnavailable("Injected credential-store delete failure.")
        return self.values.pop(credential_name, None) is not None


@dataclass
class FakeVerifier:
    result: VerificationResult = VerificationResult(
        status="healthy",
        message="Provider accepted the credential.",
        http_status=200,
        latency_ms=12,
    )
    calls: list[str] = field(default_factory=list)

    def verify(self, secret: str) -> VerificationResult:
        self.calls.append(secret)
        return self.result


def make_fred_fetcher(
    values: dict[str, tuple[float, float]] | None = None,
):
    """Fake FredFetcher: two synthetic observations (year-ago, latest) per
    series, dated relative to the requested window so freshness/staleness
    checks pass regardless of which `now` a given test uses. No real network
    call is ever made."""

    series_values = values or {
        "INDPRO": (100.0, 102.0),
        "CPIAUCSL": (300.0, 306.0),
        "PPIACO": (250.0, 254.0),
        "PCEPILFE": (120.0, 122.4),
        "PAYEMS": (158000.0, 159200.0),
        "NFCI": (0.1, -0.2),
        "VIXCLS": (22.0, 16.0),
        "DGS10": (4.3, 4.1),
    }
    calls: list[tuple[Any, ...]] = []

    def fetcher(
        secret: str,
        series_id: str,
        *,
        observation_start: str,
        observation_end: str,
        realtime_start: str,
        realtime_end: str,
    ) -> list[FredObservation]:
        calls.append((secret, series_id, observation_start, observation_end))
        year_ago_value, latest_value = series_values[series_id]
        start = date.fromisoformat(observation_start)
        end = date.fromisoformat(observation_end)
        total_days = (end - start).days or 1
        # A real, if synthetic, linear trend across the whole requested window
        # (not just two points): naive-v2's surprise scoring needs several
        # trailing observations per series to compute a real trailing-mean
        # expectation, not a fixed target. The slope is fixed so the point
        # exactly one year before `end` lands on `year_ago_value` and the
        # last point lands on `latest_value`, preserving every existing
        # test's YoY-based scenario configuration.
        slope_per_day = (latest_value - year_ago_value) / 365.0
        point_count = max(65, min(140, total_days // 25))
        step_days = total_days / (point_count - 1) if point_count > 1 else total_days
        observations = []
        for index in range(point_count):
            offset_days = round(index * step_days)
            observation_date = (start + timedelta(days=offset_days)).isoformat()
            days_before_end = total_days - offset_days
            value = latest_value - slope_per_day * days_before_end
            observations.append(
                FredObservation(series_id, observation_date, value, realtime_start, realtime_end, "lin")
            )
        # Guarantee the exact configured endpoints are present regardless of
        # step-size rounding, since several tests assert on them directly.
        year_ago_date = (end - timedelta(days=365)).isoformat()
        observations.append(
            FredObservation(series_id, year_ago_date, year_ago_value, realtime_start, realtime_end, "lin")
        )
        observations.append(
            FredObservation(series_id, observation_end, latest_value, realtime_start, realtime_end, "lin")
        )
        deduped = {observation.observation_date: observation for observation in observations}
        return [deduped[key] for key in sorted(deduped)]

    fetcher.calls = calls  # type: ignore[attr-defined]
    return fetcher


def make_price_fetcher(as_of: date, *, count: int = 260):
    """Fake PriceFetcher: `count` synthetic daily bars per symbol, ending
    exactly on `as_of` so freshness checks pass regardless of which `now` a
    test uses, with a small symbol-dependent drift so cross-sectional ranks
    aren't all tied. No real network call is ever made."""

    calls: list[tuple[str, str | None]] = []

    def fetcher(symbol: str, *, range_: str = "1y", start_date: str | None = None) -> list[PriceBar]:
        calls.append((symbol, start_date or range_))
        seed = sum(ord(character) for character in symbol) % 11
        drift = 0.0003 * (seed - 5)
        price = 50.0 + seed * 10.0
        dates = [as_of - timedelta(days=offset) for offset in range(count - 1, -1, -1)]
        bars = []
        for bar_date in dates:
            price = max(1.0, price * (1 + drift))
            bars.append(PriceBar(symbol, bar_date.isoformat(), price, price, price, price, 1_000_000.0))
        return bars

    fetcher.calls = calls  # type: ignore[attr-defined]
    return fetcher


@pytest.fixture
def admin_context(tmp_path: Path):
    database = tmp_path / "desk.db"
    seed_demo(database)
    secret_store = MemorySecretStore()
    verifier = FakeVerifier()
    app = create_app(
        database,
        frontend_dist=tmp_path / "missing-dist",
        secret_store=secret_store,
        provider_verifiers={"fred_v2": verifier},
        fred_observation_fetcher=make_fred_fetcher(),
        price_fetcher=make_price_fetcher(NOW.date()),
        now=lambda: NOW,
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52000),
    ) as client:
        yield database, client, secret_store, verifier


def operator_headers(action: str, *, origin: str = ORIGIN) -> dict[str, str]:
    return {"Origin": origin, "X-Operator-Action": action}


def test_empty_v6_database_has_operator_and_readiness_catalog_but_no_decision_snapshot(
    tmp_path: Path,
) -> None:
    database = initialize_database(tmp_path / "empty.db")
    store = MemorySecretStore()
    app = create_app(
        database,
        frontend_dist=tmp_path / "missing",
        secret_store=store,
        provider_verifiers={"fred_v2": FakeVerifier()},
        now=lambda: NOW,
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52000),
    ) as client:
        assert client.get("/api/health").json()["schema_version"] == "16"
        assert client.get("/api/v1/desk/latest").status_code == 404
        payload = client.get("/api/v1/admin/providers").json()
        providers = payload["providers"]
        assert [provider["key"] for provider in providers] == ["fred"]
        assert providers[0]["credential"]["configured"] is False
        assert providers[0]["credential"]["source"] is None
        assert providers[0]["credential"]["cooldown_seconds"] == 900
        assert providers[0]["credential"]["verification_ttl_seconds"] == 31536000
        roadmap = payload["roadmap"]
        assert roadmap["summary"] == {
            "planned_accounts": 4,
            "supported_accounts": 1,
            "verified_accounts": 0,
            "registrations_needed_now": 1,
            "verifications_needed_now": 0,
            "future_accounts_planned": 3,
            "capabilities_total": 5,
            "capabilities_ingestion_ready": 0,
        }
        assert [account["key"] for account in roadmap["accounts"]] == [
            "fred",
            "intrinio",
            "benzinga",
            "trading_economics",
        ]
        assert roadmap["accounts"][0]["access_status"] == "not_configured"
        assert all(
            account["registration_available"] is False
            for account in roadmap["accounts"][1:]
        )
        assert [capability["key"] for capability in roadmap["capabilities"]] == [
            "macro_actuals_vintages",
            "macro_consensus_expectations",
            "equity_reference_events",
            "equity_market_history",
            "options_reference_history",
        ]
        assert "Register the FRED / ALFRED key" in roadmap["next_action"]
        pipeline = client.get("/api/v1/admin/pipeline").json()
        assert pipeline["definition"]["manual_only"] is True
        assert pipeline["definition"]["stages"][0]["implemented"] is True
        assert pipeline["latest_run"] is None

        readiness = client.get("/api/v1/admin/overview").json()["readiness"]
        assert readiness["summary"] == {
            "milestones_total": 5,
            "milestones_passed": 0,
            "gates_total": 15,
            "gates_passed": 0,
            "current_gate_key": "fred_provider_access",
            "current_action": "Register or reverify the FRED key on the Credentials page.",
            "target_route": "/operations/credentials",
        }
        assert [gate["key"] for gate in readiness["gates"]] == [
            "fred_provider_access",
            "macro_pit_ingestion",
            "macro_validation_seal",
            "real_regime_snapshot",
            "versioned_security_universe",
            "real_market_history",
            "cross_sectional_selection",
            "symbol_time_series_confirmation",
            "portfolio_risk_allocation",
            "cash_long_short_expression",
            "options_expression",
            "walk_forward_evidence",
            "repeated_shadow_recovery",
            "scheduling",
            "broker_execution_boundary",
        ]
        gates = {gate["key"]: gate for gate in readiness["gates"]}
        assert gates["fred_provider_access"]["status"] == "action_required"
        assert gates["macro_pit_ingestion"]["status"] == "blocked"
        assert gates["macro_pit_ingestion"]["blocked_by"] == [
            "fred_provider_access"
        ]
        assert gates["scheduling"]["status"] == "deferred"
        assert gates["broker_execution_boundary"]["status"] == "deferred"
        universe_criterion = gates["versioned_security_universe"][
            "acceptance_criterion"
        ]
        assert "DIA" in universe_criterion
        assert "IBIT" in universe_criterion
        assert "stable exposure, research-reference, and security IDs" in universe_criterion
        assert "point-in-time membership" in universe_criterion
        assert "BTC/USD reference" in universe_criterion
        assert "actual availability date" in universe_criterion
        assert "pre-listing IBIT history or trades" in universe_criterion

    with connect(database, read_only=True) as connection:
        readiness_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(readiness_gates)"
            ).fetchall()
        }
        assert "status" not in readiness_columns
        assert "completed" not in readiness_columns
        assert connection.execute(
            "SELECT COUNT(*) FROM readiness_gate_dependencies"
        ).fetchone()[0] == 14


def test_real_pipeline_run_persists_backtest_events_and_metrics_per_symbol(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    _, client, _, _ = admin_context
    client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": "backtest-wiring-test"},
        headers=operator_headers("credential.write"),
    )
    client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    )
    run = client.post(
        "/api/v1/admin/pipeline/runs",
        json={"dry_run": False},
        headers=operator_headers("pipeline.run"),
    ).json()["run"]
    factor = next(stage for stage in run["stages"] if stage["key"] == "factor_engine")
    assert factor["status"] == "completed"

    symbols = client.get("/api/v1/symbols").json()["symbols"]
    assert len(symbols) == 22
    top = next(item for item in symbols if item["rank"] == 1)

    detail = client.get(f"/api/v1/symbols/{top['symbol']}").json()
    metric_keys = {metric["key"] for metric in detail["metrics"]}
    assert {"total_return", "buy_hold_return", "trade_count", "sharpe_ratio", "max_drawdown"} <= metric_keys
    total_return_metric = next(m for m in detail["metrics"] if m["key"] == "total_return")
    assert total_return_metric["value"] is not None

    event_types = {event["type"] for event in detail["events"]}
    assert event_types <= {"backtest_entry_fill", "backtest_exit_fill", "timing_signal"}
    assert "timing_signal" in event_types  # one current-state row is always written, win or lose
    for event in detail["events"]:
        assert event["status"] in {"executed", "signal_state"}
        assert event["detail"]  # every entry/exit/current-state row carries a real why-reason


def test_staging_universe_is_seeded_by_default_with_no_paid_provider_references(
    tmp_path: Path,
) -> None:
    database = initialize_database(tmp_path / "empty-universe.db")
    store = MemorySecretStore()
    app = create_app(
        database,
        frontend_dist=tmp_path / "missing",
        secret_store=store,
        provider_verifiers={"fred_v2": FakeVerifier()},
        now=lambda: NOW,
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52000),
    ) as client:
        universe = client.get("/api/v1/admin/universe").json()
    assert universe["summary"]["total"] == 26
    assert universe["summary"]["active"] == 26
    assert universe["summary"]["by_category"]["macro_series"] == 4
    assert universe["summary"]["by_category"]["sector_equity_etf"] == 11
    symbols_by_key = {item["symbol"]: item for item in universe["symbols"]}
    assert set(symbols_by_key) >= {
        "INDPRO", "CPIAUCSL", "NFCI", "VIXCLS",
        "SPY", "QQQ", "DIA", "TLT", "IEF", "GLD", "BTC-USD",
        "XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLK", "XLU",
        "AAPL", "NVDA", "SMH", "IGV",
    }
    assert all(item["tier"] == "free" for item in universe["symbols"])
    assert symbols_by_key["INDPRO"]["production_provider_key"] == "fred"
    assert symbols_by_key["SPY"]["production_provider_key"] == "intrinio"
    assert symbols_by_key["SPY"]["production_provider_name"] == "Intrinio"
    assert symbols_by_key["BTC-USD"]["production_provider_key"] is None


def test_seeded_admin_inventory_strategies_signals_and_chart_annotations(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    _, client, _, _ = admin_context
    overview = client.get("/api/v1/admin/overview").json()
    assert overview["manual_only"] is True
    assert overview["data"] == {
        "assets": 6,
        "ready": 3,
        "stale": 0,
        "missing": 3,
        "partial": 0,
        "invalid": 0,
        "invalid_assets": 0,
        "invalid_symbols": 0,
    }
    data = client.get("/api/v1/admin/data").json()
    demo = next(
        asset for asset in data["assets"] if asset["key"] == "demo_daily_bars"
    )
    assert demo["freshness"] == "not_applicable"
    assert demo["classification"] == "synthetic"
    fred = next(asset for asset in data["assets"] if asset["key"] == "fred_release_observations")
    assert fred["freshness"] == "missing"
    assert fred["row_count"] == 0
    assert len(data["symbols"]) == 6
    spy_data = next(item for item in data["symbols"] if item["symbol"] == "SPY")
    assert spy_data["row_count"] == 8
    assert spy_data["freshness"] == "not_applicable"
    assert spy_data["classification"] == "synthetic"

    strategies = client.get("/api/v1/admin/strategies").json()
    # 2 synthetic demo fixtures (seed.py) + 5 real engine algorithms
    # registered in schema.sql (macro_regime_composite, cross_sectional_momentum,
    # macd_rsi_single_name_timing, risk_envelope_allocation,
    # conviction_instrument_selection) + 2 honest draft placeholders with no
    # implementation yet (sentiment_text_mining, fundamental_analysis).
    assert strategies["summary"]["total"] == 9
    assert strategies["strategies"][0]["decay"]["value"] is None
    detail = client.get(
        "/api/v1/admin/strategies/state_conditioned_exposure"
    ).json()["strategy"]
    assert detail["versions"][0]["diagnostics"][0]["value"] is None
    assert detail["research_runs"] == []
    assert detail["public_spec_url"] is None

    real_strategy = client.get(
        "/api/v1/admin/strategies/macro_regime_composite"
    ).json()["strategy"]
    assert real_strategy["status"] == "active"
    assert real_strategy["version"] == "naive-v2"
    versions_by_number = {version["version"]: version for version in real_strategy["versions"]}
    assert set(versions_by_number) == {"naive-v1", "naive-v2"}
    real_version = versions_by_number["naive-v2"]
    assert real_version["verification_status"] == "registered_only"
    assert real_version["next_review_at"] == "2027-02-25"
    assert real_version["code_reference"] == "backend/engine/regime/scoring_v2.py"
    decay_diagnostic = next(d for d in real_version["diagnostics"] if d["metric_key"] == "decay_rate")
    assert decay_diagnostic["value"] is None
    # naive-v1 stays present, unedited, for historical reproducibility of any
    # dataset snapshot already sealed under it.
    v1_version = versions_by_number["naive-v1"]
    assert v1_version["code_reference"] == "backend/engine/regime/scoring.py"
    assert decay_diagnostic["status"] == "not_computed"

    tlt = client.get("/api/v1/symbols/TLT").json()
    assert tlt["current_signal"]["status"] == "candidate"
    assert tlt["current_signal"]["direction"] == "bullish"
    signal_event = next(event for event in tlt["events"] if event["type"] == "signal_entry")
    assert signal_event["id"] == "tlt_signal_candidate"
    assert signal_event["status"] == "signal_state"
    assert "no order" in signal_event["detail"].lower()
    assert "no fill" in signal_event["detail"].lower()
    qqq = client.get("/api/v1/symbols/QQQ").json()
    assert qqq["current_signal"]["status"] == "none"
    assert qqq["current_signal"]["strength"] is None

    hardened = client.get("/api/v1/admin/providers")
    assert hardened.headers["cache-control"] == "no-store"
    assert hardened.headers["x-content-type-options"] == "nosniff"
    assert hardened.headers["referrer-policy"] == "no-referrer"
    assert hardened.headers["x-frame-options"] == "DENY"


def test_mutations_require_direct_loopback_origin_and_exact_action(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    _, client, store, _ = admin_context
    route = "/api/v1/admin/providers/fred/credential"
    payload = {"secret": "safe-test-value"}
    assert client.put(route, json=payload).status_code == 403
    assert client.put(
        route,
        json=payload,
        headers=operator_headers("credential.write", origin="https://example.com"),
    ).status_code == 403
    assert client.put(
        route,
        json=payload,
        headers={**operator_headers("wrong.action"), "X-Forwarded-For": "127.0.0.1"},
    ).status_code == 403
    assert store.set_calls == []


def test_mutation_rejects_non_loopback_client(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "desk.db")
    store = MemorySecretStore()
    app = create_app(database, secret_store=store, now=lambda: NOW)
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("198.51.100.4", 52000),
    ) as client:
        read_response = client.get("/api/v1/admin/overview")
        response = client.put(
            "/api/v1/admin/providers/fred/credential",
            json={"secret": "safe-test-value"},
            headers=operator_headers("credential.write"),
        )
    assert read_response.status_code == 403
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "operator_loopback_required"
    assert store.set_calls == []


def test_invalid_secret_validation_never_echoes_rejected_input(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    _, client, store, _ = admin_context
    rejected = " DO-NOT-ECHO-THIS-CREDENTIAL "
    response = client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": rejected},
        headers=operator_headers("credential.write"),
    )
    assert response.status_code == 422
    assert rejected not in response.text
    assert "DO-NOT-ECHO" not in response.text
    assert "input" not in response.text
    assert store.set_calls == []


def test_credential_is_keyring_only_and_verification_is_cached_and_invalidated(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    database, client, store, verifier = admin_context
    first_secret = "first-local-test-credential"
    write = client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": first_secret},
        headers=operator_headers("credential.write"),
    )
    assert write.status_code == 200
    assert first_secret not in write.text
    assert write.json()["provider"]["credential"]["status"] == "unverified"

    first = client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    )
    second = client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    )
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert verifier.calls == [first_secret]
    assert first_secret not in first.text + second.text
    provider_payload = client.get("/api/v1/admin/providers").json()
    provider = provider_payload["providers"][0]
    assert provider["credential"]["verification_status"] == "healthy"
    assert provider["verification"]["http_status"] == 200
    roadmap = provider_payload["roadmap"]
    assert roadmap["summary"]["verified_accounts"] == 1
    assert roadmap["summary"]["registrations_needed_now"] == 0
    assert roadmap["summary"]["verifications_needed_now"] == 0
    assert roadmap["summary"]["future_accounts_planned"] == 3
    assert roadmap["summary"]["capabilities_ingestion_ready"] == 0
    assert roadmap["accounts"][0]["integration_status"] == "verification_ready"
    assert roadmap["accounts"][0]["access_status"] == "healthy"
    assert roadmap["capabilities"][0]["ingestion_ready"] is False
    assert roadmap["capabilities"][0]["integration_status"] == "verification_ready"
    assert "No additional registration is needed" in roadmap["next_action"]
    readiness = client.get("/api/v1/admin/overview").json()["readiness"]
    readiness_gates = {gate["key"]: gate for gate in readiness["gates"]}
    assert readiness["summary"]["gates_passed"] == 1
    assert readiness["summary"]["current_gate_key"] == "macro_pit_ingestion"
    assert readiness["summary"]["target_route"] == "/operations"
    assert readiness_gates["fred_provider_access"]["status"] == "passed"
    assert readiness_gates["macro_pit_ingestion"]["status"] == "action_required"
    assert readiness_gates["macro_pit_ingestion"]["blocked_by"] == []
    assert readiness_gates["macro_validation_seal"]["status"] == "blocked"
    assert readiness_gates["versioned_security_universe"]["evidence"][0][
        "status"
    ] == "non_qualifying"

    second_secret = "second-local-test-credential"
    rotated = client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": second_secret},
        headers=operator_headers("credential.write"),
    ).json()["provider"]
    assert rotated["verification"] is None
    assert rotated["credential"]["verification_status"] is None
    verified_again = client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    ).json()
    assert verified_again["cached"] is False
    assert verifier.calls == [first_secret, second_secret]

    deleted = client.delete(
        "/api/v1/admin/providers/fred/credential",
        headers=operator_headers("credential.delete"),
    ).json()
    assert deleted["deleted"] is True
    assert deleted["provider"]["verification"] is None
    assert deleted["provider"]["credential"]["configured"] is False

    # SQLite contains metadata and sanitized verification history, never either secret.
    with connect(database, read_only=True) as connection:
        for table_row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall():
            rows = connection.execute(f'SELECT * FROM "{table_row["name"]}"').fetchall()
            serialized = repr([tuple(row) for row in rows])
            assert first_secret not in serialized
            assert second_secret not in serialized
        assert connection.execute("SELECT COUNT(*) FROM provider_verifications").fetchone()[0] == 2
    assert store.values == {}


def test_readiness_uses_latest_matching_real_evidence_and_rejects_demo_fetch(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    database, client, _, _ = admin_context
    client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": "readiness-matching-evidence"},
        headers=operator_headers("credential.write"),
    )
    client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    )

    with connect(database) as connection:
        connection.execute(
            """
            UPDATE pipeline_stage_definitions
            SET implementation_status = 'ready'
            WHERE pipeline_key = 'daily_desk' AND stage_key = 'fetch_data'
            """
        )
        connection.execute(
            """
            INSERT INTO dataset_snapshots (
                id, as_of, created_at, mode, data_classification, is_live,
                is_demo, status, immutable, source_manifest_json
            ) VALUES (
                'real-macro-readiness', '2026-08-24T11:55:00Z',
                '2026-08-24T11:56:00Z', 'research', 'real', 0, 0,
                'staging', 0, '{"source":"fred"}'
            )
            """
        )
        connection.execute(
            """
            UPDATE data_assets
            SET row_count = 12, period_start = '2026-08-01T00:00:00Z',
                period_end = '2026-08-24T00:00:00Z',
                last_observation_at = '2026-08-24T00:00:00Z',
                last_fetched_at = '2026-08-24T11:56:00Z', status = 'ready',
                dataset_snapshot_id = 'real-macro-readiness',
                detail = 'Test point-in-time macro inventory.',
                updated_at = '2026-08-24T11:56:00Z'
            WHERE asset_key = 'fred_release_observations'
            """
        )
        connection.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, pipeline_key, pipeline_version, trigger_type, dry_run,
                requested_at, started_at, status, dataset_snapshot_id, summary
            ) VALUES (
                'real-fetch-run', 'daily_desk', '0.1.0', 'manual', 0,
                '2026-08-24T11:56:00Z', '2026-08-24T11:56:00Z', 'running',
                'real-macro-readiness', 'Real fetch test.'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO pipeline_stage_runs (
                run_id, stage_key, stage_order, status, started_at, finished_at,
                records_read, records_written, message
            ) VALUES (
                'real-fetch-run', 'fetch_data', 20, 'completed',
                '2026-08-24T11:56:00Z', '2026-08-24T11:57:00Z',
                12, 12, 'Stored real FRED observations.'
            )
            """
        )
        connection.execute(
            """
            UPDATE pipeline_runs
            SET finished_at = '2026-08-24T11:57:00Z', status = 'partial'
            WHERE run_id = 'real-fetch-run'
            """
        )

    real_readiness = client.get("/api/v1/admin/overview").json()["readiness"]
    real_gates = {gate["key"]: gate for gate in real_readiness["gates"]}
    assert real_readiness["summary"]["gates_passed"] == 2
    assert real_readiness["summary"]["current_gate_key"] == "macro_validation_seal"
    assert real_gates["macro_pit_ingestion"]["status"] == "passed"
    assert real_gates["macro_validation_seal"]["status"] == "action_required"
    assert any(
        evidence["record_id"] == "real-macro-readiness"
        and evidence["status"] == "qualifying"
        for evidence in real_gates["macro_pit_ingestion"]["evidence"]
    )

    with connect(database) as connection:
        connection.execute(
            """
            INSERT INTO dataset_snapshots (
                id, as_of, created_at, mode, data_classification, is_live,
                is_demo, status, immutable, source_manifest_json
            ) VALUES (
                'newer-demo-fetch', '2026-08-24T11:58:00Z',
                '2026-08-24T11:58:00Z', 'demo', 'synthetic', 0, 1,
                'demo_not_live', 0, '{}'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO data_assets (
                asset_key, provider_key, label, kind, frequency,
                classification, row_count, period_start, period_end,
                last_observation_at, last_fetched_at, status,
                dataset_snapshot_id, detail, updated_at
            ) VALUES (
                'fred_demo_attempt', 'fred', 'Synthetic FRED lookalike',
                'macro_release', 'release', 'synthetic', 12,
                '2026-08-01T00:00:00Z', '2026-08-24T00:00:00Z',
                '2026-08-24T00:00:00Z', '2026-08-24T11:58:00Z', 'ready',
                'newer-demo-fetch', 'Must never satisfy real readiness.',
                '2026-08-24T11:58:00Z'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, pipeline_key, pipeline_version, trigger_type, dry_run,
                requested_at, started_at, status, dataset_snapshot_id, summary
            ) VALUES (
                'demo-fetch-run', 'daily_desk', '0.1.0', 'manual', 0,
                '2026-08-24T11:58:00Z', '2026-08-24T11:58:00Z', 'running',
                'newer-demo-fetch', 'Synthetic fetch test.'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO pipeline_stage_runs (
                run_id, stage_key, stage_order, status, started_at, finished_at,
                records_read, records_written, message
            ) VALUES (
                'demo-fetch-run', 'fetch_data', 20, 'completed',
                '2026-08-24T11:58:00Z', '2026-08-24T11:59:00Z',
                12, 12, 'Stored only synthetic rows.'
            )
            """
        )
        connection.execute(
            """
            UPDATE pipeline_runs
            SET finished_at = '2026-08-24T11:59:00Z', status = 'partial'
            WHERE run_id = 'demo-fetch-run'
            """
        )

    demo_readiness = client.get("/api/v1/admin/overview").json()["readiness"]
    demo_gates = {gate["key"]: gate for gate in demo_readiness["gates"]}
    assert demo_readiness["summary"]["gates_passed"] == 1
    assert demo_readiness["summary"]["current_gate_key"] == "macro_pit_ingestion"
    assert demo_gates["macro_pit_ingestion"]["status"] == "failed"
    assert demo_gates["macro_validation_seal"]["status"] == "blocked"
    assert demo_gates["macro_validation_seal"]["blocked_by"] == [
        "macro_pit_ingestion"
    ]


def test_environment_managed_credential_cannot_be_overridden_or_deleted(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    _, client, store, _ = admin_context
    store.values["fred_api_key"] = SecretValue(
        "environment-only-value", "environment", False
    )
    put = client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": "replacement-value"},
        headers=operator_headers("credential.write"),
    )
    delete = client.delete(
        "/api/v1/admin/providers/fred/credential",
        headers=operator_headers("credential.delete"),
    )
    assert put.status_code == 409
    assert delete.status_code == 409
    assert put.json()["detail"]["code"] == "credential_environment_managed"
    assert store.set_calls == []
    assert store.delete_calls == []


def test_manual_pipeline_preflight_requires_current_healthy_verification(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    database, client, _, _ = admin_context
    client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": "pipeline-test-credential"},
        headers=operator_headers("credential.write"),
    )
    unverified = client.post(
        "/api/v1/admin/pipeline/runs",
        json={"dry_run": True},
        headers=operator_headers("pipeline.run"),
    ).json()["run"]
    assert unverified["status"] == "partial"
    assert "unverified" in unverified["stages"][0]["detail"]

    client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    )
    ready = client.post(
        "/api/v1/admin/pipeline/runs",
        json={"dry_run": True},
        headers=operator_headers("pipeline.run"),
    ).json()["run"]
    assert ready["status"] == "completed"
    assert ready["stages"][0]["status"] == "completed"
    assert all(stage["status"] == "skipped" for stage in ready["stages"][1:])

    actual = client.post(
        "/api/v1/admin/pipeline/runs",
        json={"dry_run": False},
        headers=operator_headers("pipeline.run"),
    ).json()["run"]
    assert actual["status"] == "blocked"
    fetch = next(stage for stage in actual["stages"] if stage["key"] == "fetch_data")
    validate = next(stage for stage in actual["stages"] if stage["key"] == "validate_data")
    regime = next(stage for stage in actual["stages"] if stage["key"] == "regime_filter")
    factor = next(stage for stage in actual["stages"] if stage["key"] == "factor_engine")
    allocation = next(stage for stage in actual["stages"] if stage["key"] == "allocation_engine")
    instrument = next(stage for stage in actual["stages"] if stage["key"] == "instrument_engine")
    publish = next(stage for stage in actual["stages"] if stage["key"] == "publish_snapshot")
    assert fetch["status"] == "completed"
    assert fetch["error_code"] is None
    assert validate["status"] == "completed"
    assert regime["status"] == "completed"
    assert factor["status"] == "completed"
    assert factor["error_code"] is None
    assert allocation["status"] == "completed"
    assert allocation["error_code"] is None
    assert instrument["status"] == "completed"
    assert instrument["error_code"] is None
    assert publish["error_code"] == "stage_not_implemented"
    assert actual["dataset_snapshot_id"] is not None
    assert actual["desk_snapshot_id"] is not None

    with connect(database) as connection:
        connection.execute(
            "UPDATE operator_providers SET enabled = 0 WHERE provider_key = 'fred'"
        )
    disabled = client.post(
        "/api/v1/admin/pipeline/runs",
        json={"dry_run": True},
        headers=operator_headers("pipeline.run"),
    ).json()["run"]
    assert disabled["status"] == "partial"
    assert "disabled fred" in disabled["stages"][0]["detail"]


def test_verification_cooldown_and_health_ttl_are_separate_fail_closed_boundaries(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
    tmp_path: Path,
) -> None:
    database, client, store, _ = admin_context
    client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": "expiry-boundary-test"},
        headers=operator_headers("credential.write"),
    )
    verified = client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    ).json()["verification"]
    assert verified["status"] == "healthy"

    after_cooldown = NOW + timedelta(minutes=16)
    cooldown_verifier = FakeVerifier()
    restarted = create_app(
        database,
        frontend_dist=tmp_path / "missing-cooldown-dist",
        secret_store=store,
        provider_verifiers={"fred_v2": cooldown_verifier},
        now=lambda: after_cooldown,
    )
    with TestClient(
        restarted,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52001),
    ) as cooldown_client:
        provider = cooldown_client.get("/api/v1/admin/providers").json()["providers"][0]
        assert provider["credential"]["status"] == "verified"
        assert provider["credential"]["verification_status"] == "healthy"
        assert provider["credential"]["cooldown_remaining_seconds"] == 0
        assert provider["verification"]["current"] is True
        assert provider["last_verification"]["expired"] is False
        run = cooldown_client.post(
            "/api/v1/admin/pipeline/runs",
            json={"dry_run": True},
            headers=operator_headers("pipeline.run"),
        ).json()["run"]
        assert run["status"] == "completed"
        reverified = cooldown_client.post(
            "/api/v1/admin/providers/fred/verify",
            json={},
            headers=operator_headers("provider.verify"),
        ).json()
        assert reverified["cached"] is False
    assert cooldown_verifier.calls == ["expiry-boundary-test"]

    after_ttl = NOW + timedelta(days=366)
    expired = create_app(
        database,
        frontend_dist=tmp_path / "missing-expired-dist",
        secret_store=store,
        provider_verifiers={"fred_v2": FakeVerifier()},
        now=lambda: after_ttl,
    )
    with TestClient(
        expired,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52002),
    ) as expired_client:
        provider = expired_client.get("/api/v1/admin/providers").json()["providers"][0]
        assert provider["credential"]["status"] == "expired"
        assert provider["credential"]["verification_status"] is None
        assert provider["verification"] is None
        assert provider["last_verification"]["current"] is False
        assert provider["last_verification"]["expired"] is True
        assert provider["credential"]["last_verified_at"] is not None
        run = expired_client.post(
            "/api/v1/admin/pipeline/runs",
            json={"dry_run": True},
            headers=operator_headers("pipeline.run"),
        ).json()["run"]
        assert run["status"] == "partial"
        assert "expired fred" in run["stages"][0]["detail"]


def test_environment_and_artifact_guards_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEAE_ADMIN_ALLOWED_ORIGINS", "https://example.com")
    with pytest.raises(ValueError, match="loopback"):
        create_app(
            tmp_path / "bad-origin.db",
            secret_store=MemorySecretStore(),
            now=lambda: NOW,
        )
    monkeypatch.delenv("HEAE_ADMIN_ALLOWED_ORIGINS")

    database = tmp_path / "research.db"
    seed_demo(database)
    with connect(database) as connection:
        connection.execute(
            """
            INSERT INTO research_runs (
                research_run_id, strategy_key, strategy_version,
                dataset_snapshot_id, parameters_json, status, summary
            ) VALUES (?, ?, ?, ?, '{}', 'completed', ?)
            """,
            (
                "research-1",
                "state_conditioned_exposure",
                "0.1.0-demo",
                DEMO_DATASET_ID,
                "Metadata-only test run.",
            ),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO research_artifacts (
                    research_run_id, artifact_key, relative_path, media_type,
                    sha256, size_bytes, curated, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "research-1",
                    "unsafe",
                    "/Users/example/private.md",
                    "text/markdown",
                    "0" * 64,
                    10,
                    0,
                    "2026-08-24T12:00:00Z",
                ),
            )


def test_published_symbol_signal_is_immutable(admin_context) -> None:
    database, _, _, _ = admin_context
    with connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE symbol_signals SET status = 'active'
                WHERE snapshot_id = ? AND symbol = 'TLT'
                """,
                (DEMO_SNAPSHOT_ID,),
            )


def test_fred_verifier_uses_bearer_header_without_redirects_or_secret_in_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class Response:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return {"release": {"release_id": 10}, "series": []}

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            captured["kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get(self, url: str, *, params: dict[str, Any]):
            captured["url"] = url
            captured["params"] = params
            return Response()

    monkeypatch.setattr("backend.providers.fred.httpx.Client", Client)
    secret = "fred-test-secret"
    result = FredV2Verifier().verify(secret)
    assert result.status == "healthy"
    assert captured["kwargs"]["follow_redirects"] is False
    assert captured["kwargs"]["trust_env"] is False
    assert captured["kwargs"]["headers"]["Authorization"] == f"Bearer {secret}"
    assert secret not in captured["url"]
    assert secret not in repr(captured["params"])
    assert secret not in repr(result)


def test_newer_mutable_snapshot_is_never_published_by_decision_or_inventory_apis(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    database, client, _, _ = admin_context
    published_id = client.get("/api/v1/desk/latest").json()["snapshot"]["id"]
    published_dataset = client.get("/api/v1/admin/data").json()["symbols"][0][
        "dataset_snapshot_id"
    ]
    with connect(database) as connection:
        connection.execute(
            """
            INSERT INTO dataset_snapshots (
                id, as_of, created_at, mode, data_classification, is_live,
                is_demo, status, immutable, source_manifest_json
            ) VALUES (?, ?, ?, 'research', 'real', 0, 0, 'draft', 0, '{}')
            """,
            (
                "newer-mutable-dataset",
                "2026-08-30T20:00:00Z",
                "2026-08-30T20:01:00Z",
            ),
        )
        source = connection.execute(
            "SELECT * FROM desk_snapshots WHERE id = ?", (published_id,)
        ).fetchone()
        columns = [item["name"] for item in connection.execute("PRAGMA table_info(desk_snapshots)")]
        values = dict(source)
        values.update(
            {
                "id": "newer-mutable-desk",
                "dataset_snapshot_id": "newer-mutable-dataset",
                "as_of": "2026-08-30T20:00:00Z",
                "created_at": "2026-08-30T20:01:00Z",
                "mode": "research",
                "data_classification": "real",
                "is_live": 0,
                "is_demo": 0,
                "status": "draft",
                "immutable": 0,
                "title": "Unpublished draft",
            }
        )
        connection.execute(
            f"INSERT INTO desk_snapshots ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            tuple(values[column] for column in columns),
        )

    assert client.get("/api/v1/desk/latest").json()["snapshot"]["id"] == published_id
    assert client.get("/api/health").json()["snapshot"]["id"] == published_id
    assert client.get("/api/v1/symbols").json()["snapshot"]["id"] == published_id
    inventory = client.get("/api/v1/admin/data").json()
    assert {item["dataset_snapshot_id"] for item in inventory["symbols"]} == {
        published_dataset
    }


def test_credential_partial_failures_always_fail_closed(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    database, client, store, _ = admin_context
    write_route = "/api/v1/admin/providers/fred/credential"
    verify_route = "/api/v1/admin/providers/fred/verify"
    client.put(
        write_route,
        json={"secret": "old-keyring-value"},
        headers=operator_headers("credential.write"),
    )
    client.post(
        verify_route, json={}, headers=operator_headers("provider.verify")
    )

    store.fail_set = True
    failed_rotation = client.put(
        write_route,
        json={"secret": "new-value-that-must-not-leak"},
        headers=operator_headers("credential.write"),
    )
    assert failed_rotation.status_code == 503
    assert "new-value-that-must-not-leak" not in failed_rotation.text
    provider = client.get("/api/v1/admin/providers").json()["providers"][0]
    assert provider["credential"]["configured"] is True
    assert provider["credential"]["status"] == "unverified"
    assert provider["verification"] is None
    assert store.values["fred_api_key"].value == "old-keyring-value"

    store.fail_set = False
    client.post(
        verify_route, json={}, headers=operator_headers("provider.verify")
    )
    store.fail_delete = True
    failed_delete = client.delete(
        write_route, headers=operator_headers("credential.delete")
    )
    assert failed_delete.status_code == 503
    provider = client.get("/api/v1/admin/providers").json()["providers"][0]
    assert provider["credential"]["status"] == "unverified"
    assert provider["verification"] is None
    assert store.values["fred_api_key"].value == "old-keyring-value"

    store.fail_delete = False
    client.post(
        verify_route, json={}, headers=operator_headers("provider.verify")
    )
    with connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_credential_revision
            BEFORE UPDATE ON operator_providers
            BEGIN
                SELECT RAISE(ABORT, 'injected metadata failure');
            END
            """
        )
    set_call_count = len(store.set_calls)
    delete_call_count = len(store.delete_calls)
    db_failed_rotation = client.put(
        write_route,
        json={"secret": "external-store-must-not-change"},
        headers=operator_headers("credential.write"),
    )
    db_failed_delete = client.delete(
        write_route, headers=operator_headers("credential.delete")
    )
    assert db_failed_rotation.status_code == 503
    assert db_failed_delete.status_code == 503
    assert len(store.set_calls) == set_call_count
    assert len(store.delete_calls) == delete_call_count
    assert store.values["fred_api_key"].value == "old-keyring-value"
    provider = client.get("/api/v1/admin/providers").json()["providers"][0]
    assert provider["credential"]["verification_status"] == "healthy"


def test_verification_source_and_environment_runtime_must_match(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
    tmp_path: Path,
) -> None:
    database, client, store, verifier = admin_context
    client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": "keyring-source-value"},
        headers=operator_headers("credential.write"),
    )
    client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    )
    store.values["fred_api_key"] = SecretValue(
        "environment-runtime-one", "environment", False
    )
    source_changed = client.get("/api/v1/admin/providers").json()["providers"][0]
    assert source_changed["credential"]["status"] == "unverified"
    assert source_changed["verification"] is None
    client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    )
    assert verifier.calls[-1] == "environment-runtime-one"

    store.values["fred_api_key"] = SecretValue(
        "environment-runtime-two", "environment", False
    )
    restarted_verifier = FakeVerifier()
    restarted_app = create_app(
        database,
        frontend_dist=tmp_path / "missing-restarted-dist",
        secret_store=store,
        provider_verifiers={"fred_v2": restarted_verifier},
        now=lambda: NOW,
    )
    with TestClient(
        restarted_app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52001),
    ) as restarted:
        provider = restarted.get("/api/v1/admin/providers").json()["providers"][0]
        assert provider["credential"]["status"] == "unverified"
        assert provider["verification"] is None
        result = restarted.post(
            "/api/v1/admin/providers/fred/verify",
            json={},
            headers=operator_headers("provider.verify"),
        ).json()
        assert result["cached"] is False
    assert restarted_verifier.calls == ["environment-runtime-two"]


def test_same_timestamp_latest_rows_follow_insertion_order(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    database, client, _, _ = admin_context
    client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": "same-time-value"},
        headers=operator_headers("credential.write"),
    )
    with connect(database) as connection:
        revision = connection.execute(
            "SELECT credential_revision FROM operator_providers WHERE provider_key = 'fred'"
        ).fetchone()[0]
        rows = [
            ("verify-z-first", "healthy", "First inserted."),
            ("verify-a-second", "invalid_credentials", "Second inserted."),
        ]
        for verification_id, status, message in rows:
            connection.execute(
                """
                INSERT INTO provider_verifications (
                    verification_id, provider_key, checked_at, expires_at,
                    status, message, credential_revision, runtime_id,
                    credential_source
                ) VALUES (?, 'fred', ?, ?, ?, ?, ?, 'irrelevant-for-keyring', 'keyring')
                """,
                (
                    verification_id,
                    "2026-08-24T12:00:00.000000Z",
                    "2026-08-24T12:15:00.000000Z",
                    status,
                    message,
                    revision,
                ),
            )
    provider = client.get("/api/v1/admin/providers").json()["providers"][0]
    assert provider["verification"]["id"] == "verify-a-second"
    assert provider["credential"]["verification_status"] == "invalid_credentials"

    first = client.post(
        "/api/v1/admin/pipeline/runs",
        json={"dry_run": True},
        headers=operator_headers("pipeline.run"),
    ).json()["run"]
    second = client.post(
        "/api/v1/admin/pipeline/runs",
        json={"dry_run": True},
        headers=operator_headers("pipeline.run"),
    ).json()["run"]
    latest = client.get("/api/v1/admin/pipeline").json()["latest_run"]
    assert first["id"] != second["id"]
    assert latest["id"] == second["id"]
    assert latest["requested_at"].endswith(".000000Z")


def test_future_dated_verification_fails_closed_and_current_reverify_recovers(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    database, client, _, verifier = admin_context
    credential = "clock-correction-test-key"
    client.put(
        "/api/v1/admin/providers/fred/credential",
        json={"secret": credential},
        headers=operator_headers("credential.write"),
    )
    client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    )
    assert verifier.calls == [credential]
    with connect(database) as connection:
        revision = connection.execute(
            "SELECT credential_revision FROM operator_providers WHERE provider_key = 'fred'"
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO provider_verifications (
                verification_id, provider_key, checked_at, expires_at, status,
                message, credential_revision, runtime_id, credential_source
            ) VALUES (
                'future-clock-row', 'fred', '2026-08-25T12:00:00.000000Z',
                '2026-09-01T12:00:00.000000Z', 'healthy',
                'Injected future-clock result.', ?, 'future-runtime', 'keyring'
            )
            """,
            (revision,),
        )

    provider = client.get("/api/v1/admin/providers").json()["providers"][0]
    assert provider["credential"]["status"] == "invalid_clock"
    assert provider["credential"]["verification_status"] is None
    assert provider["credential"]["cooldown_remaining_seconds"] == 0
    assert provider["verification"] is None
    assert provider["last_verification"]["id"] == "future-clock-row"
    assert provider["last_verification"]["future_dated"] is True
    run = client.post(
        "/api/v1/admin/pipeline/runs",
        json={"dry_run": True},
        headers=operator_headers("pipeline.run"),
    ).json()["run"]
    assert run["status"] == "partial"
    assert "invalid clock fred" in run["stages"][0]["detail"]

    corrected = client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    ).json()
    assert corrected["cached"] is False
    assert verifier.calls == [credential, credential]
    provider = client.get("/api/v1/admin/providers").json()["providers"][0]
    assert provider["credential"]["status"] == "verified"
    assert provider["credential"]["verification_status"] == "healthy"
    assert provider["last_verification"]["id"] == corrected["verification"]["id"]
    assert provider["last_verification"]["future_dated"] is False


def test_future_observations_are_invalid_beyond_named_clock_tolerance(
    tmp_path: Path,
) -> None:
    database = tmp_path / "future.db"
    seed_demo(database)
    future_now = datetime(2026, 8, 21, 19, 50, tzinfo=timezone.utc)
    store = MemorySecretStore()
    app = create_app(
        database,
        secret_store=store,
        provider_verifiers={"fred_v2": FakeVerifier()},
        fred_observation_fetcher=make_fred_fetcher(),
        price_fetcher=make_price_fetcher(future_now.date()),
        now=lambda: future_now,
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52000),
    ) as client:
        data = client.get("/api/v1/admin/data").json()
        bars = next(
            asset
            for asset in data["assets"]
            if asset["key"] == "demo_daily_bars"
        )
        spy = next(symbol for symbol in data["symbols"] if symbol["symbol"] == "SPY")
        assert bars["freshness"] == "future"
        assert bars["status"] == "invalid"
        assert bars["age_seconds"] == -600
        assert spy["freshness"] == "future"
        assert spy["status"] == "invalid"
        assert spy["age_seconds"] == -600
        assert data["summary"]["invalid_assets"] == 3
        assert data["summary"]["invalid_symbols"] == 6
        run = client.post(
            "/api/v1/admin/pipeline/runs",
            json={"dry_run": True},
            headers=operator_headers("pipeline.run"),
        ).json()["run"]
        assert run["status"] == "partial"
        assert (
            "invalid future-dated inventory records: 9 (assets 3, symbols 6)"
            in run["stages"][0]["detail"]
        )

        # Invalid existing inventory is visible during preflight, but fetch must
        # still be allowed to refresh it. With the provider healthy, fetch_data
        # now runs for real and succeeds; the run proceeds through validate_data
        # and regime_filter and stops at the still-scaffolded factor_engine stage.
        client.put(
            "/api/v1/admin/providers/fred/credential",
            json={"secret": "future-inventory-refresh-test"},
            headers=operator_headers("credential.write"),
        )
        client.post(
            "/api/v1/admin/providers/fred/verify",
            json={},
            headers=operator_headers("provider.verify"),
        )
        actual = client.post(
            "/api/v1/admin/pipeline/runs",
            json={"dry_run": False},
            headers=operator_headers("pipeline.run"),
        ).json()["run"]
        fetch = next(stage for stage in actual["stages"] if stage["key"] == "fetch_data")
        assert fetch["status"] == "completed"
        assert fetch["error_code"] is None


def test_keyring_read_failure_uses_explicit_environment_fallback_or_safe_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenKeyring:
        @staticmethod
        def get_password(_service_name: str, _credential_name: str) -> str | None:
            raise RuntimeError("private backend diagnostic must not escape")

    monkeypatch.setattr(
        KeyringEnvironmentSecretStore,
        "_keyring",
        staticmethod(lambda: BrokenKeyring()),
    )
    store = KeyringEnvironmentSecretStore()
    monkeypatch.setenv("HEAE_FRED_API_KEY", "environment-fallback-test")
    fallback = store.get("fred_api_key", "HEAE_FRED_API_KEY")
    assert fallback == SecretValue(
        "environment-fallback-test", "environment", False
    )

    monkeypatch.delenv("HEAE_FRED_API_KEY")
    with pytest.raises(SecretStoreUnavailable):
        store.get("fred_api_key", "HEAE_FRED_API_KEY")

    database = initialize_database(tmp_path / "keyring-unavailable.db")
    app = create_app(database, secret_store=store, now=lambda: NOW)
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52000),
    ) as client:
        responses = [
            client.get("/api/v1/admin/overview"),
            client.get("/api/v1/admin/providers"),
            client.post(
                "/api/v1/admin/providers/fred/verify",
                json={},
                headers=operator_headers("provider.verify"),
            ),
            client.post(
                "/api/v1/admin/pipeline/runs",
                json={"dry_run": True},
                headers=operator_headers("pipeline.run"),
            ),
        ]
    for response in responses:
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "credential_store_unavailable"
        assert "private backend diagnostic" not in response.text
        assert response.headers["cache-control"] == "no-store"


def test_research_completion_requires_sealed_dataset_provenance(tmp_path: Path) -> None:
    database = tmp_path / "research-provenance.db"
    seed_demo(database)
    with connect(database) as connection:
        connection.execute(
            """
            INSERT INTO research_runs (
                research_run_id, strategy_key, strategy_version,
                parameters_json, status, summary
            ) VALUES ('research-transition', 'state_conditioned_exposure',
                      '0.1.0-demo', '{}', 'queued', 'Pending research.')
            """
        )
        connection.commit()
        connection.execute(
            "UPDATE research_runs SET status = 'running' WHERE research_run_id = 'research-transition'"
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE research_runs SET status = 'completed' WHERE research_run_id = 'research-transition'"
            )
        connection.rollback()
        connection.execute(
            """
            INSERT INTO dataset_snapshots (
                id, as_of, created_at, mode, data_classification, is_live,
                is_demo, status, immutable, source_manifest_json
            ) VALUES ('research-draft-data', ?, ?, 'research', 'real', 0, 0,
                      'draft', 0, '{}')
            """,
            ("2026-08-24T12:00:00Z", "2026-08-24T12:01:00Z"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE research_runs
                SET status = 'completed', dataset_snapshot_id = 'research-draft-data'
                WHERE research_run_id = 'research-transition'
                """
            )
        connection.rollback()
        connection.execute(
            "UPDATE dataset_snapshots SET immutable = 1 WHERE id = 'research-draft-data'"
        )
        connection.execute(
            """
            UPDATE research_runs
            SET status = 'completed', dataset_snapshot_id = 'research-draft-data'
            WHERE research_run_id = 'research-transition'
            """
        )
        connection.commit()
        completed = connection.execute(
            "SELECT status, dataset_snapshot_id FROM research_runs WHERE research_run_id = 'research-transition'"
        ).fetchone()
        assert tuple(completed) == ("completed", "research-draft-data")


def test_v3_event_migration_only_backfills_unambiguous_fills(tmp_path: Path) -> None:
    database = tmp_path / "legacy-v3.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_metadata VALUES ('schema_version', '3');
            CREATE TABLE dataset_snapshots (
                id TEXT PRIMARY KEY, as_of TEXT NOT NULL, created_at TEXT NOT NULL,
                mode TEXT NOT NULL, data_classification TEXT NOT NULL,
                is_live INTEGER NOT NULL, is_demo INTEGER NOT NULL,
                status TEXT NOT NULL, immutable INTEGER NOT NULL,
                source_manifest_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE securities (
                security_id TEXT PRIMARY KEY, primary_symbol TEXT NOT NULL,
                name TEXT NOT NULL, asset_type TEXT NOT NULL, exchange TEXT,
                currency TEXT NOT NULL, sector TEXT, active INTEGER NOT NULL
            );
            CREATE TABLE symbol_events (
                dataset_snapshot_id TEXT NOT NULL REFERENCES dataset_snapshots(id),
                security_id TEXT NOT NULL REFERENCES securities(security_id),
                event_id TEXT NOT NULL, time TEXT NOT NULL, event_type TEXT NOT NULL,
                label TEXT NOT NULL, price REAL, detail TEXT, source_key TEXT,
                observed_at TEXT, available_at TEXT, ingested_at TEXT NOT NULL,
                PRIMARY KEY (dataset_snapshot_id, security_id, event_id)
            );
            INSERT INTO dataset_snapshots VALUES (
                'legacy-data', '2026-01-01T00:00:00Z', '2026-01-01T00:01:00Z',
                'research', 'real', 0, 0, 'sealed', 1, '{}'
            );
            INSERT INTO securities VALUES (
                'legacy-spy', 'SPY', 'Legacy SPY', 'ETF', 'ARCA', 'USD', NULL, 1
            );
            INSERT INTO symbol_events VALUES
                ('legacy-data','legacy-spy','fill','2026-01-01T00:00:00Z',
                 'execution_fill','Confirmed legacy fill',1,NULL,NULL,NULL,NULL,
                 '2026-01-01T00:01:00Z'),
                ('legacy-data','legacy-spy','signal','2026-01-01T00:00:00Z',
                 'signal_entry','Legacy signal',1,NULL,NULL,NULL,NULL,
                 '2026-01-01T00:01:00Z'),
                ('legacy-data','legacy-spy','pattern','2026-01-01T00:00:00Z',
                 'pattern_higher_high','Legacy pattern',1,NULL,NULL,NULL,NULL,
                 '2026-01-01T00:01:00Z');
            CREATE TRIGGER immutable_symbol_events_update
            BEFORE UPDATE ON symbol_events
            WHEN COALESCE((
                SELECT immutable FROM dataset_snapshots
                WHERE id = OLD.dataset_snapshot_id
            ), 0) = 1
            BEGIN
                SELECT RAISE(ABORT, 'cannot update sealed dataset snapshot');
            END;
            """
        )
    initialize_database(database)
    with connect(database, read_only=True) as connection:
        statuses = {
            row["event_id"]: row["event_status"]
            for row in connection.execute(
                "SELECT event_id, event_status FROM symbol_events"
            ).fetchall()
        }
        assert statuses == {
            "fill": "executed",
            "signal": "annotation",
            "pattern": "annotation",
        }
    with connect(database) as connection:
        assert connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'trigger' AND name = 'immutable_symbol_events_update'
            """
        ).fetchone() is not None
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE symbol_events SET label = 'must remain sealed'
                WHERE dataset_snapshot_id = 'legacy-data' AND event_id = 'fill'
                """
            )


def test_concurrent_provider_verification_is_serialized_by_cooldown(tmp_path: Path) -> None:
    database = tmp_path / "concurrent.db"
    seed_demo(database)
    store = MemorySecretStore(
        values={"fred_api_key": SecretValue("concurrent-value", "keyring", True)}
    )

    class BlockingVerifier:
        def __init__(self) -> None:
            self.started = threading.Event()
            self.release = threading.Event()
            self.calls = 0

        def verify(self, secret: str) -> VerificationResult:
            self.calls += 1
            self.started.set()
            assert self.release.wait(timeout=3)
            return VerificationResult(
                status="healthy", message="Verified once.", http_status=200
            )

    verifier = BlockingVerifier()
    app = create_app(
        database,
        secret_store=store,
        provider_verifiers={"fred_v2": verifier},
        now=lambda: NOW,
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52000),
    ) as client, ThreadPoolExecutor(max_workers=2) as pool:
        call = lambda: client.post(
            "/api/v1/admin/providers/fred/verify",
            json={},
            headers=operator_headers("provider.verify"),
        )
        first = pool.submit(call)
        assert verifier.started.wait(timeout=2)
        second = pool.submit(call)
        verifier.release.set()
        responses = [first.result(timeout=4), second.result(timeout=4)]
    assert all(response.status_code == 200 for response in responses)
    assert verifier.calls == 1
    assert {response.json()["cached"] for response in responses} == {False, True}


def test_credential_rotation_delete_and_verification_share_one_provider_lock(
    tmp_path: Path,
) -> None:
    database = tmp_path / "credential-operation-race.db"
    seed_demo(database)

    class BlockingMutationStore(MemorySecretStore):
        def __init__(self) -> None:
            super().__init__()
            self.block_operation: str | None = None
            self.operation_entered = threading.Event()
            self.operation_release = threading.Event()

        def prepare(self, operation: str) -> None:
            self.block_operation = operation
            self.operation_entered.clear()
            self.operation_release.clear()

        def set(self, credential_name: str, secret: str) -> None:
            self.set_calls.append((credential_name, secret))
            if self.block_operation == "set":
                self.operation_entered.set()
                assert self.operation_release.wait(timeout=3)
            self.values[credential_name] = SecretValue(secret, "keyring", True)

        def delete(self, credential_name: str) -> bool:
            self.delete_calls.append(credential_name)
            if self.block_operation == "delete":
                self.operation_entered.set()
                assert self.operation_release.wait(timeout=3)
            return self.values.pop(credential_name, None) is not None

    class TrackingLock:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self._attempt_guard = threading.Lock()
            self._attempts = 0
            self.second_attempted = threading.Event()

        def acquire(self, *, timeout: float) -> bool:
            with self._attempt_guard:
                self._attempts += 1
                if self._attempts == 2:
                    self.second_attempted.set()
            return self._lock.acquire(timeout=timeout)

        def release(self) -> None:
            self._lock.release()

    store = BlockingMutationStore()
    verifier = FakeVerifier()
    app = create_app(
        database,
        secret_store=store,
        provider_verifiers={"fred_v2": verifier},
        now=lambda: NOW,
    )
    write_route = "/api/v1/admin/providers/fred/credential"
    verify_route = "/api/v1/admin/providers/fred/verify"
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52000),
    ) as client, ThreadPoolExecutor(max_workers=2) as pool:
        assert client.put(
            write_route,
            json={"secret": "old-race-key"},
            headers=operator_headers("credential.write"),
        ).status_code == 200
        assert client.post(
            verify_route,
            json={},
            headers=operator_headers("provider.verify"),
        ).status_code == 200
        assert verifier.calls == ["old-race-key"]
        verifier.calls.clear()

        # Rotation blocks after committing the new credential revision but
        # before replacing the old external key. Verification deterministically
        # reaches the same lock and must wait rather than testing the old key
        # under that new revision.
        rotation_lock = TrackingLock()
        app.state.provider_operation_locks["fred"] = rotation_lock
        store.prepare("set")
        rotation = pool.submit(
            lambda: client.put(
                write_route,
                json={"secret": "new-race-key"},
                headers=operator_headers("credential.write"),
            )
        )
        assert store.operation_entered.wait(timeout=2)
        concurrent_verify = pool.submit(
            lambda: client.post(
                verify_route,
                json={},
                headers=operator_headers("provider.verify"),
            )
        )
        assert rotation_lock.second_attempted.wait(timeout=2)
        assert verifier.calls == []
        store.operation_release.set()
        assert rotation.result(timeout=3).status_code == 200
        verify_response = concurrent_verify.result(timeout=3)
        assert verify_response.status_code == 200
        assert verifier.calls == ["new-race-key"]
        assert verify_response.json()["cached"] is False
        provider = client.get("/api/v1/admin/providers").json()["providers"][0]
        assert provider["credential"]["verification_status"] == "healthy"
        assert provider["verification"]["current"] is True

        # Delete holds the same boundary through external removal. The queued
        # verifier observes no key and cannot call the provider with a key that
        # is being deleted.
        delete_lock = TrackingLock()
        app.state.provider_operation_locks["fred"] = delete_lock
        store.prepare("delete")
        delete = pool.submit(
            lambda: client.delete(
                write_route,
                headers=operator_headers("credential.delete"),
            )
        )
        assert store.operation_entered.wait(timeout=2)
        verify_after_delete = pool.submit(
            lambda: client.post(
                verify_route,
                json={},
                headers=operator_headers("provider.verify"),
            )
        )
        assert delete_lock.second_attempted.wait(timeout=2)
        assert verifier.calls == ["new-race-key"]
        store.operation_release.set()
        delete_response = delete.result(timeout=3)
        missing_response = verify_after_delete.result(timeout=3)
        assert delete_response.status_code == 200
        assert delete_response.json()["deleted"] is True
        assert missing_response.status_code == 200
        assert missing_response.json()["verification"]["status"] == "not_configured"
        assert verifier.calls == ["new-race-key"]
        provider = client.get("/api/v1/admin/providers").json()["providers"][0]
        assert provider["credential"]["status"] == "missing"
        assert provider["verification"] is None

    with connect(database, read_only=True) as connection:
        provider_revision = connection.execute(
            "SELECT credential_revision FROM operator_providers WHERE provider_key = 'fred'"
        ).fetchone()[0]
        latest_revision = connection.execute(
            """
            SELECT credential_revision FROM provider_verifications
            WHERE provider_key = 'fred' ORDER BY checked_at DESC, rowid DESC LIMIT 1
            """
        ).fetchone()[0]
        assert provider_revision == latest_revision == 3


def test_legacy_demo_gets_complete_versioned_v3_fixture_on_reseed(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "catalog-backfill.db")
    legacy_dataset_id = "demo-market-2026-08-21-v2"
    legacy_snapshot_id = "demo-2026-08-21-v2"
    with connect(database) as connection:
        connection.execute(
            """
            INSERT INTO dataset_snapshots (
                id, as_of, created_at, mode, data_classification, is_live,
                is_demo, status, immutable, source_manifest_json
            ) VALUES (?, ?, ?, 'demo', 'synthetic', 0, 1, 'legacy_demo', 0, '{}')
            """,
            (legacy_dataset_id, "2026-08-21T20:00:00Z", "2026-08-21T20:05:00Z"),
        )
        connection.execute(
            """
            INSERT INTO desk_snapshots (
                id, dataset_snapshot_id, as_of, created_at, mode,
                data_classification, is_live, is_demo, status, immutable,
                seed_revision, title, subtitle, disclaimer, regime_label,
                regime_summary, recommendation_posture,
                recommendation_summary, change_summary
            ) VALUES (?, ?, ?, ?, 'demo', 'synthetic', 0, 1, 'legacy_demo', 0,
                      'legacy-v3', 'Legacy demo', 'Before operator catalog',
                      'Synthetic only', 'Unknown', 'No conclusion', 'observe',
                      'No recommendation', 'No change')
            """,
            (
                legacy_snapshot_id,
                legacy_dataset_id,
                "2026-08-21T20:00:00Z",
                "2026-08-21T20:05:00Z",
            ),
        )
        connection.executemany(
            """
            INSERT INTO data_assets (
                asset_key, label, kind, classification, row_count, status,
                dataset_snapshot_id, detail, updated_at
            ) VALUES (?, ?, ?, 'synthetic', ?, 'ready', ?, 'Legacy v2 row.', ?)
            """,
            [
                ("demo_daily_bars", "Old bars", "price_bars", 12, legacy_dataset_id, "2026-08-21T20:05:00Z"),
                ("demo_chart_events", "Old events", "symbol_events", 1, legacy_dataset_id, "2026-08-21T20:05:00Z"),
                ("demo_tlt_options", "Old options", "option_chain_fixture", 1, legacy_dataset_id, "2026-08-21T20:05:00Z"),
            ],
        )
        connection.execute(
            "UPDATE dataset_snapshots SET immutable = 1 WHERE id = ?",
            (legacy_dataset_id,),
        )
        connection.execute(
            "UPDATE desk_snapshots SET immutable = 1 WHERE id = ?",
            (legacy_snapshot_id,),
        )
    _, created = seed_demo(database)
    assert created is True
    with connect(database, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM data_assets").fetchone()[0] == 6
        # 2 synthetic demo fixtures + 5 real engine algorithms + 2 honest
        # draft placeholders with no implementation yet (sentiment_text_mining,
        # fundamental_analysis), all registered in schema.sql. Of the 5 real
        # ones, macro_regime_composite and cross_sectional_momentum each carry
        # 2 versions (naive-v1, naive-v2); macd_rsi_single_name_timing carries
        # 3 (naive-v1, naive-v2, naive-v3 -- naive-v3 real, wired code:
        # macd_crossover retired for no real entry edge, 0.29; replaced by
        # short_term_reversal_entry, real cost-checked evidence,
        # backend/engine/timing/backtest_v3.py). naive-v2's own 3 components
        # (macd_crossover, rsi_overbought_exit, short_term_reversal_entry
        # draft) stay registered as an unedited historical record; naive-v3
        # re-registers its own 2 (short_term_reversal_entry now active,
        # rsi_overbought_exit carried forward) -- 3 lifecycle events record
        # the retirement, the draft registration, and the naive-v3 promotion.
        # cross_sectional_momentum's naive-v2 registers one more component:
        # 12m_skip1m, the first research-loop smoke-test candidate
        # (status='draft', not yet promoted into the live blend).
        assert connection.execute("SELECT COUNT(*) FROM strategies").fetchone()[0] == 9
        assert connection.execute("SELECT COUNT(*) FROM strategy_versions").fetchone()[0] == 11
        assert connection.execute("SELECT COUNT(*) FROM strategy_diagnostics").fetchone()[0] == 24
        assert connection.execute("SELECT COUNT(*) FROM strategy_lifecycle_events").fetchone()[0] == 13
        assert connection.execute("SELECT COUNT(*) FROM strategy_components").fetchone()[0] == 6
        synthetic_assets = connection.execute(
            """
            SELECT asset_key, dataset_snapshot_id, row_count
            FROM data_assets WHERE classification = 'synthetic'
            ORDER BY asset_key
            """
        ).fetchall()
        assert [row["asset_key"] for row in synthetic_assets] == [
            "demo_chart_events",
            "demo_daily_bars",
            "demo_tlt_options",
        ]
        assert {row["dataset_snapshot_id"] for row in synthetic_assets} == {
            DEMO_DATASET_ID
        }
        assert connection.execute(
            "SELECT COUNT(*) FROM symbol_signals WHERE snapshot_id = ?",
            (DEMO_SNAPSHOT_ID,),
        ).fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM desk_snapshots").fetchone()[0] == 2


def test_application_catalog_upsert_refreshes_definitions_but_preserves_enabled(
    tmp_path: Path,
) -> None:
    database = initialize_database(tmp_path / "catalog-upsert.db")
    with connect(database) as connection:
        connection.execute(
            """
            UPDATE operator_providers
            SET enabled = 0, name = 'Stale provider name',
                credential_name = 'legacy_credential', credential_revision = 5,
                verification_ttl_seconds = 1209600
            WHERE provider_key = 'fred'
            """
        )
        connection.execute(
            "UPDATE pipeline_definitions SET enabled = 0, version = 'old' WHERE pipeline_key = 'daily_desk'"
        )
        connection.execute(
            """
            UPDATE pipeline_stage_definitions SET description = 'stale'
            WHERE pipeline_key = 'daily_desk' AND stage_key = 'fetch_data'
            """
        )
    initialize_database(database)
    with connect(database, read_only=True) as connection:
        provider = connection.execute(
            """
            SELECT enabled, name, credential_name, credential_revision,
                   verification_ttl_seconds, attribution_notice
            FROM operator_providers WHERE provider_key = 'fred'
            """
        ).fetchone()
        assert tuple(provider[:5]) == (
            0,
            "FRED / ALFRED",
            "fred_api_key",
            6,
            31536000,
        )
        assert "not endorsed or certified" in provider["attribution_notice"]
        pipeline = connection.execute(
            "SELECT enabled, version FROM pipeline_definitions WHERE pipeline_key = 'daily_desk'"
        ).fetchone()
        assert tuple(pipeline) == (0, "0.1.0")
        stage = connection.execute(
            """
            SELECT description FROM pipeline_stage_definitions
            WHERE pipeline_key = 'daily_desk' AND stage_key = 'fetch_data'
            """
        ).fetchone()[0]
        assert "point-in-time macro" in stage
    initialize_database(database)
    with connect(database, read_only=True) as connection:
        assert connection.execute(
            "SELECT credential_revision FROM operator_providers WHERE provider_key = 'fred'"
        ).fetchone()[0] == 6


def test_old_provider_catalog_adds_columns_before_application_upsert(
    tmp_path: Path,
) -> None:
    database = tmp_path / "old-provider-catalog.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE operator_providers (
                provider_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                required INTEGER NOT NULL,
                credential_label TEXT,
                credential_name TEXT,
                environment_variable TEXT,
                documentation_url TEXT,
                signup_url TEXT,
                terms_url TEXT,
                instructions TEXT NOT NULL,
                capabilities_json TEXT NOT NULL DEFAULT '[]',
                verifier_kind TEXT,
                credential_revision INTEGER NOT NULL DEFAULT 0,
                verification_cooldown_seconds INTEGER NOT NULL DEFAULT 900,
                sort_order INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO operator_providers VALUES (
                'fred', 'Legacy FRED', 'macro', 'Legacy definition', 0, 1,
                'FRED key', 'fred_api_key', 'HEAE_FRED_API_KEY', NULL, NULL,
                NULL, 'Legacy instructions', '[]', 'fred_v2', 3, 900, 10,
                '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z'
            );
            """
        )
    initialize_database(database)
    with connect(database, read_only=True) as connection:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(operator_providers)"
            ).fetchall()
        }
        assert {"attribution_notice", "verification_ttl_seconds"} <= columns
        provider = connection.execute(
            """
            SELECT enabled, name, credential_revision,
                   verification_ttl_seconds, attribution_notice
            FROM operator_providers WHERE provider_key = 'fred'
            """
        ).fetchone()
        assert provider["enabled"] == 0
        assert provider["name"] == "FRED / ALFRED"
        assert provider["credential_revision"] == 3
        assert provider["verification_ttl_seconds"] == 31536000
        assert "not endorsed or certified" in provider["attribution_notice"]


def test_extended_catalog_ttl_preserves_recorded_expiry_until_fresh_verification(
    tmp_path: Path,
) -> None:
    database = initialize_database(tmp_path / "ttl-policy-upgrade.db")
    with connect(database) as connection:
        revision = connection.execute(
            "SELECT credential_revision FROM operator_providers WHERE provider_key = 'fred'"
        ).fetchone()[0]
        connection.execute(
            """
            UPDATE operator_providers
            SET verification_ttl_seconds = 604800
            WHERE provider_key = 'fred'
            """
        )
        connection.execute(
            """
            INSERT INTO provider_verifications (
                verification_id, provider_key, checked_at, expires_at, status,
                message, credential_revision, runtime_id, credential_source
            ) VALUES (
                'old-seven-day-ttl', 'fred', '2030-01-01T00:00:00.000000Z',
                '2030-01-08T00:00:00.000000Z', 'healthy',
                'Healthy under the former seven-day policy.', ?, 'old-runtime', 'keyring'
            )
            """,
            (revision,),
        )

    # Installing the one-year policy must not rewrite or extend immutable
    # verification history. The old result remains expired until a real fresh
    # smoke test establishes validity under the new policy.
    initialize_database(database)
    store = MemorySecretStore(
        values={"fred_api_key": SecretValue("ttl-policy-key", "keyring", True)}
    )
    app = create_app(
        database,
        secret_store=store,
        provider_verifiers={"fred_v2": FakeVerifier()},
        now=lambda: datetime(2030, 1, 9, tzinfo=timezone.utc),
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52000),
    ) as client:
        before_refresh = client.get("/api/v1/admin/providers").json()
        provider = before_refresh["providers"][0]
        assert provider["credential"]["verification_ttl_seconds"] == 31536000
        assert provider["credential"]["cooldown_seconds"] == 900
        assert provider["credential"]["status"] == "expired"
        assert provider["credential"]["verification_policy_refresh_required"] is True
        assert before_refresh["roadmap"]["summary"]["verifications_needed_now"] == 1
        assert "adopt the one-year health policy" in before_refresh["roadmap"]["next_action"]
        assert provider["verification"] is None
        assert provider["last_verification"]["expires_at"] == (
            "2030-01-08T00:00:00.000000Z"
        )
        assert provider["last_verification"]["effective_expires_at"] == (
            "2030-01-08T00:00:00.000000Z"
        )

        fresh = client.post(
            "/api/v1/admin/providers/fred/verify",
            json={},
            headers=operator_headers("provider.verify"),
        ).json()
        assert fresh["cached"] is False
        assert fresh["verification"]["expires_at"] == (
            "2031-01-09T00:00:00.000000Z"
        )
        refreshed = client.get("/api/v1/admin/providers").json()
        current = refreshed["providers"][0]
        assert current["credential"]["status"] == "verified"
        assert current["credential"]["cooldown_remaining_seconds"] == 900
        assert current["credential"]["verification_policy_refresh_required"] is False
        assert refreshed["roadmap"]["summary"]["verifications_needed_now"] == 0

    with connect(database, read_only=True) as connection:
        history = connection.execute(
            """
            SELECT verification_id, checked_at, expires_at
            FROM provider_verifications
            ORDER BY rowid
            """
        ).fetchall()
    assert len(history) == 2
    assert tuple(history[0]) == (
        "old-seven-day-ttl",
        "2030-01-01T00:00:00.000000Z",
        "2030-01-08T00:00:00.000000Z",
    )


def test_shortened_current_ttl_caps_health_without_rewriting_history(
    tmp_path: Path,
) -> None:
    database = initialize_database(tmp_path / "ttl-policy-cap.db")
    with connect(database) as connection:
        revision = connection.execute(
            "SELECT credential_revision FROM operator_providers WHERE provider_key = 'fred'"
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO provider_verifications (
                verification_id, provider_key, checked_at, expires_at, status,
                message, credential_revision, runtime_id, credential_source
            ) VALUES (
                'old-one-year-ttl', 'fred', '2030-01-01T00:00:00.000000Z',
                '2031-01-01T00:00:00.000000Z', 'healthy',
                'Healthy under a one-year policy.', ?, 'old-runtime', 'keyring'
            )
            """,
            (revision,),
        )
    app = create_app(
        database,
        secret_store=MemorySecretStore(
            values={"fred_api_key": SecretValue("ttl-cap-key", "keyring", True)}
        ),
        provider_verifiers={"fred_v2": FakeVerifier()},
        now=lambda: datetime(2030, 1, 9, tzinfo=timezone.utc),
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 52000),
    ) as client:
        # App startup refreshes the application-owned catalog. Apply a
        # hypothetical later shortening after that refresh to exercise the
        # fail-closed cap.
        with connect(database) as connection:
            connection.execute(
                """
                UPDATE operator_providers
                SET verification_ttl_seconds = 604800
                WHERE provider_key = 'fred'
                """
            )
        provider = client.get("/api/v1/admin/providers").json()["providers"][0]
    assert provider["credential"]["status"] == "expired"
    assert provider["last_verification"]["expires_at"] == (
        "2031-01-01T00:00:00.000000Z"
    )
    assert provider["last_verification"]["effective_expires_at"] == (
        "2030-01-08T00:00:00.000000Z"
    )
    with connect(database, read_only=True) as connection:
        stored_expiry = connection.execute(
            """
            SELECT expires_at FROM provider_verifications
            WHERE verification_id = 'old-one-year-ttl'
            """
        ).fetchone()[0]
    assert stored_expiry == "2031-01-01T00:00:00.000000Z"


def test_terminal_history_and_artifact_manifests_are_immutable(
    admin_context: tuple[Path, TestClient, MemorySecretStore, FakeVerifier],
) -> None:
    database, client, _, _ = admin_context
    verification = client.post(
        "/api/v1/admin/providers/fred/verify",
        json={},
        headers=operator_headers("provider.verify"),
    ).json()["verification"]
    run = client.post(
        "/api/v1/admin/pipeline/runs",
        json={"dry_run": True},
        headers=operator_headers("pipeline.run"),
    ).json()["run"]
    with connect(database) as connection:
        connection.execute(
            """
            INSERT INTO research_runs (
                research_run_id, strategy_key, strategy_version,
                dataset_snapshot_id, parameters_json, status, summary
            ) VALUES ('immutable-research', 'state_conditioned_exposure',
                      '0.1.0-demo', ?, '{}', 'completed', 'Completed fixture.')
            """,
            (DEMO_DATASET_ID,),
        )
        connection.execute(
            """
            INSERT INTO research_artifacts (
                research_run_id, artifact_key, relative_path, media_type,
                sha256, size_bytes, curated, created_at
            ) VALUES ('immutable-research', 'summary', 'artifacts/runs/immutable-research/summary.md',
                      'text/markdown', ?, 10, 1, ?)
            """,
            ("a" * 64, "2026-08-24T12:00:00Z"),
        )
        connection.commit()
        mutations = [
            (
                "UPDATE provider_verifications SET message = 'changed' WHERE verification_id = ?",
                (verification["id"],),
            ),
            (
                "UPDATE pipeline_runs SET summary = 'changed' WHERE run_id = ?",
                (run["id"],),
            ),
            (
                "UPDATE pipeline_stage_runs SET message = 'changed' WHERE run_id = ?",
                (run["id"],),
            ),
            (
                "DELETE FROM pipeline_runs WHERE run_id = ?",
                (run["id"],),
            ),
            (
                "UPDATE strategy_lifecycle_events SET reason = 'changed' WHERE event_id = 'demo-state-added'",
                (),
            ),
            (
                "UPDATE research_runs SET summary = 'changed' WHERE research_run_id = 'immutable-research'",
                (),
            ),
            (
                "UPDATE research_artifacts SET size_bytes = 11 WHERE research_run_id = 'immutable-research'",
                (),
            ),
            (
                "DELETE FROM research_artifacts WHERE research_run_id = 'immutable-research'",
                (),
            ),
        ]
        for sql, values in mutations:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(sql, values)
            connection.rollback()


def test_desk_cannot_publish_without_sealed_dataset(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "publish-guard.db")
    with connect(database) as connection:
        connection.execute(
            """
            INSERT INTO dataset_snapshots (
                id, as_of, created_at, mode, data_classification, is_live,
                is_demo, status, immutable, source_manifest_json
            ) VALUES ('draft-data', ?, ?, 'research', 'real', 0, 0, 'draft', 0, '{}')
            """,
            ("2026-08-24T00:00:00Z", "2026-08-24T00:01:00Z"),
        )
        connection.execute(
            """
            INSERT INTO desk_snapshots (
                id, dataset_snapshot_id, as_of, created_at, mode,
                data_classification, is_live, is_demo, status, immutable,
                seed_revision, title, subtitle, disclaimer, regime_label,
                regime_summary, recommendation_posture,
                recommendation_summary, change_summary
            ) VALUES ('draft-desk', 'draft-data', ?, ?, 'research', 'real', 0, 0,
                      'draft', 0, 'test', 'Draft', 'Draft', 'Draft', 'Unknown',
                      'None', 'observe', 'None', 'None')
            """,
            ("2026-08-24T00:00:00Z", "2026-08-24T00:01:00Z"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE desk_snapshots SET immutable = 1 WHERE id = 'draft-desk'"
            )
        connection.rollback()

        # Direct publication cannot bypass the draft-to-sealed transition guard.
        columns = [
            item["name"]
            for item in connection.execute("PRAGMA table_info(desk_snapshots)")
        ]
        source = dict(
            connection.execute(
                "SELECT * FROM desk_snapshots WHERE id = 'draft-desk'"
            ).fetchone()
        )
        for desk_id, dataset_id in (
            ("sealed-with-null-data", None),
            ("sealed-with-draft-data", "draft-data"),
        ):
            values = {
                **source,
                "id": desk_id,
                "dataset_snapshot_id": dataset_id,
                "immutable": 1,
            }
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    f"INSERT INTO desk_snapshots ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' for _ in columns)})",
                    tuple(values[column] for column in columns),
                )
            connection.rollback()

        connection.execute(
            "UPDATE dataset_snapshots SET immutable = 1 WHERE id = 'draft-data'"
        )
        connection.commit()
        mismatches = (
            ("data_classification", "synthetic"),
            ("is_live", 1),
            ("is_demo", 1),
        )
        for field, mismatched_value in mismatches:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    f"UPDATE desk_snapshots SET {field} = ?, immutable = 1 "
                    "WHERE id = 'draft-desk'",
                    (mismatched_value,),
                )
            connection.rollback()

            values = {
                **source,
                "id": f"sealed-mismatch-{field}",
                "immutable": 1,
                field: mismatched_value,
            }
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    f"INSERT INTO desk_snapshots ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' for _ in columns)})",
                    tuple(values[column] for column in columns),
                )
            connection.rollback()

        # Matching sealed provenance remains the successful publication path.
        connection.execute(
            "UPDATE desk_snapshots SET immutable = 1 WHERE id = 'draft-desk'"
        )
        connection.commit()


def test_migration_rejects_dangling_published_provenance(tmp_path: Path) -> None:
    desk_database = tmp_path / "dangling-desk.db"
    seed_demo(desk_database)
    with sqlite3.connect(desk_database) as legacy:
        legacy.executescript(
            """
            PRAGMA foreign_keys = OFF;
            DROP TRIGGER IF EXISTS desk_snapshots_are_immutable_update;
            DROP TRIGGER IF EXISTS desk_snapshot_publish_requires_sealed_dataset_update;
            UPDATE desk_snapshots
            SET dataset_snapshot_id = 'missing-legacy-dataset'
            WHERE id = 'demo-2026-08-21-v3';
            """
        )
    with pytest.raises(
        sqlite3.IntegrityError,
        match="published desk snapshots require sealed dataset provenance",
    ):
        initialize_database(desk_database)

    research_database = tmp_path / "dangling-research.db"
    seed_demo(research_database)
    with sqlite3.connect(research_database) as legacy:
        legacy.executescript(
            """
            PRAGMA foreign_keys = OFF;
            DROP TRIGGER IF EXISTS research_completed_requires_sealed_dataset_insert;
            INSERT INTO research_runs (
                research_run_id, strategy_key, strategy_version,
                dataset_snapshot_id, parameters_json, status, summary
            ) VALUES (
                'dangling-research', 'state_conditioned_exposure',
                '0.1.0-demo', 'missing-legacy-dataset', '{}', 'completed',
                'Legacy result with broken provenance.'
            );
            """
        )
    with pytest.raises(
        sqlite3.IntegrityError,
        match="completed research runs require sealed dataset provenance",
    ):
        initialize_database(research_database)
