from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import Any


def _json(value: str | None) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None


def _readiness_evidence(
    kind: str,
    summary: str,
    *,
    status: str = "missing",
    record_id: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "record_id": record_id,
        "status": status,
        "observed_at": observed_at,
        "summary": summary,
    }


def _stage_definition(
    connection: sqlite3.Connection, stage_key: str
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM pipeline_stage_definitions
        WHERE pipeline_key = 'daily_desk' AND stage_key = ?
        """,
        (stage_key,),
    ).fetchone()


def _latest_stage_attempt(
    connection: sqlite3.Connection, stage_key: str
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT stage.stage_key, stage.status AS stage_status,
               stage.started_at AS stage_started_at,
               stage.finished_at AS stage_finished_at,
               stage.records_read, stage.records_written,
               stage.message AS stage_message, stage.error_code,
               run.run_id, run.status AS run_status, run.requested_at,
               run.dataset_snapshot_id, run.desk_snapshot_id
        FROM pipeline_stage_runs AS stage
        JOIN pipeline_runs AS run ON run.run_id = stage.run_id
        WHERE run.pipeline_key = 'daily_desk'
          AND run.dry_run = 0
          AND stage.stage_key = ?
        ORDER BY run.requested_at DESC, run.rowid DESC
        LIMIT 1
        """,
        (stage_key,),
    ).fetchone()


def _stage_evidence(
    stage_key: str, attempt: sqlite3.Row | None
) -> dict[str, Any]:
    if attempt is None:
        return _readiness_evidence(
            "pipeline_stage_run",
            f"No non-dry {stage_key} stage attempt is recorded.",
        )
    qualifies = attempt["stage_status"] == "completed"
    return _readiness_evidence(
        "pipeline_stage_run",
        f"{stage_key} is {attempt['stage_status']}: {attempt['stage_message']}",
        status="qualifying" if qualifies else "non_qualifying",
        record_id=f"{attempt['run_id']}:{stage_key}",
        observed_at=(
            attempt["stage_finished_at"]
            or attempt["stage_started_at"]
            or attempt["requested_at"]
        ),
    )


def _definition_evidence(
    stage_key: str, definition: sqlite3.Row | None
) -> dict[str, Any]:
    if definition is None:
        return _readiness_evidence(
            "pipeline_stage_definition",
            f"The {stage_key} stage is not registered.",
        )
    qualifies = definition["implementation_status"] == "ready"
    return _readiness_evidence(
        "pipeline_stage_definition",
        f"{stage_key} implementation is {definition['implementation_status']}.",
        status="qualifying" if qualifies else "non_qualifying",
        record_id=f"daily_desk:{stage_key}",
    )


def _real_dataset(
    connection: sqlite3.Connection,
    dataset_snapshot_id: str | None,
    *,
    immutable: bool,
) -> sqlite3.Row | None:
    if dataset_snapshot_id is None:
        return None
    immutable_clause = "AND immutable = 1" if immutable else ""
    return connection.execute(
        f"""
        SELECT * FROM dataset_snapshots
        WHERE id = ?
          AND is_demo = 0
          AND data_classification = 'real'
          {immutable_clause}
        """,
        (dataset_snapshot_id,),
    ).fetchone()


def _real_desk(
    connection: sqlite3.Connection, desk_snapshot_id: str | None
) -> sqlite3.Row | None:
    if desk_snapshot_id is None:
        return None
    return connection.execute(
        """
        SELECT * FROM desk_snapshots
        WHERE id = ? AND immutable = 1 AND is_demo = 0
          AND data_classification = 'real'
        """,
        (desk_snapshot_id,),
    ).fetchone()


def _dataset_evidence(
    dataset: sqlite3.Row | None,
    dataset_snapshot_id: str | None,
    *,
    label: str,
) -> dict[str, Any]:
    if dataset is None:
        return _readiness_evidence(
            "dataset_snapshot",
            f"No qualifying immutable non-demo real dataset supports {label}.",
            status="non_qualifying" if dataset_snapshot_id else "missing",
            record_id=dataset_snapshot_id,
        )
    return _readiness_evidence(
        "dataset_snapshot",
        f"Dataset {dataset['id']} is immutable, non-demo, and real.",
        status="qualifying",
        record_id=dataset["id"],
        observed_at=dataset["created_at"],
    )


def _desk_evidence(
    desk: sqlite3.Row | None, desk_snapshot_id: str | None, summary: str
) -> dict[str, Any]:
    if desk is None:
        return _readiness_evidence(
            "desk_snapshot",
            "No qualifying immutable non-demo real desk snapshot is recorded.",
            status="non_qualifying" if desk_snapshot_id else "missing",
            record_id=desk_snapshot_id,
        )
    return _readiness_evidence(
        "desk_snapshot",
        summary,
        status="qualifying",
        record_id=desk["id"],
        observed_at=desk["created_at"],
    )


def _evaluate_provider_access_fred(
    _connection: sqlite3.Connection, providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    provider = providers.get("fred")
    if provider is None:
        return "action_required", [
            _readiness_evidence(
                "provider_verification", "FRED is not registered."
            )
        ]
    credential = provider["credential"]
    verification = provider.get("verification")
    last = provider.get("last_verification")
    if (
        credential.get("status") == "verified"
        and credential.get("verification_status") == "healthy"
        and verification is not None
    ):
        return "passed", [
            _readiness_evidence(
                "provider_verification",
                "The current FRED credential has a healthy, unexpired smoke verification.",
                status="qualifying",
                record_id=verification.get("id"),
                observed_at=verification.get("checked_at"),
            )
        ]
    if not credential.get("configured"):
        state = "action_required"
        summary = "No FRED credential is configured."
    elif credential.get("status") == "unhealthy":
        state = "failed"
        summary = "The current FRED credential has a non-healthy verification."
    else:
        state = "action_required"
        summary = (
            "The configured FRED credential does not have a current healthy "
            f"verification ({credential.get('status') or 'unverified'})."
        )
    return state, [
        _readiness_evidence(
            "provider_verification",
            summary,
            status="non_qualifying" if last else "missing",
            record_id=last.get("id") if last else None,
            observed_at=last.get("checked_at") if last else None,
        )
    ]


def _evaluate_macro_pit_ingestion(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    definition = _stage_definition(connection, "fetch_data")
    attempt = _latest_stage_attempt(connection, "fetch_data")
    evidence = [
        _definition_evidence("fetch_data", definition),
        _stage_evidence("fetch_data", attempt),
    ]
    if definition is None or definition["implementation_status"] != "ready":
        return "action_required", evidence
    if attempt is None:
        return "action_required", evidence
    if attempt["stage_status"] != "completed":
        return "failed", evidence
    assets = connection.execute(
        """
        SELECT asset.*, dataset.is_demo AS dataset_is_demo,
               dataset.data_classification AS dataset_classification
        FROM data_assets AS asset
        LEFT JOIN dataset_snapshots AS dataset
          ON dataset.id = asset.dataset_snapshot_id
        WHERE asset.provider_key = 'fred'
        ORDER BY asset.updated_at DESC, asset.asset_key
        """
    ).fetchall()
    qualifying = [
        asset
        for asset in assets
        if asset["classification"] == "real"
        and asset["status"] == "ready"
        and asset["row_count"] > 0
        and asset["dataset_snapshot_id"] == attempt["dataset_snapshot_id"]
        and asset["dataset_is_demo"] == 0
        and asset["dataset_classification"] == "real"
    ]
    if qualifying:
        evidence.append(
            _readiness_evidence(
                "data_inventory",
                f"{len(qualifying)} ready real FRED inventory record(s) refer to dataset {attempt['dataset_snapshot_id']}.",
                status="qualifying",
                record_id=attempt["dataset_snapshot_id"],
                observed_at=max(asset["updated_at"] for asset in qualifying),
            )
        )
        return "passed", evidence
    evidence.append(
        _readiness_evidence(
            "data_inventory",
            "The completed fetch has no ready real FRED inventory with rows on its non-demo dataset.",
            status="non_qualifying" if assets else "missing",
            record_id=attempt["dataset_snapshot_id"],
        )
    )
    return "failed", evidence


def _evaluate_macro_validation_seal(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    definition = _stage_definition(connection, "validate_data")
    attempt = _latest_stage_attempt(connection, "validate_data")
    evidence = [
        _definition_evidence("validate_data", definition),
        _stage_evidence("validate_data", attempt),
    ]
    if definition is None or definition["implementation_status"] != "ready":
        return "action_required", evidence
    if attempt is None:
        return "action_required", evidence
    if attempt["stage_status"] != "completed":
        return "failed", evidence
    dataset = _real_dataset(
        connection, attempt["dataset_snapshot_id"], immutable=True
    )
    evidence.append(
        _dataset_evidence(
            dataset,
            attempt["dataset_snapshot_id"],
            label="macro validation",
        )
    )
    return ("passed" if dataset is not None else "failed"), evidence


def _evaluate_real_regime_snapshot(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    definition = _stage_definition(connection, "regime_filter")
    attempt = _latest_stage_attempt(connection, "regime_filter")
    evidence = [
        _definition_evidence("regime_filter", definition),
        _stage_evidence("regime_filter", attempt),
    ]
    if definition is None or definition["implementation_status"] != "ready":
        return "action_required", evidence
    if attempt is None:
        return "action_required", evidence
    if attempt["stage_status"] != "completed":
        return "failed", evidence
    desk = _real_desk(connection, attempt["desk_snapshot_id"])
    contributions = evidence_rows = 0
    if desk is not None:
        contributions = connection.execute(
            "SELECT COUNT(*) FROM regime_contributions WHERE snapshot_id = ?",
            (desk["id"],),
        ).fetchone()[0]
        evidence_rows = connection.execute(
            """
            SELECT COUNT(*) FROM regime_evidence
            WHERE snapshot_id = ?
              AND observed_at IS NOT NULL
              AND available_at IS NOT NULL
            """,
            (desk["id"],),
        ).fetchone()[0]
    qualifies = desk is not None and contributions > 0 and evidence_rows > 0
    evidence.append(
        _desk_evidence(
            desk if qualifies else None,
            attempt["desk_snapshot_id"],
            f"Desk {desk['id']} contains {contributions} regime contribution(s) and {evidence_rows} evidence record(s)."
            if desk is not None
            else "No qualifying real regime snapshot is recorded.",
        )
    )
    return ("passed" if qualifies else "failed"), evidence


def _evaluate_versioned_security_universe(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    active = connection.execute(
        "SELECT COUNT(*) FROM securities WHERE active = 1"
    ).fetchone()[0]
    return "action_required", [
        _readiness_evidence(
            "security_universe_revision",
            f"{active} active security record(s) exist, but no versioned point-in-time universe membership contract exists; demo symbols do not qualify.",
            status="non_qualifying" if active else "missing",
        )
    ]


def _evaluate_real_market_history(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    asset = connection.execute(
        """
        SELECT asset.*, dataset.immutable AS dataset_immutable,
               dataset.is_demo AS dataset_is_demo,
               dataset.data_classification AS dataset_classification,
               dataset.source_manifest_json
        FROM data_assets AS asset
        LEFT JOIN dataset_snapshots AS dataset
          ON dataset.id = asset.dataset_snapshot_id
        WHERE asset.kind = 'price_bars' AND asset.classification = 'real'
        ORDER BY asset.updated_at DESC, asset.asset_key
        LIMIT 1
        """
    ).fetchone()
    if asset is None or asset["row_count"] == 0 or asset["status"] == "missing":
        return "action_required", [
            _readiness_evidence(
                "market_data_inventory",
                "No populated real market-history inventory is recorded.",
                status="non_qualifying" if asset else "missing",
                record_id=asset["asset_key"] if asset else None,
                observed_at=asset["updated_at"] if asset else None,
            )
        ]
    manifest = _json(asset["source_manifest_json"] or "{}")
    has_adjustment_lineage = bool(
        isinstance(manifest, dict)
        and (
            manifest.get("corporate_actions")
            or manifest.get("adjustment_lineage")
        )
    )
    bars = 0
    if asset["dataset_snapshot_id"]:
        bars = connection.execute(
            "SELECT COUNT(*) FROM symbol_bars WHERE dataset_snapshot_id = ?",
            (asset["dataset_snapshot_id"],),
        ).fetchone()[0]
    qualifies = bool(
        asset["status"] == "ready"
        and asset["dataset_immutable"] == 1
        and asset["dataset_is_demo"] == 0
        and asset["dataset_classification"] == "real"
        and bars > 0
        and has_adjustment_lineage
    )
    return ("passed" if qualifies else "failed"), [
        _readiness_evidence(
            "market_data_inventory",
            f"Asset {asset['asset_key']} has {asset['row_count']} inventory rows, {bars} stored bars, status {asset['status']}, and {'has' if has_adjustment_lineage else 'lacks'} adjustment lineage.",
            status="qualifying" if qualifies else "non_qualifying",
            record_id=asset["asset_key"],
            observed_at=asset["updated_at"],
        )
    ]


def _qualifying_factor_snapshot(
    connection: sqlite3.Connection,
) -> tuple[sqlite3.Row | None, sqlite3.Row | None, int, int]:
    attempt = _latest_stage_attempt(connection, "factor_engine")
    if attempt is None or attempt["stage_status"] != "completed":
        return attempt, None, 0, 0
    desk = _real_desk(connection, attempt["desk_snapshot_id"])
    if desk is None:
        return attempt, None, 0, 0
    rows = connection.execute(
        "SELECT COUNT(*) FROM cross_section_rows WHERE snapshot_id = ?",
        (desk["id"],),
    ).fetchone()[0]
    factors = connection.execute(
        """
        SELECT COUNT(*) FROM factor_values
        WHERE snapshot_id = ?
          AND observed_at IS NOT NULL
          AND available_at IS NOT NULL
        """,
        (desk["id"],),
    ).fetchone()[0]
    return attempt, desk, rows, factors


def _evaluate_cross_sectional_snapshot(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    definition = _stage_definition(connection, "factor_engine")
    attempt, desk, rows, factors = _qualifying_factor_snapshot(connection)
    evidence = [
        _definition_evidence("factor_engine", definition),
        _stage_evidence("factor_engine", attempt),
    ]
    if definition is None or definition["implementation_status"] != "ready":
        return "action_required", evidence
    if attempt is None:
        return "action_required", evidence
    if attempt["stage_status"] != "completed":
        return "failed", evidence
    qualifies = desk is not None and rows >= 2 and factors >= rows
    evidence.append(
        _desk_evidence(
            desk if qualifies else None,
            attempt["desk_snapshot_id"],
            f"Desk {desk['id']} contains {rows} ranked securities and {factors} factor values."
            if desk is not None
            else "No qualifying real cross-sectional snapshot is recorded.",
        )
    )
    return ("passed" if qualifies else "failed"), evidence


def _evaluate_symbol_timing_snapshot(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    _attempt, desk, rows, _factors = _qualifying_factor_snapshot(connection)
    if desk is None or rows < 2:
        return "action_required", [
            _readiness_evidence(
                "symbol_signal_coverage",
                "No qualifying real ranked snapshot exists for symbol timing.",
            )
        ]
    signals = connection.execute(
        """
        SELECT COUNT(*) FROM cross_section_rows AS ranked
        JOIN symbol_signals AS signal
          ON signal.snapshot_id = ranked.snapshot_id
         AND signal.symbol = ranked.symbol
        WHERE ranked.snapshot_id = ?
        """,
        (desk["id"],),
    ).fetchone()[0]
    # The current symbol_signals table is a snapshot presentation. It does not
    # identify the separately revisioned timing model or model run that created
    # each state, so even complete presentation coverage cannot prove this gate.
    return "action_required", [
        _readiness_evidence(
            "symbol_signal_coverage",
            f"Desk {desk['id']} has signal-state presentation for {signals} of {rows} ranked securities, but no separately revisioned timing-model evidence contract exists.",
            status="non_qualifying",
            record_id=desk["id"],
            observed_at=desk["created_at"],
        )
    ]


def _evaluate_portfolio_allocation_snapshot(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    definition = _stage_definition(connection, "allocation_engine")
    attempt = _latest_stage_attempt(connection, "allocation_engine")
    evidence = [
        _definition_evidence("allocation_engine", definition),
        _stage_evidence("allocation_engine", attempt),
    ]
    if definition is None or definition["implementation_status"] != "ready":
        return "action_required", evidence
    if attempt is None:
        return "action_required", evidence
    if attempt["stage_status"] != "completed":
        return "failed", evidence
    desk = _real_desk(connection, attempt["desk_snapshot_id"])
    risk_nodes = 0
    if desk is not None:
        risk_nodes = connection.execute(
            """
            SELECT COUNT(*) FROM decision_nodes
            WHERE snapshot_id = ? AND node_type = 'risk_budget'
            """,
            (desk["id"],),
        ).fetchone()[0]
    qualifies = bool(
        desk is not None
        and desk["target_net_exposure"] is not None
        and desk["target_gross_exposure"] is not None
        and risk_nodes > 0
    )
    evidence.append(
        _desk_evidence(
            desk if qualifies else None,
            attempt["desk_snapshot_id"],
            f"Desk {desk['id']} records target net/gross exposure and {risk_nodes} risk-budget node(s)."
            if desk is not None
            else "No qualifying real allocation snapshot is recorded.",
        )
    )
    return ("passed" if qualifies else "failed"), evidence


def _instrument_attempt_and_desk(
    connection: sqlite3.Connection,
) -> tuple[sqlite3.Row | None, sqlite3.Row | None]:
    attempt = _latest_stage_attempt(connection, "instrument_engine")
    if attempt is None or attempt["stage_status"] != "completed":
        return attempt, None
    return attempt, _real_desk(connection, attempt["desk_snapshot_id"])


def _unresolved_candidate_blockers(
    connection: sqlite3.Connection, snapshot_id: str
) -> int:
    return connection.execute(
        """
        SELECT COUNT(*) FROM position_blockers
        WHERE snapshot_id = ? AND required = 1 AND resolved = 0
        """,
        (snapshot_id,),
    ).fetchone()[0]


def _evaluate_cash_expression_snapshot(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    definition = _stage_definition(connection, "instrument_engine")
    attempt, desk = _instrument_attempt_and_desk(connection)
    evidence = [
        _definition_evidence("instrument_engine", definition),
        _stage_evidence("instrument_engine", attempt),
    ]
    if definition is None or definition["implementation_status"] != "ready":
        return "action_required", evidence
    if attempt is None:
        return "action_required", evidence
    if attempt["stage_status"] != "completed":
        return "failed", evidence
    blockers = _unresolved_candidate_blockers(connection, desk["id"]) if desk else 0
    cash_candidates = 0
    if desk is not None:
        cash_candidates = connection.execute(
            """
            SELECT COUNT(*) FROM position_candidates AS candidate
            WHERE candidate.snapshot_id = ?
              AND candidate.market_data_complete = 1
              AND candidate.actionability NOT IN ('blocked', 'unavailable')
              AND lower(candidate.structure_type) IN (
                  'stock', 'equity', 'cash', 'long_stock', 'short_stock',
                  'cash_equity'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM position_legs AS leg
                  WHERE leg.snapshot_id = candidate.snapshot_id
                    AND leg.candidate_id = candidate.candidate_id
                    AND lower(leg.instrument_type) = 'option'
              )
            """,
            (desk["id"],),
        ).fetchone()[0]
    qualifies = desk is not None and cash_candidates > 0 and blockers == 0
    evidence.append(
        _readiness_evidence(
            "cash_expression_result",
            (
                f"Desk {desk['id']} has {cash_candidates} complete cash candidate(s) and {blockers} unresolved required blocker(s)."
                if desk is not None
                else "No qualifying real instrument snapshot is recorded."
            ),
            status="qualifying" if qualifies else ("non_qualifying" if desk else "missing"),
            record_id=desk["id"] if desk else attempt["desk_snapshot_id"],
            observed_at=desk["created_at"] if desk else None,
        )
    )
    # Absence of a candidate is not silently interpreted as no-trade. A future
    # explicit no-trade record can satisfy this gate without manufacturing a
    # position; until then, a completed stage with no cash result needs action.
    if qualifies:
        return "passed", evidence
    return ("failed" if cash_candidates or blockers else "action_required"), evidence


def _evaluate_options_expression_snapshot(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    definition = _stage_definition(connection, "instrument_engine")
    attempt, desk = _instrument_attempt_and_desk(connection)
    asset = connection.execute(
        """
        SELECT asset.*, dataset.immutable AS dataset_immutable,
               dataset.is_demo AS dataset_is_demo,
               dataset.data_classification AS dataset_classification
        FROM data_assets AS asset
        LEFT JOIN dataset_snapshots AS dataset
          ON dataset.id = asset.dataset_snapshot_id
        WHERE asset.kind LIKE '%option%' AND asset.classification = 'real'
        ORDER BY asset.updated_at DESC, asset.asset_key
        LIMIT 1
        """
    ).fetchone()
    if asset is None or asset["row_count"] == 0 or asset["status"] == "missing":
        state = "action_required"
        qualifies_asset = False
    else:
        qualifies_asset = bool(
            asset["status"] == "ready"
            and asset["dataset_immutable"] == 1
            and asset["dataset_is_demo"] == 0
            and asset["dataset_classification"] == "real"
            and desk is not None
            and asset["dataset_snapshot_id"] == desk["dataset_snapshot_id"]
        )
        state = "failed"
    blockers = _unresolved_candidate_blockers(connection, desk["id"]) if desk else 0
    incomplete_options = 0
    if desk is not None:
        incomplete_options = connection.execute(
            """
            SELECT COUNT(DISTINCT candidate.candidate_id)
            FROM position_candidates AS candidate
            JOIN position_legs AS leg
              ON leg.snapshot_id = candidate.snapshot_id
             AND leg.candidate_id = candidate.candidate_id
            WHERE candidate.snapshot_id = ?
              AND lower(leg.instrument_type) = 'option'
              AND candidate.market_data_complete = 0
            """,
            (desk["id"],),
        ).fetchone()[0]
    stage_ok = bool(
        definition is not None
        and definition["implementation_status"] == "ready"
        and attempt is not None
        and attempt["stage_status"] == "completed"
    )
    qualifies = qualifies_asset and stage_ok and blockers == 0 and incomplete_options == 0
    if qualifies:
        state = "passed"
    elif attempt is not None and attempt["stage_status"] in {"failed", "blocked"}:
        state = "failed"
    evidence = [
        _definition_evidence("instrument_engine", definition),
        _stage_evidence("instrument_engine", attempt),
        _readiness_evidence(
            "option_data_inventory",
            (
                f"Asset {asset['asset_key']} has {asset['row_count']} rows and status {asset['status']}; "
                f"{incomplete_options} option candidate(s) have incomplete market data and {blockers} required blocker(s) remain."
                if asset is not None
                else "No real option-chain inventory is recorded."
            ),
            status="qualifying" if qualifies else ("non_qualifying" if asset else "missing"),
            record_id=asset["asset_key"] if asset else None,
            observed_at=asset["updated_at"] if asset else None,
        ),
    ]
    return state, evidence


def _evaluate_walk_forward_research(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    run = connection.execute(
        """
        SELECT research.*, dataset.created_at AS dataset_created_at
        FROM research_runs AS research
        JOIN dataset_snapshots AS dataset
          ON dataset.id = research.dataset_snapshot_id
        WHERE research.status = 'completed'
          AND dataset.immutable = 1
          AND dataset.is_demo = 0
          AND dataset.data_classification = 'real'
        ORDER BY research.finished_at DESC, research.started_at DESC,
                 research.rowid DESC
        LIMIT 1
        """
    ).fetchone()
    if run is None:
        return "action_required", [
            _readiness_evidence(
                "research_run",
                "No completed research run on an immutable non-demo real dataset is recorded.",
            )
        ]
    diagnostics = connection.execute(
        """
        SELECT metric_key FROM strategy_diagnostics
        WHERE strategy_key = ? AND version = ?
          AND metric_key IN ('decay_rate', 'information_coefficient', 'sharpe')
          AND value IS NOT NULL
          AND status NOT IN ('unavailable', 'missing')
        """,
        (run["strategy_key"], run["strategy_version"]),
    ).fetchall()
    parameters = _json(run["parameters_json"])
    parameter_evidence = bool(
        isinstance(parameters, dict)
        and parameters.get("point_in_time") is True
        and parameters.get("cost_model")
        and parameters.get("benchmark")
        and parameters.get("uncertainty_method")
    )
    metric_keys = {row["metric_key"] for row in diagnostics}
    qualifies = parameter_evidence and metric_keys == {
        "decay_rate",
        "information_coefficient",
        "sharpe",
    }
    return ("passed" if qualifies else "failed"), [
        _readiness_evidence(
            "research_run",
            f"Research run {run['research_run_id']} has {len(metric_keys)}/3 required diagnostics and {'complete' if parameter_evidence else 'incomplete'} point-in-time/cost/baseline/uncertainty parameters.",
            status="qualifying" if qualifies else "non_qualifying",
            record_id=run["research_run_id"],
            observed_at=run["finished_at"] or run["started_at"],
        )
    ]


def _evaluate_shadow_recovery(
    connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    counts = connection.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed
        FROM pipeline_runs WHERE dry_run = 0
        """
    ).fetchone()
    return "action_required", [
        _readiness_evidence(
            "pipeline_run_history",
            f"{counts['completed'] or 0} of {counts['total']} non-dry run(s) completed, but the current run schema has no normalized input hash, shared lock, resume, or recovery proof.",
            status="non_qualifying" if counts["total"] else "missing",
        )
    ]


def _evaluate_deferred_policy(
    _connection: sqlite3.Connection, _providers: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    return "deferred", [
        _readiness_evidence(
            "policy_boundary",
            "This capability is deliberately deferred and has no authorization to run.",
            status="non_qualifying",
        )
    ]


READINESS_EVALUATORS: dict[
    str,
    Callable[
        [sqlite3.Connection, dict[str, dict[str, Any]]],
        tuple[str, list[dict[str, Any]]],
    ],
] = {
    "provider_access_fred": _evaluate_provider_access_fred,
    "macro_pit_ingestion": _evaluate_macro_pit_ingestion,
    "macro_validation_seal": _evaluate_macro_validation_seal,
    "real_regime_snapshot": _evaluate_real_regime_snapshot,
    "versioned_security_universe": _evaluate_versioned_security_universe,
    "real_market_history": _evaluate_real_market_history,
    "cross_sectional_snapshot": _evaluate_cross_sectional_snapshot,
    "symbol_timing_snapshot": _evaluate_symbol_timing_snapshot,
    "portfolio_allocation_snapshot": _evaluate_portfolio_allocation_snapshot,
    "cash_expression_snapshot": _evaluate_cash_expression_snapshot,
    "options_expression_snapshot": _evaluate_options_expression_snapshot,
    "walk_forward_research": _evaluate_walk_forward_research,
    "shadow_recovery": _evaluate_shadow_recovery,
    "deferred_policy": _evaluate_deferred_policy,
}


def get_readiness(
    connection: sqlite3.Connection, providers: list[dict[str, Any]]
) -> dict[str, Any]:
    milestone_rows = connection.execute(
        "SELECT * FROM readiness_milestones ORDER BY sort_order, milestone_key"
    ).fetchall()
    gate_rows = connection.execute(
        "SELECT * FROM readiness_gates ORDER BY sort_order, gate_key"
    ).fetchall()
    dependency_rows = connection.execute(
        """
        SELECT dependency.gate_key, dependency.dependency_gate_key,
               required.sort_order AS dependency_sort_order
        FROM readiness_gate_dependencies AS dependency
        JOIN readiness_gates AS required
          ON required.gate_key = dependency.dependency_gate_key
        ORDER BY dependency.gate_key, required.sort_order, dependency.dependency_gate_key
        """
    ).fetchall()
    dependencies: dict[str, list[str]] = {}
    for row in dependency_rows:
        dependencies.setdefault(row["gate_key"], []).append(
            row["dependency_gate_key"]
        )

    provider_by_key = {provider["key"]: provider for provider in providers}
    gates: list[dict[str, Any]] = []
    resolved: dict[str, dict[str, Any]] = {}
    for row in gate_rows:
        evaluator = READINESS_EVALUATORS.get(row["evaluator_key"])
        if evaluator is None:
            raw_status = "failed"
            evidence = [
                _readiness_evidence(
                    "readiness_configuration",
                    f"Evaluator {row['evaluator_key']} is not installed.",
                    status="non_qualifying",
                    record_id=row["gate_key"],
                )
            ]
        else:
            raw_status, evidence = evaluator(connection, provider_by_key)
        if raw_status not in {
            "passed",
            "action_required",
            "blocked",
            "failed",
            "deferred",
        }:
            evidence.append(
                _readiness_evidence(
                    "readiness_configuration",
                    f"Evaluator {row['evaluator_key']} returned unsupported state {raw_status}.",
                    status="non_qualifying",
                    record_id=row["gate_key"],
                )
            )
            raw_status = "failed"
        required = dependencies.get(row["gate_key"], [])
        unresolved = [key for key in required if key not in resolved]
        blocked_by = [
            key
            for key in required
            if key in resolved and resolved[key]["status"] != "passed"
        ]
        if raw_status == "deferred":
            status = "deferred"
        elif unresolved:
            status = "failed"
            blocked_by = [*unresolved, *blocked_by]
            evidence.append(
                _readiness_evidence(
                    "readiness_configuration",
                    "A dependency is missing or ordered after this gate: "
                    + ", ".join(unresolved),
                    status="non_qualifying",
                    record_id=row["gate_key"],
                )
            )
        elif blocked_by:
            status = "blocked"
        else:
            status = raw_status
        gate = {
            "key": row["gate_key"],
            "milestone_key": row["milestone_key"],
            "name": row["name"],
            "layer": row["layer"],
            "description": row["description"],
            "status": status,
            "acceptance_criterion": row["acceptance_criterion"],
            "evaluator_key": row["evaluator_key"],
            "next_action": row["next_action"],
            "target_route": row["target_route"],
            "sort_order": row["sort_order"],
            "dependencies": required,
            "blocked_by": blocked_by,
            "evidence": evidence,
        }
        gates.append(gate)
        resolved[gate["key"]] = gate

    milestones: list[dict[str, Any]] = []
    for row in milestone_rows:
        milestone_gates = [
            gate for gate in gates if gate["milestone_key"] == row["milestone_key"]
        ]
        passed = sum(gate["status"] == "passed" for gate in milestone_gates)
        if milestone_gates and passed == len(milestone_gates):
            status = "passed"
        elif any(gate["status"] == "failed" for gate in milestone_gates):
            status = "failed"
        elif any(gate["status"] == "action_required" for gate in milestone_gates):
            status = "action_required"
        elif any(gate["status"] == "blocked" for gate in milestone_gates):
            status = "blocked"
        else:
            status = "deferred"
        current = next(
            (
                gate
                for gate in milestone_gates
                if gate["status"] not in {"passed", "deferred"}
            ),
            None,
        )
        milestones.append(
            {
                "key": row["milestone_key"],
                "name": row["name"],
                "description": row["description"],
                "status": status,
                "sort_order": row["sort_order"],
                "gates_total": len(milestone_gates),
                "gates_passed": passed,
                "current_gate_key": current["key"] if current else None,
            }
        )

    current = next(
        (
            gate
            for gate in gates
            if gate["status"] in {"action_required", "failed"}
        ),
        None,
    )
    if current is None:
        current = next(
            (gate for gate in gates if gate["status"] == "blocked"), None
        )
    return {
        "summary": {
            "milestones_total": len(milestones),
            "milestones_passed": sum(
                milestone["status"] == "passed" for milestone in milestones
            ),
            "gates_total": len(gates),
            "gates_passed": sum(gate["status"] == "passed" for gate in gates),
            "current_gate_key": current["key"] if current else None,
            "current_action": current["next_action"] if current else None,
            "target_route": current["target_route"] if current else None,
        },
        "milestones": milestones,
        "gates": gates,
    }
