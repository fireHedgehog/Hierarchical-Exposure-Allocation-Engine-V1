from __future__ import annotations

import sqlite3

import pytest

import backend.readiness_repository as readiness


def test_presentation_rows_do_not_prove_revisioned_timing_or_cash_no_trade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE cross_section_rows (snapshot_id TEXT, symbol TEXT);
        CREATE TABLE symbol_signals (snapshot_id TEXT, symbol TEXT);
        CREATE TABLE position_candidates (
            snapshot_id TEXT, candidate_id TEXT, market_data_complete INTEGER,
            actionability TEXT, structure_type TEXT
        );
        CREATE TABLE position_legs (
            snapshot_id TEXT, candidate_id TEXT, instrument_type TEXT
        );
        INSERT INTO cross_section_rows VALUES ('real-desk', 'AAA');
        INSERT INTO cross_section_rows VALUES ('real-desk', 'BBB');
        INSERT INTO symbol_signals VALUES ('real-desk', 'AAA');
        INSERT INTO symbol_signals VALUES ('real-desk', 'BBB');
        """
    )
    desk = {"id": "real-desk", "created_at": "2026-08-24T12:00:00Z"}
    monkeypatch.setattr(
        readiness,
        "_qualifying_factor_snapshot",
        lambda _connection: (None, desk, 2, 2),
    )

    timing_status, timing_evidence = readiness._evaluate_symbol_timing_snapshot(
        connection, {}
    )
    assert timing_status == "action_required"
    assert timing_evidence[0]["status"] == "non_qualifying"
    assert "separately revisioned timing-model" in timing_evidence[0]["summary"]

    definition = {"implementation_status": "ready"}
    attempt = {
        "stage_status": "completed",
        "stage_message": "Instrument stage completed without a candidate.",
        "run_id": "instrument-run",
        "stage_finished_at": "2026-08-24T12:00:00Z",
        "stage_started_at": "2026-08-24T11:59:00Z",
        "requested_at": "2026-08-24T11:59:00Z",
        "desk_snapshot_id": "real-desk",
    }
    monkeypatch.setattr(
        readiness, "_stage_definition", lambda _connection, _key: definition
    )
    monkeypatch.setattr(
        readiness,
        "_instrument_attempt_and_desk",
        lambda _connection: (attempt, desk),
    )
    monkeypatch.setattr(
        readiness,
        "_unresolved_candidate_blockers",
        lambda _connection, _snapshot_id: 0,
    )

    cash_status, cash_evidence = readiness._evaluate_cash_expression_snapshot(
        connection, {}
    )
    assert cash_status == "action_required"
    cash_result = next(
        item for item in cash_evidence if item["kind"] == "cash_expression_result"
    )
    assert cash_result["status"] == "non_qualifying"
    assert "0 complete cash candidate" in cash_result["summary"]

    connection.close()
