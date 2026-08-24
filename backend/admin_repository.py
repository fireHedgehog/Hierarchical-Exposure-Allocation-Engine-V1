from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.pipeline.stages import (
    FredFetcher,
    PriceFetcher,
    run_allocation_engine_stage,
    run_factor_engine_stage,
    run_fetch_data_stage,
    run_instrument_engine_stage,
    run_regime_filter_stage,
    run_validate_data_stage,
)
from backend.providers import ProviderVerifier, VerificationResult
from backend.readiness_repository import get_readiness
from backend.secrets import SecretStore


class ProviderNotFoundError(LookupError):
    pass


class PipelineNotFoundError(LookupError):
    pass


class StrategyNotFoundError(LookupError):
    pass


CLOCK_SKEW_TOLERANCE_SECONDS = 300


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip().replace(" ", "T")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json(value: str) -> Any:
    return json.loads(value)


def _provider_row(connection: sqlite3.Connection, provider_key: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM operator_providers WHERE provider_key = ?",
        (provider_key.strip().lower(),),
    ).fetchone()
    if row is None:
        raise ProviderNotFoundError(provider_key)
    return row


def _latest_verification(
    connection: sqlite3.Connection, provider_key: str
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM provider_verifications
        WHERE provider_key = ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (provider_key,),
    ).fetchone()


def _verification_payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["verification_id"],
        "checked_at": row["checked_at"],
        "expires_at": row["expires_at"],
        "status": row["status"],
        "http_status": row["http_status"],
        "latency_ms": row["latency_ms"],
        "error_code": row["error_code"],
        "message": row["message"],
        "credential_source": row["credential_source"],
    }


def get_engine_mode(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute(
        "SELECT mode, updated_at, updated_reason FROM engine_operating_mode WHERE id = 1"
    ).fetchone()
    if row is None:
        return {"mode": "pilot", "updated_at": None, "updated_reason": None}
    return {
        "mode": row["mode"],
        "updated_at": row["updated_at"],
        "updated_reason": row["updated_reason"],
    }


def set_engine_mode(
    connection: sqlite3.Connection, mode: str, changed_at: datetime, reason: str | None = None
) -> dict[str, Any]:
    connection.execute(
        """
        INSERT INTO engine_operating_mode (id, mode, updated_at, updated_reason)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            mode = excluded.mode,
            updated_at = excluded.updated_at,
            updated_reason = excluded.updated_reason
        """,
        (mode, iso_z(changed_at), reason),
    )
    return get_engine_mode(connection)


def serialize_provider(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    secret_store: SecretStore,
    now: datetime,
    runtime_id: str,
) -> dict[str, Any]:
    credential_name = row["credential_name"]
    secret = (
        secret_store.get(credential_name, row["environment_variable"])
        if credential_name
        else None
    )
    verification_row = _latest_verification(connection, row["provider_key"])
    verification = _verification_payload(verification_row)
    checked_at = _parse_time(verification_row["checked_at"]) if verification_row else None
    stored_expires_at = (
        _parse_time(verification_row["expires_at"]) if verification_row else None
    )
    cooldown_seconds = int(row["verification_cooldown_seconds"])
    verification_ttl_seconds = max(
        cooldown_seconds, int(row["verification_ttl_seconds"])
    )
    policy_expires_at = (
        checked_at + timedelta(seconds=verification_ttl_seconds)
        if checked_at
        else None
    )
    # A shortened current policy immediately caps older stored validity. A TTL
    # extension never resurrects a result beyond the expiry recorded at check
    # time; that requires one fresh smoke test.
    expires_at = (
        min(stored_expires_at, policy_expires_at)
        if stored_expires_at and policy_expires_at
        else None
    )
    credential_updated_at = _parse_time(row["updated_at"])
    matches_credential_identity = bool(
        checked_at
        and verification_row["credential_revision"] == row["credential_revision"]
        and verification_row["credential_source"] == (secret.source if secret else None)
        and (
            secret is None
            or secret.source != "environment"
            or verification_row["runtime_id"] == runtime_id
        )
        and (credential_updated_at is None or checked_at >= credential_updated_at)
        and secret is not None
    )
    future_limit = now + timedelta(seconds=CLOCK_SKEW_TOLERANCE_SECONDS)
    verification_future_dated = bool(
        matches_credential_identity and checked_at and checked_at > future_limit
    )
    matches_current_credential = bool(
        matches_credential_identity and not verification_future_dated
    )
    applies_to_current_credential = bool(
        matches_current_credential and expires_at and expires_at > now
    )
    verification_expired = bool(
        matches_current_credential and expires_at and expires_at <= now
    )
    verification_policy_refresh_required = bool(
        matches_current_credential
        and stored_expires_at
        and policy_expires_at
        and stored_expires_at < policy_expires_at
    )
    cooldown_until = (
        checked_at + timedelta(seconds=cooldown_seconds) if checked_at else None
    )
    cooldown_remaining = (
        max(0, int((cooldown_until - now).total_seconds()))
        if matches_current_credential and cooldown_until and cooldown_until > now
        else 0
    )
    last_verification = (
        {
            **verification,
            "current": applies_to_current_credential,
            "applies_to_credential": matches_credential_identity,
            "expired": verification_expired,
            "future_dated": verification_future_dated,
            "effective_expires_at": iso_z(expires_at) if expires_at else None,
        }
        if verification is not None
        else None
    )
    if secret is None:
        credential_status = "missing"
        verification_status = None
    elif verification_future_dated:
        credential_status = "invalid_clock"
        verification_status = None
    elif verification_expired:
        credential_status = "expired"
        verification_status = None
    elif not applies_to_current_credential:
        credential_status = "unverified"
        verification_status = None
    else:
        verification_status = verification_row["status"]
        credential_status = "verified" if verification_status == "healthy" else "unhealthy"

    return {
        "key": row["provider_key"],
        "name": row["name"],
        "category": row["category"],
        "description": row["description"],
        "enabled": bool(row["enabled"]),
        "required": bool(row["required"]),
        "documentation_url": row["documentation_url"],
        "signup_url": row["signup_url"],
        "terms_url": row["terms_url"],
        "attribution_notice": row["attribution_notice"],
        "instructions": row["instructions"],
        "capabilities": _json(row["capabilities_json"]),
        "credential": {
            "label": row["credential_label"],
            "configured": secret is not None,
            "source": secret.source if secret else None,
            "managed": secret.managed if secret else False,
            "environment_variable": row["environment_variable"],
            "status": credential_status,
            "last_verified_at": verification_row["checked_at"] if matches_current_credential else None,
            "verification_expires_at": iso_z(expires_at) if matches_current_credential and expires_at else None,
            "verification_status": verification_status,
            "cooldown_seconds": cooldown_seconds,
            "cooldown_remaining_seconds": cooldown_remaining,
            "verification_ttl_seconds": verification_ttl_seconds,
            "verification_policy_refresh_required": verification_policy_refresh_required,
        },
        # Historical rows remain in SQLite for audit, but a result for a rotated
        # or deleted credential is never presented as the current verification.
        "verification": last_verification if applies_to_current_credential else None,
        "last_verification": last_verification,
    }


def list_providers(
    connection: sqlite3.Connection,
    secret_store: SecretStore,
    now: datetime,
    runtime_id: str,
) -> dict[str, Any]:
    rows = connection.execute(
        "SELECT * FROM operator_providers ORDER BY sort_order, provider_key"
    ).fetchall()
    providers = [
        serialize_provider(connection, row, secret_store, now, runtime_id)
        for row in rows
    ]
    return {
        "as_of": iso_z(now),
        "providers": providers,
        "roadmap": _provider_roadmap(connection, providers),
        "engine_mode": get_engine_mode(connection),
    }


def _provider_roadmap(
    connection: sqlite3.Connection, providers: list[dict[str, Any]]
) -> dict[str, Any]:
    provider_by_key = {provider["key"]: provider for provider in providers}
    plan_rows = connection.execute(
        "SELECT * FROM provider_onboarding_plan ORDER BY sort_order, plan_key"
    ).fetchall()
    capability_rows = connection.execute(
        "SELECT * FROM data_capabilities ORDER BY sort_order, capability_key"
    ).fetchall()
    coverage_rows = connection.execute(
        """
        SELECT mapping.*, plan.name AS provider_name,
               plan.integration_status AS provider_integration_status
        FROM provider_plan_capabilities AS mapping
        JOIN provider_onboarding_plan AS plan USING (plan_key)
        ORDER BY plan.sort_order, mapping.plan_key
        """
    ).fetchall()

    coverage_by_plan: dict[str, list[dict[str, Any]]] = {}
    coverage_by_capability: dict[str, list[dict[str, Any]]] = {}
    for row in coverage_rows:
        coverage = {
            "key": row["capability_key"],
            "role": row["coverage_role"],
            "note": row["coverage_note"],
        }
        coverage_by_plan.setdefault(row["plan_key"], []).append(coverage)
        coverage_by_capability.setdefault(row["capability_key"], []).append(
            {
                "key": row["plan_key"],
                "name": row["provider_name"],
                "role": row["coverage_role"],
                "integration_status": row["provider_integration_status"],
                "note": row["coverage_note"],
            }
        )

    accounts: list[dict[str, Any]] = []
    for row in plan_rows:
        operator = (
            provider_by_key.get(row["operator_provider_key"])
            if row["operator_provider_key"]
            else None
        )
        access_status = _roadmap_access_status(operator)
        accounts.append(
            {
                "key": row["plan_key"],
                "operator_provider_key": row["operator_provider_key"],
                "name": row["name"],
                "category": row["category"],
                "role": row["role"],
                "integration_status": row["integration_status"],
                "access_status": access_status,
                "required_for_first_slice": bool(row["required_for_first_slice"]),
                "registration_available": bool(operator),
                "verification_policy_refresh_required": bool(
                    operator
                    and operator["credential"].get(
                        "verification_policy_refresh_required"
                    )
                ),
                "documentation_url": row["documentation_url"],
                "signup_url": row["signup_url"],
                "pricing_url": row["pricing_url"],
                "terms_url": row["terms_url"],
                "guidance": row["guidance"],
                "licensing_note": row["licensing_note"],
                "capabilities": coverage_by_plan.get(row["plan_key"], []),
            }
        )

    capabilities: list[dict[str, Any]] = []
    for row in capability_rows:
        sources = coverage_by_capability.get(row["capability_key"], [])
        integration_status = _best_integration_status(
            [source["integration_status"] for source in sources]
        )
        capabilities.append(
            {
                "key": row["capability_key"],
                "name": row["name"],
                "category": row["category"],
                "description": row["description"],
                "requirement_level": row["requirement_level"],
                "unlocks": _json(row["unlocks_json"]),
                "integration_status": integration_status,
                "ingestion_ready": integration_status == "ingestion_ready",
                "providers": sources,
            }
        )

    first_slice_accounts = [
        account for account in accounts if account["required_for_first_slice"]
    ]
    registrations_needed_now = sum(
        account["access_status"] == "not_configured"
        for account in first_slice_accounts
    )
    verifications_needed_now = sum(
        account["access_status"] not in {"healthy", "not_configured"}
        or account["verification_policy_refresh_required"]
        for account in first_slice_accounts
    )
    verified_accounts = sum(account["access_status"] == "healthy" for account in accounts)
    supported_accounts = sum(account["registration_available"] for account in accounts)
    future_accounts = sum(not account["required_for_first_slice"] for account in accounts)

    return {
        "summary": {
            "planned_accounts": len(accounts),
            "supported_accounts": supported_accounts,
            "verified_accounts": verified_accounts,
            "registrations_needed_now": registrations_needed_now,
            "verifications_needed_now": verifications_needed_now,
            "future_accounts_planned": future_accounts,
            "capabilities_total": len(capabilities),
            "capabilities_ingestion_ready": sum(
                capability["ingestion_ready"] for capability in capabilities
            ),
        },
        "next_action": _provider_next_action(first_slice_accounts),
        "accounts": accounts,
        "capabilities": capabilities,
    }


def _roadmap_access_status(provider: dict[str, Any] | None) -> str:
    if provider is None:
        return "not_available"
    credential = provider["credential"]
    if (
        credential["status"] == "verified"
        and credential["verification_status"] == "healthy"
    ):
        return "healthy"
    if not credential["configured"]:
        return "not_configured"
    return credential["status"] or "unverified"


def _best_integration_status(statuses: list[str]) -> str:
    rank = {"planned": 0, "verification_ready": 1, "ingestion_ready": 2}
    return max(statuses, key=lambda status: rank.get(status, -1), default="planned")


def _provider_next_action(first_slice_accounts: list[dict[str, Any]]) -> str:
    if not first_slice_accounts:
        return "No provider is assigned to the first product slice."
    primary = first_slice_accounts[0]
    if primary["access_status"] == "not_configured":
        return f"Register the {primary['name']} key, then run its smoke test."
    if primary["verification_policy_refresh_required"]:
        return (
            f"Run one fresh {primary['name']} smoke test to adopt the one-year "
            "health policy. No additional registration is requested."
        )
    if primary["access_status"] != "healthy":
        return f"Run or resolve the {primary['name']} smoke test. No other registration is requested yet."
    return (
        "No additional registration is needed for the first regime slice. "
        "Next: implement FRED/ALFRED point-in-time ingestion and validate the stored data."
    )


def get_provider(
    connection: sqlite3.Connection,
    provider_key: str,
    secret_store: SecretStore,
    now: datetime,
    runtime_id: str,
) -> dict[str, Any]:
    return serialize_provider(
        connection, _provider_row(connection, provider_key), secret_store, now, runtime_id
    )


def mark_credential_changed(
    connection: sqlite3.Connection, provider_key: str, changed_at: datetime
) -> None:
    cursor = connection.execute(
        """
        UPDATE operator_providers
        SET updated_at = ?, credential_revision = credential_revision + 1
        WHERE provider_key = ?
        """,
        (iso_z(changed_at), provider_key.strip().lower()),
    )
    if cursor.rowcount == 0:
        raise ProviderNotFoundError(provider_key)


def verify_provider(
    connection: sqlite3.Connection,
    provider_key: str,
    secret_store: SecretStore,
    verifiers: Mapping[str, ProviderVerifier],
    now: datetime,
    runtime_id: str,
) -> dict[str, Any]:
    provider = _provider_row(connection, provider_key)
    key = provider["provider_key"]
    credential = secret_store.get(provider["credential_name"], provider["environment_variable"])
    latest = _latest_verification(connection, key)
    latest_checked = _parse_time(latest["checked_at"]) if latest else None
    latest_stored_expires = _parse_time(latest["expires_at"]) if latest else None
    changed_at = _parse_time(provider["updated_at"])
    cooldown = int(provider["verification_cooldown_seconds"])
    current_ttl = max(cooldown, int(provider["verification_ttl_seconds"]))
    current_policy_expires = (
        latest_checked + timedelta(seconds=current_ttl)
        if latest_checked
        else None
    )
    latest_expires = (
        min(latest_stored_expires, current_policy_expires)
        if latest_stored_expires and current_policy_expires
        else None
    )
    cooldown_until = (
        latest_checked + timedelta(seconds=cooldown) if latest_checked else None
    )
    cache_applies = bool(
        credential
        and latest
        and latest_checked
        and latest_expires
        and latest_expires > now
        and latest_checked
        <= now + timedelta(seconds=CLOCK_SKEW_TOLERANCE_SECONDS)
        and cooldown_until
        and cooldown_until > now
        and latest["credential_revision"] == provider["credential_revision"]
        and latest["credential_source"] == (credential.source if credential else None)
        and (
            credential is None
            or credential.source != "environment"
            or latest["runtime_id"] == runtime_id
        )
        and (changed_at is None or latest_checked >= changed_at)
    )
    if cache_applies:
        return {
            "provider_key": key,
            "cached": True,
            "cooldown_remaining_seconds": max(
                0, int((cooldown_until - now).total_seconds())
            ),
            "verification": _verification_payload(latest),
        }

    if credential is None:
        result = VerificationResult(
            status="not_configured",
            error_code="credential_missing",
            message="No credential is configured for this provider.",
        )
        credential_source = None
    else:
        verifier = verifiers.get(provider["verifier_kind"])
        if verifier is None:
            result = VerificationResult(
                status="provider_error",
                error_code="verifier_unavailable",
                message="No smoke verifier is installed for this provider.",
            )
        else:
            result = verifier.verify(credential.value)
        credential_source = credential.source

    checked_at = iso_z(now)
    # `expires_at` is the health-validity boundary, not the anti-repeat cache.
    # A manual click after cooldown performs a new smoke call even while the
    # prior result remains current enough for pipeline readiness.
    verification_ttl = max(
        cooldown, int(provider["verification_ttl_seconds"])
    )
    expires_at = iso_z(
        datetime.fromtimestamp(now.timestamp() + verification_ttl, timezone.utc)
    )
    verification_id = f"verify-{uuid.uuid4()}"
    connection.execute(
        """
        INSERT INTO provider_verifications (
            verification_id, provider_key, checked_at, expires_at, status,
            http_status, latency_ms, error_code, message, credential_revision,
            runtime_id, credential_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            verification_id,
            key,
            checked_at,
            expires_at,
            result.status,
            result.http_status,
            result.latency_ms,
            result.error_code,
            result.message,
            provider["credential_revision"],
            runtime_id,
            credential_source,
        ),
    )
    row = connection.execute(
        "SELECT * FROM provider_verifications WHERE verification_id = ?",
        (verification_id,),
    ).fetchone()
    return {
        "provider_key": key,
        "cached": False,
        "cooldown_remaining_seconds": cooldown,
        "verification": _verification_payload(row),
    }


def list_staging_symbols(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT staging.*, plan.name AS production_provider_name
        FROM staging_symbols AS staging
        LEFT JOIN provider_onboarding_plan AS plan
          ON plan.plan_key = staging.production_provider_key
        ORDER BY staging.sort_order, staging.symbol
        """
    ).fetchall()
    symbols = [
        {
            "symbol": row["symbol"],
            "name": row["name"],
            "category": row["category"],
            "tier": row["tier"],
            "production_provider_key": row["production_provider_key"],
            "production_provider_name": row["production_provider_name"],
            "notes": row["notes"],
            "active": bool(row["active"]),
        }
        for row in rows
    ]
    by_category: dict[str, int] = {}
    for symbol in symbols:
        by_category[symbol["category"]] = by_category.get(symbol["category"], 0) + 1
    return {
        "summary": {
            "total": len(symbols),
            "active": sum(symbol["active"] for symbol in symbols),
            "by_category": by_category,
        },
        "symbols": symbols,
    }


def get_data_inventory(
    connection: sqlite3.Connection, now: datetime
) -> dict[str, Any]:
    rows = connection.execute(
        "SELECT * FROM data_assets ORDER BY label, asset_key"
    ).fetchall()
    assets: list[dict[str, Any]] = []
    counts = {
        "ready": 0,
        "stale": 0,
        "missing": 0,
        "partial": 0,
        "invalid": 0,
    }
    for row in rows:
        observation_at = _parse_time(row["last_observation_at"])
        age_seconds = (
            int((now - observation_at).total_seconds()) if observation_at else None
        )
        if (
            age_seconds is not None
            and age_seconds < -CLOCK_SKEW_TOLERANCE_SECONDS
        ):
            freshness = "future"
            effective_status = "invalid"
        elif row["classification"] == "synthetic":
            freshness = "not_applicable"
            effective_status = row["status"]
        elif row["status"] == "missing" or observation_at is None:
            freshness = "missing"
            age_seconds = None
            effective_status = row["status"]
        elif row["max_age_seconds"] is None:
            freshness = "unknown"
            effective_status = row["status"]
        else:
            freshness = "current" if age_seconds <= row["max_age_seconds"] else "stale"
            effective_status = row["status"]
        if freshness == "stale" and effective_status == "ready":
            effective_status = "stale"
        if effective_status in counts:
            counts[effective_status] += 1
        assets.append(
            {
                "key": row["asset_key"],
                "provider_key": row["provider_key"],
                "label": row["label"],
                "kind": row["kind"],
                "symbol": row["symbol"],
                "frequency": row["frequency"],
                "classification": row["classification"],
                "row_count": row["row_count"],
                "period_start": row["period_start"],
                "period_end": row["period_end"],
                "last_observation_at": row["last_observation_at"],
                "last_fetched_at": row["last_fetched_at"],
                "max_age_seconds": row["max_age_seconds"],
                "age_seconds": age_seconds,
                "freshness": freshness,
                "status": effective_status,
                "dataset_snapshot_id": row["dataset_snapshot_id"],
                "detail": row["detail"],
            }
        )
    latest_snapshot = connection.execute(
        """
        SELECT id, dataset_snapshot_id, data_classification
        FROM desk_snapshots AS desk
        WHERE desk.immutable = 1
          AND desk.dataset_snapshot_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM dataset_snapshots AS dataset
              WHERE dataset.id = desk.dataset_snapshot_id
                AND dataset.immutable = 1
          )
        ORDER BY desk.as_of DESC, desk.created_at DESC, desk.rowid DESC
        LIMIT 1
        """
    ).fetchone()
    symbols: list[dict[str, Any]] = []
    if latest_snapshot is not None and latest_snapshot["dataset_snapshot_id"] is not None:
        symbol_rows = connection.execute(
            """
            SELECT symbols.symbol, symbols.name, COUNT(bars.time) AS row_count,
                   MIN(bars.time) AS period_start, MAX(bars.time) AS period_end,
                   MAX(COALESCE(bars.observed_at, bars.time)) AS last_observation_at,
                   MAX(bars.ingested_at) AS last_fetched_at
            FROM symbols
            LEFT JOIN symbol_bars AS bars
              ON bars.dataset_snapshot_id = ?
             AND bars.security_id = symbols.security_id
            WHERE symbols.snapshot_id = ?
            GROUP BY symbols.symbol, symbols.name
            ORDER BY symbols.symbol
            """,
            (latest_snapshot["dataset_snapshot_id"], latest_snapshot["id"]),
        ).fetchall()
        price_policy = connection.execute(
            """
            SELECT MIN(max_age_seconds) AS max_age_seconds
            FROM data_assets
            WHERE kind = 'price_bars' AND classification = ?
            """,
            (latest_snapshot["data_classification"],),
        ).fetchone()
        max_age_seconds = price_policy["max_age_seconds"] if price_policy else None
        for symbol in symbol_rows:
            observed = _parse_time(symbol["last_observation_at"])
            age_seconds = int((now - observed).total_seconds()) if observed else None
            if (
                age_seconds is not None
                and age_seconds < -CLOCK_SKEW_TOLERANCE_SECONDS
            ):
                freshness = "future"
                status = "invalid"
            elif latest_snapshot["data_classification"] == "synthetic":
                freshness = "not_applicable"
                status = "ready" if symbol["row_count"] else "missing"
            elif not symbol["row_count"] or observed is None:
                freshness = "missing"
                status = "missing"
            elif max_age_seconds is None:
                freshness = "unknown"
                status = "ready"
            else:
                freshness = "current" if age_seconds <= max_age_seconds else "stale"
                status = "ready" if freshness == "current" else "stale"
            symbols.append(
                {
                    "symbol": symbol["symbol"],
                    "name": symbol["name"],
                    "row_count": symbol["row_count"],
                    "period_start": symbol["period_start"],
                    "period_end": symbol["period_end"],
                    "last_observation_at": symbol["last_observation_at"],
                    "last_fetched_at": symbol["last_fetched_at"],
                    "age_seconds": age_seconds,
                    "classification": latest_snapshot["data_classification"],
                    "freshness": freshness,
                    "status": status,
                    "dataset_snapshot_id": latest_snapshot["dataset_snapshot_id"],
                }
            )
    invalid_assets = counts["invalid"]
    invalid_symbols = sum(symbol["status"] == "invalid" for symbol in symbols)
    summary = {
        "assets": len(assets),
        **counts,
        "invalid": invalid_assets + invalid_symbols,
        "invalid_assets": invalid_assets,
        "invalid_symbols": invalid_symbols,
    }
    return {
        "as_of": iso_z(now),
        "summary": summary,
        "assets": assets,
        "symbols": symbols,
    }


def _serialize_stage_definition(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "key": row["stage_key"],
        "label": row["label"],
        "name": row["label"],
        "description": row["description"],
        "order": row["stage_order"],
        "implementation_status": row["implementation_status"],
        "implemented": row["implementation_status"] == "ready",
        "status": row["implementation_status"],
        "required_provider_keys": _json(row["required_provider_keys_json"]),
    }


def _serialize_pipeline_run(
    connection: sqlite3.Connection, row: sqlite3.Row | None
) -> dict[str, Any] | None:
    if row is None:
        return None
    stages = connection.execute(
        """
        SELECT stage.*, definition.label AS stage_name
        FROM pipeline_stage_runs AS stage
        LEFT JOIN pipeline_runs AS run ON run.run_id = stage.run_id
        LEFT JOIN pipeline_stage_definitions AS definition
          ON definition.pipeline_key = run.pipeline_key
         AND definition.stage_key = stage.stage_key
        WHERE stage.run_id = ? ORDER BY stage.stage_order, stage.stage_key
        """,
        (row["run_id"],),
    ).fetchall()
    return {
        "id": row["run_id"],
        "pipeline_key": row["pipeline_key"],
        "pipeline_version": row["pipeline_version"],
        "trigger_type": row["trigger_type"],
        "dry_run": bool(row["dry_run"]),
        "requested_at": row["requested_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "status": row["status"],
        "dataset_snapshot_id": row["dataset_snapshot_id"],
        "desk_snapshot_id": row["desk_snapshot_id"],
        "summary": row["summary"],
        "detail": row["summary"],
        "stages": [
            {
                "key": stage["stage_key"],
                "name": stage["stage_name"] or stage["stage_key"],
                "order": stage["stage_order"],
                "status": stage["status"],
                "started_at": stage["started_at"],
                "finished_at": stage["finished_at"],
                "records_read": stage["records_read"],
                "records_written": stage["records_written"],
                "message": stage["message"],
                "detail": stage["message"],
                "error_code": stage["error_code"],
                "error": stage["error_code"],
            }
            for stage in stages
        ],
    }


def get_pipeline(
    connection: sqlite3.Connection, pipeline_key: str = "daily_desk"
) -> dict[str, Any]:
    definition = connection.execute(
        "SELECT * FROM pipeline_definitions WHERE pipeline_key = ?",
        (pipeline_key,),
    ).fetchone()
    if definition is None:
        raise PipelineNotFoundError(pipeline_key)
    stages = connection.execute(
        """
        SELECT * FROM pipeline_stage_definitions
        WHERE pipeline_key = ? ORDER BY stage_order, stage_key
        """,
        (pipeline_key,),
    ).fetchall()
    latest = connection.execute(
        """
        SELECT * FROM pipeline_runs
        WHERE pipeline_key = ? ORDER BY requested_at DESC, rowid DESC LIMIT 1
        """,
        (pipeline_key,),
    ).fetchone()
    return {
        "definition": {
            "key": definition["pipeline_key"],
            "name": definition["name"],
            "version": definition["version"],
            "description": definition["description"],
            "enabled": bool(definition["enabled"]),
            "manual_only": bool(definition["manual_only"]),
            "stages": [_serialize_stage_definition(row) for row in stages],
        },
        "latest_run": _serialize_pipeline_run(connection, latest),
    }


def run_pipeline(
    connection: sqlite3.Connection,
    secret_store: SecretStore,
    now: datetime,
    *,
    dry_run: bool,
    runtime_id: str,
    fred_observation_fetcher: FredFetcher,
    price_fetcher: PriceFetcher,
    pipeline_key: str = "daily_desk",
) -> dict[str, Any]:
    pipeline = get_pipeline(connection, pipeline_key)["definition"]
    if not pipeline["enabled"]:
        raise PipelineNotFoundError(f"{pipeline_key}:disabled")

    timestamp = iso_z(now)
    run_id = f"run-{uuid.uuid4()}"
    engine_mode = get_engine_mode(connection)["mode"]
    provider_rows = {
        row["provider_key"]: row
        for row in connection.execute("SELECT * FROM operator_providers").fetchall()
    }
    required = sorted(
        {
            key
            for stage in pipeline["stages"]
            for key in stage["required_provider_keys"]
        }
    )
    provider_states: dict[str, str] = {}
    for key in required:
        provider = provider_rows.get(key)
        if provider is None:
            provider_states[key] = "missing"
            continue
        if not provider["enabled"]:
            provider_states[key] = "disabled"
            continue
        status = serialize_provider(
            connection, provider, secret_store, now, runtime_id
        )["credential"]
        if not status["configured"]:
            provider_states[key] = "missing"
        elif status["status"] == "expired":
            provider_states[key] = "expired"
        elif status["status"] == "invalid_clock":
            provider_states[key] = "invalid_clock"
        elif status["verification_status"] is None:
            provider_states[key] = "unverified"
        elif status["verification_status"] != "healthy":
            provider_states[key] = "unhealthy"
        else:
            provider_states[key] = "healthy"

    stage_provider_issues: dict[str, dict[str, list[str]]] = {}
    for stage in pipeline["stages"]:
        issues = {
            "missing": [],
            "disabled": [],
            "unverified": [],
            "expired": [],
            "invalid_clock": [],
            "unhealthy": [],
            "pilot_mode_restricted": [],
        }
        for key in stage["required_provider_keys"]:
            state = provider_states.get(key, "missing")
            if state != "healthy":
                issues[state].append(key)
            # Pilot mode blocks a paid-tier provider even if it happens to be
            # configured and healthy — the gate is about the operating mode
            # choice, not credential health. No current stage requires a paid
            # provider yet, so this has no visible effect until one does.
            provider = provider_rows.get(key)
            if engine_mode == "pilot" and provider is not None and provider["tier"] == "paid":
                issues["pilot_mode_restricted"].append(key)
        stage_provider_issues[stage["key"]] = issues

    stage_results: list[tuple[Any, ...]] = []
    provider_issues = any(
        any(values for values in issues.values())
        for issues in stage_provider_issues.values()
    )
    inventory = get_data_inventory(connection, now)
    invalid_data = inventory["summary"]["invalid"]
    preflight_issues = provider_issues or invalid_data > 0
    preflight_status = "completed_with_warnings" if preflight_issues else "completed"
    preflight_parts = []
    for stage in pipeline["stages"]:
        issues = stage_provider_issues[stage["key"]]
        labels = []
        if issues["missing"]:
            labels.append(f"missing {', '.join(issues['missing'])}")
        if issues["disabled"]:
            labels.append(f"disabled {', '.join(issues['disabled'])}")
        if issues["unverified"]:
            labels.append(f"unverified {', '.join(issues['unverified'])}")
        if issues["expired"]:
            labels.append(f"expired {', '.join(issues['expired'])}")
        if issues["invalid_clock"]:
            labels.append(f"invalid clock {', '.join(issues['invalid_clock'])}")
        if issues["unhealthy"]:
            labels.append(f"unhealthy {', '.join(issues['unhealthy'])}")
        if issues["pilot_mode_restricted"]:
            labels.append(
                f"pilot mode restricts paid provider {', '.join(issues['pilot_mode_restricted'])}"
            )
        if labels:
            preflight_parts.append(f"{stage['key']}: {', '.join(labels)}")
    if invalid_data:
        preflight_parts.append(
            "invalid future-dated inventory records: "
            f"{invalid_data} (assets {inventory['summary']['invalid_assets']}, "
            f"symbols {inventory['summary']['invalid_symbols']})"
        )
    preflight_message = (
        "Provider readiness — " + "; ".join(preflight_parts) + "."
        if preflight_parts
        else "All required providers have a current healthy smoke verification; data has not been fetched."
    )
    stage_results.append(
        (run_id, "preflight", 10, preflight_status, timestamp, timestamp, 0, 0, preflight_message, "preflight_not_ready" if preflight_issues else None)
    )

    remaining = [stage for stage in pipeline["stages"] if stage["key"] != "preflight"]
    dataset_snapshot_id: str | None = None
    desk_snapshot_id: str | None = None
    if dry_run:
        for stage in remaining:
            stage_results.append(
                (run_id, stage["key"], stage["order"], "skipped", None, None, None, None, "Dry run: stage was not executed.", None)
            )
        run_status = "partial" if preflight_issues else "completed"
        summary = "Preflight completed; dry run made no data or decision changes."
    else:
        blocked = False
        stage_statuses: list[str] = []
        for stage in remaining:
            if blocked:
                stage_results.append(
                    (run_id, stage["key"], stage["order"], "pending", None, None, None, None, "Not started because an earlier required stage was blocked.", None)
                )
                continue
            issues = stage_provider_issues[stage["key"]]
            stage_has_provider_issue = any(values for values in issues.values())
            # Fetch is allowed to refresh bad existing inventory. Timestamp
            # invalidity becomes a hard gate at validation and downstream stages.
            invalid_blocks_stage = bool(
                invalid_data and stage["key"] != "fetch_data"
            )
            if invalid_blocks_stage or stage_has_provider_issue:
                error_code = "preflight_not_ready"
                message = (
                    "Cannot continue until this stage's provider requirements and data timestamps pass preflight."
                )
                stage_results.append(
                    (run_id, stage["key"], stage["order"], "blocked", timestamp, timestamp, 0, 0, message, error_code)
                )
                stage_statuses.append("blocked")
                blocked = True
                continue
            if stage["implementation_status"] != "ready":
                stage_results.append(
                    (run_id, stage["key"], stage["order"], "blocked", timestamp, timestamp, 0, 0, "This stage is scaffolded but its implementation is not connected.", "stage_not_implemented")
                )
                stage_statuses.append("blocked")
                blocked = True
                continue

            if stage["key"] == "fetch_data":
                outcome = run_fetch_data_stage(
                    connection, secret_store, fred_observation_fetcher, price_fetcher, now, engine_mode
                )
            elif stage["key"] == "validate_data":
                outcome = run_validate_data_stage(connection, now, dataset_snapshot_id)
            elif stage["key"] == "regime_filter":
                outcome = run_regime_filter_stage(connection, now, dataset_snapshot_id, engine_mode)
            elif stage["key"] == "factor_engine":
                outcome = run_factor_engine_stage(
                    connection, now, dataset_snapshot_id, desk_snapshot_id, engine_mode
                )
            elif stage["key"] == "allocation_engine":
                outcome = run_allocation_engine_stage(connection, now, dataset_snapshot_id, desk_snapshot_id)
            elif stage["key"] == "instrument_engine":
                outcome = run_instrument_engine_stage(connection, now, dataset_snapshot_id, desk_snapshot_id)
            else:
                # Defensive: no other stage's implementation_status should be
                # 'ready' yet. factor_engine/allocation_engine/instrument_engine/
                # publish_snapshot stay 'scaffolded' until their own iteration.
                outcome = None

            if outcome is None:
                stage_results.append(
                    (run_id, stage["key"], stage["order"], "blocked", timestamp, timestamp, 0, 0, "This stage is marked ready but has no registered executor.", "stage_executor_missing")
                )
                stage_statuses.append("blocked")
                blocked = True
                continue

            dataset_snapshot_id = outcome.dataset_snapshot_id or dataset_snapshot_id
            desk_snapshot_id = outcome.desk_snapshot_id or desk_snapshot_id
            stage_results.append(
                (
                    run_id, stage["key"], stage["order"], outcome.status, timestamp, timestamp,
                    outcome.records_read, outcome.records_written, outcome.message, outcome.error_code,
                )
            )
            stage_statuses.append(outcome.status)
            if outcome.status in {"blocked", "failed"}:
                blocked = True

        if any(status == "failed" for status in stage_statuses):
            run_status = "failed"
        elif any(status == "blocked" for status in stage_statuses):
            run_status = "blocked"
        elif any(status == "completed_with_warnings" for status in stage_statuses):
            run_status = "partial"
        else:
            run_status = "completed"
        summary = (
            "Manual run stopped safely before publishing a full downstream snapshot."
            if run_status in {"blocked", "failed"}
            else "Manual run completed."
        )
        # Stages publish into one open dataset/desk snapshot pair (created by
        # fetch_data/regime_filter) rather than each sealing independently, so
        # a later 'ready' stage — factor_engine today, allocation/instrument
        # engines later — can still attach to the same decision (factor_engine
        # writes dataset-scoped symbol_events, the backtest trade log, which a
        # sealed dataset would reject). Seal once, here, dataset before desk
        # (the desk-publish trigger requires an already-sealed matching
        # dataset), after every stage that will run this pass has run.
        if dataset_snapshot_id:
            connection.execute(
                "UPDATE dataset_snapshots SET immutable = 1 WHERE id = ? AND immutable = 0",
                (dataset_snapshot_id,),
            )
        if desk_snapshot_id:
            connection.execute(
                "UPDATE desk_snapshots SET immutable = 1 WHERE id = ? AND immutable = 0",
                (desk_snapshot_id,),
            )

    connection.execute(
        """
        INSERT INTO pipeline_runs (
            run_id, pipeline_key, pipeline_version, trigger_type, dry_run,
            requested_at, started_at, finished_at, status,
            dataset_snapshot_id, desk_snapshot_id, summary
        ) VALUES (?, ?, ?, 'manual', ?, ?, ?, NULL, 'running', NULL, NULL, ?)
        """,
        (
            run_id,
            pipeline_key,
            pipeline["version"],
            int(dry_run),
            timestamp,
            timestamp,
            "Run stages are being recorded.",
        ),
    )
    connection.executemany(
        """
        INSERT INTO pipeline_stage_runs (
            run_id, stage_key, stage_order, status, started_at, finished_at,
            records_read, records_written, message, error_code
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        stage_results,
    )
    connection.execute(
        """
        UPDATE pipeline_runs
        SET finished_at = ?, status = ?, summary = ?, dataset_snapshot_id = ?, desk_snapshot_id = ?
        WHERE run_id = ?
        """,
        (timestamp, run_status, summary, dataset_snapshot_id, desk_snapshot_id, run_id),
    )
    row = connection.execute(
        "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    return {"run": _serialize_pipeline_run(connection, row)}


def _decay_for_strategy(
    connection: sqlite3.Connection, strategy_key: str, version: str | None
) -> dict[str, Any] | None:
    if version is None:
        return None
    row = connection.execute(
        """
        SELECT value, unit, status, as_of FROM strategy_diagnostics
        WHERE strategy_key = ? AND version = ? AND metric_key = 'decay_rate'
        """,
        (strategy_key, version),
    ).fetchone()
    return dict(row) if row else None


def list_strategies(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = connection.execute(
        "SELECT * FROM strategies ORDER BY family, name, strategy_key"
    ).fetchall()
    summary = {"total": len(rows), "active": 0, "watching": 0, "retired": 0, "draft": 0}
    strategies = []
    for row in rows:
        summary[row["status"]] += 1
        strategies.append(
            {
                "key": row["strategy_key"],
                "name": row["name"],
                "family": row["family"],
                "summary": row["summary"],
                "status": row["status"],
                "version": row["current_version"],
                "decay": _decay_for_strategy(connection, row["strategy_key"], row["current_version"]),
                "added_at": row["added_at"],
                "retired_at": row["retired_at"],
                "public_spec_url": row["public_spec_url"],
            }
        )
    return {"summary": summary, "strategies": strategies}


def get_strategy(connection: sqlite3.Connection, strategy_key: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM strategies WHERE strategy_key = ?", (strategy_key,)
    ).fetchone()
    if row is None:
        raise StrategyNotFoundError(strategy_key)
    versions = connection.execute(
        """
        SELECT * FROM strategy_versions WHERE strategy_key = ?
        ORDER BY created_at DESC, version DESC
        """,
        (strategy_key,),
    ).fetchall()
    version_payloads = []
    for version in versions:
        diagnostics = connection.execute(
            """
            SELECT metric_key, label, value, unit, status, window_label, as_of, description
            FROM strategy_diagnostics
            WHERE strategy_key = ? AND version = ?
            ORDER BY sort_order, metric_key
            """,
            (strategy_key, version["version"]),
        ).fetchall()
        version_payloads.append(
            {
                "version": version["version"],
                "created_at": version["created_at"],
                "thesis": version["thesis"],
                "expected_edge": version["expected_edge"],
                "change_summary": version["change_summary"],
                "parameters": _json(version["parameters_json"]),
                "code_reference": version["code_reference"],
                "promoted_at": version["promoted_at"],
                "next_review_at": version["next_review_at"],
                "verification_status": version["verification_status"],
                "diagnostics": [dict(metric) for metric in diagnostics],
            }
        )
    lifecycle = connection.execute(
        """
        SELECT event_id, occurred_at, from_status, to_status, reason, strategy_version
        FROM strategy_lifecycle_events WHERE strategy_key = ?
        ORDER BY occurred_at DESC, rowid DESC
        """,
        (strategy_key,),
    ).fetchall()
    research_rows = connection.execute(
        """
        SELECT * FROM research_runs WHERE strategy_key = ?
        ORDER BY started_at DESC, rowid DESC
        """,
        (strategy_key,),
    ).fetchall()
    research_runs = []
    for run in research_rows:
        artifacts = connection.execute(
            """
            SELECT artifact_key, relative_path, media_type, sha256, size_bytes,
                   curated, created_at
            FROM research_artifacts WHERE research_run_id = ?
            ORDER BY curated DESC, artifact_key
            """,
            (run["research_run_id"],),
        ).fetchall()
        research_runs.append(
            {
                "id": run["research_run_id"],
                "strategy_version": run["strategy_version"],
                "dataset_snapshot_id": run["dataset_snapshot_id"],
                "code_commit": run["code_commit"],
                "parameters": _json(run["parameters_json"]),
                "status": run["status"],
                "started_at": run["started_at"],
                "finished_at": run["finished_at"],
                "summary": run["summary"],
                "artifacts": [
                    {**dict(artifact), "curated": bool(artifact["curated"])}
                    for artifact in artifacts
                ],
            }
        )
    return {
        "strategy": {
            "key": row["strategy_key"],
            "name": row["name"],
            "family": row["family"],
            "summary": row["summary"],
            "status": row["status"],
            "version": row["current_version"],
            "added_at": row["added_at"],
            "retired_at": row["retired_at"],
            "retirement_reason": row["retirement_reason"],
            "public_spec_url": row["public_spec_url"],
            "versions": version_payloads,
            "lifecycle": [dict(event) for event in lifecycle],
            "research_runs": research_runs,
        }
    }


def get_overview(
    connection: sqlite3.Connection,
    secret_store: SecretStore,
    now: datetime,
    runtime_id: str,
) -> dict[str, Any]:
    provider_payload = list_providers(connection, secret_store, now, runtime_id)[
        "providers"
    ]
    data = get_data_inventory(connection, now)
    pipeline = get_pipeline(connection)
    strategies = list_strategies(connection)
    return {
        "as_of": iso_z(now),
        "manual_only": pipeline["definition"]["manual_only"],
        "providers": {
            "total": len(provider_payload),
            "configured": sum(item["credential"]["configured"] for item in provider_payload),
            "healthy": sum(item["credential"]["verification_status"] == "healthy" for item in provider_payload),
        },
        "data": data["summary"],
        "pipeline": {
            "definition": pipeline["definition"],
            "latest_run": pipeline["latest_run"],
        },
        "strategies": strategies["summary"],
        "readiness": get_readiness(connection, provider_payload),
    }
