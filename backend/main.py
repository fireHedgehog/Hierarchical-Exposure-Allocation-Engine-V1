from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterator, Literal, Mapping

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend import __version__
from backend.admin_models import (
    CredentialWriteRequest,
    EngineModeWriteRequest,
    PipelineRunRequest,
    ProviderVerifyRequest,
    SignalValidationRunRequest,
    StrategyBacktestRunRequest,
)
from backend.admin_repository import (
    PipelineNotFoundError,
    ProviderNotFoundError,
    StrategyNotFoundError,
    SymbolNotInStagingUniverseError,
    add_to_watchlist,
    get_data_inventory,
    get_overview,
    get_pipeline,
    get_provider,
    get_strategy,
    list_providers,
    list_staging_symbols,
    list_strategies,
    list_watchlist,
    mark_credential_changed,
    remove_from_watchlist,
    run_pipeline,
    set_engine_mode,
    utc_now,
    verify_provider,
)
from backend.admin_security import direct_loopback_guard, operator_guard, validate_admin_origins
from backend.database import PROJECT_ROOT, connect, initialize_database, resolve_database_path
from backend.pipeline.stages import FredFetcher, PriceFetcher
from backend.pipeline.stages.common import STAGING_UNIVERSE_START_DATE
from backend.pipeline_progress import finish_run as finish_background_run
from backend.pipeline_progress import get_progress
from backend.pipeline_progress import start_run as start_background_run
from backend.universe.library_fetch import DEFAULT_BATCH_SIZE as DEFAULT_LIBRARY_FETCH_BATCH_SIZE
from backend.universe.library_fetch import fetch_library_batch, get_library_fetch_coverage
from backend.universe.earnings_fetch import (
    DEFAULT_BATCH_SIZE as DEFAULT_RESULTS_FILING_FETCH_BATCH_SIZE,
    DEFAULT_START_DATE as DEFAULT_RESULTS_FILING_START_DATE,
    fetch_results_filing_batch,
    get_results_filing_coverage_summary,
)
from backend.providers import ProviderVerifier
from backend.providers.fred import FredV2Verifier, fetch_series_observations
from backend.providers.sec_edgar import (
    SecEdgarFetchError,
    SecSubmissionHistory,
    SecTickerIdentity,
    fetch_company_ticker_map,
    fetch_results_filings,
)
from backend.providers.yahoo import PriceFetchError, fetch_daily_bars
from backend.repository import (
    SnapshotNotFoundError,
    SymbolNotFoundError,
    get_latest_cross_section,
    get_latest_desk,
    get_latest_snapshot_meta,
    get_latest_symbol,
    list_latest_symbols,
)
from backend.engine.factors import InsufficientBacktestHistoryError
from backend.research_repository import (
    DatasetNotSealedError,
    UnsupportedSignalValidationFamilyError,
    UnsupportedStrategyBacktestFamilyError,
    get_latest_factor_significance_run,
    get_latest_momentum_significance_run,
    get_latest_signal_validation_run,
    get_latest_strategy_backtest_run,
    get_latest_timing_signal_significance_run,
    run_factor_significance_research,
    run_momentum_significance_research,
    run_signal_validation_research,
    run_strategy_backtest_research,
    run_timing_signal_significance_research,
)
from backend.secrets import (
    KeyringEnvironmentSecretStore,
    SecretStore,
    SecretStoreUnavailable,
)


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": code, "message": message})


def create_app(
    database_path: str | Path | None = None,
    *,
    frontend_dist: str | Path | None = None,
    secret_store: SecretStore | None = None,
    provider_verifiers: Mapping[str, ProviderVerifier] | None = None,
    fred_observation_fetcher: FredFetcher | None = None,
    price_fetcher: PriceFetcher | None = None,
    sec_ticker_map_fetcher: Callable[[str], dict[str, tuple[SecTickerIdentity, ...]]] | None = None,
    sec_submission_fetcher: Callable[..., SecSubmissionHistory] | None = None,
    sec_user_agent: str | None = None,
    now: Callable[[], datetime] | None = None,
) -> FastAPI:
    path = resolve_database_path(database_path or os.getenv("HEAE_DATABASE_PATH"))
    static_root = Path(frontend_dist) if frontend_dist is not None else PROJECT_ROOT / "frontend" / "dist"
    secrets = secret_store or KeyringEnvironmentSecretStore()
    verifiers = dict(provider_verifiers or {"fred_v2": FredV2Verifier()})
    fred_fetcher = fred_observation_fetcher or fetch_series_observations
    price_fetcher_fn = price_fetcher or fetch_daily_bars
    sec_ticker_fetcher_fn = sec_ticker_map_fetcher or fetch_company_ticker_map
    sec_submission_fetcher_fn = sec_submission_fetcher or fetch_results_filings
    sec_user_agent_value = sec_user_agent if sec_user_agent is not None else os.getenv("HEAE_SEC_USER_AGENT", "")
    now_fn = now or utc_now
    runtime_id = f"runtime-{uuid.uuid4()}"
    provider_operation_locks: dict[str, threading.Lock] = {}
    provider_operation_locks_guard = threading.Lock()
    results_filing_fetch_lock = threading.Lock()
    admin_origins = validate_admin_origins(os.getenv("HEAE_ADMIN_ALLOWED_ORIGINS"))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Schema creation is safe and honest; synthetic content remains explicit opt-in.
        initialize_database(path)
        yield

    application = FastAPI(
        title="Hierarchical Exposure Allocation Engine API",
        version=__version__,
        description="Decision-state reads with a loopback-only local operator console. Empty databases remain empty until ingestion or an explicit seed runs.",
        lifespan=lifespan,
    )
    application.state.database_path = path
    application.state.frontend_dist = static_root
    application.state.secret_store = secrets
    application.state.provider_verifiers = verifiers
    application.state.fred_observation_fetcher = fred_fetcher
    application.state.price_fetcher = price_fetcher_fn
    application.state.sec_ticker_map_fetcher = sec_ticker_fetcher_fn
    application.state.sec_submission_fetcher = sec_submission_fetcher_fn
    application.state.admin_origins = admin_origins
    application.state.runtime_id = runtime_id
    application.state.provider_operation_locks = provider_operation_locks

    @contextmanager
    def serialized_provider_operation(provider_key: str) -> Iterator[str]:
        """Serialize credential mutation and verification for one provider.

        The lock begins before any credential/revision read and remains held
        through the external secret-store operation and final serialization.
        This is an in-process boundary for the local single-worker draft.
        """

        normalized_key = provider_key.strip().lower()
        with connect(path, read_only=True) as connection:
            exists = connection.execute(
                "SELECT 1 FROM operator_providers WHERE provider_key = ?",
                (normalized_key,),
            ).fetchone()
        if exists is None:
            raise ProviderNotFoundError(provider_key)
        with provider_operation_locks_guard:
            provider_lock = provider_operation_locks.setdefault(
                normalized_key, threading.Lock()
            )
        if not provider_lock.acquire(timeout=7.0):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "provider_operation_in_progress",
                    "message": "Another credential or smoke-verification operation is already in progress for this provider.",
                },
            )
        try:
            yield normalized_key
        finally:
            provider_lock.release()

    configured_origins = os.getenv(
        "HEAE_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
    )
    origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Operator-Action"],
    )

    @application.middleware("http")
    async def response_hardening(request: Any, call_next: Callable[..., Any]) -> Any:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(RequestValidationError)
    async def sanitized_validation_error(
        _request: Any, error: RequestValidationError
    ) -> JSONResponse:
        # Pydantic's default error rendering includes the rejected `input`, which
        # can be a credential supplied to an invalid request. Keep useful field
        # locations and messages while dropping inputs and validation context.
        sanitized = [
            {
                "type": item.get("type", "validation_error"),
                "loc": item.get("loc", ()),
                "msg": item.get("msg", "Invalid request value."),
            }
            for item in error.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": sanitized})

    @application.exception_handler(SecretStoreUnavailable)
    async def credential_store_unavailable(
        _request: Any, _error: SecretStoreUnavailable
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "credential_store_unavailable",
                    "message": "Credential storage is unavailable and no environment fallback could be resolved.",
                }
            },
        )

    @application.get("/api/health", tags=["system"])
    def health() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            snapshot = get_latest_snapshot_meta(connection)
            metadata = {
                row["key"]: row["value"]
                for row in connection.execute(
                    "SELECT key, value FROM schema_metadata ORDER BY key"
                ).fetchall()
            }
        return {
            "status": "ok",
            "service": "hierarchical-exposure-allocation-engine",
            "version": __version__,
            "read_only_api": False,
            "decision_api_read_only": True,
            "operator_api_local_only": True,
            "operator_mutations_local_only": True,
            "data_status": snapshot["status"] if snapshot is not None else "empty",
            "snapshot": snapshot,
            "schema_version": metadata.get("schema_version"),
            "seed_policy": metadata.get("seed_policy"),
        }

    @application.get("/api/v1/desk/latest", tags=["desk"])
    def desk_latest() -> dict[str, Any]:
        try:
            with connect(path, read_only=True) as connection:
                return get_latest_desk(connection)
        except SnapshotNotFoundError as error:
            raise _not_found(
                "snapshot_not_found",
                "No desk snapshot is available. Run live ingestion or explicitly seed the synthetic demo.",
            ) from error

    @application.get("/api/v1/cross-section/latest", tags=["desk"])
    def cross_section_latest() -> dict[str, Any]:
        try:
            with connect(path, read_only=True) as connection:
                return get_latest_cross_section(connection)
        except SnapshotNotFoundError as error:
            raise _not_found(
                "snapshot_not_found",
                "No cross-sectional snapshot is available.",
            ) from error

    @application.get("/api/v1/symbols", tags=["symbols"])
    def symbols(scope: Literal["watchlist", "all"] = "watchlist") -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            return list_latest_symbols(connection, scope=scope)

    @application.get("/api/v1/symbols/{symbol}", tags=["symbols"])
    def symbol_detail(symbol: str) -> dict[str, Any]:
        try:
            with connect(path, read_only=True) as connection:
                return get_latest_symbol(connection, symbol)
        except SnapshotNotFoundError as error:
            raise _not_found(
                "snapshot_not_found",
                "No desk snapshot is available.",
            ) from error
        except SymbolNotFoundError as error:
            raise _not_found(
                "symbol_not_found",
                f"Symbol {error.args[0]} is not present in the latest snapshot.",
            ) from error

    @application.get(
        "/api/v1/admin/overview",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_overview() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            return get_overview(connection, secrets, now_fn(), runtime_id)

    @application.get(
        "/api/v1/admin/providers",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_providers() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            return list_providers(connection, secrets, now_fn(), runtime_id)

    @application.put(
        "/api/v1/admin/providers/{provider_key}/credential",
        tags=["operator"],
        dependencies=[Depends(operator_guard("credential.write", admin_origins))],
    )
    def admin_write_credential(
        provider_key: str, payload: CredentialWriteRequest
    ) -> dict[str, Any]:
        invalidation_committed = False
        try:
            with serialized_provider_operation(provider_key) as normalized_key:
                timestamp = now_fn()
                with connect(path, read_only=True) as connection:
                    provider = get_provider(
                        connection, normalized_key, secrets, timestamp, runtime_id
                    )
                    if (
                        provider["credential"]["configured"]
                        and not provider["credential"]["managed"]
                    ):
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "code": "credential_environment_managed",
                                "message": f"Unset {provider['credential']['environment_variable']} before storing an OS-managed credential.",
                            },
                        )
                    credential_name = connection.execute(
                        "SELECT credential_name FROM operator_providers WHERE provider_key = ?",
                        (provider["key"],),
                    ).fetchone()["credential_name"]
                # Commit invalidation before touching the external credential
                # store. The provider lock prevents a verifier from testing the
                # old key under the new revision during this interval.
                with connect(path) as connection:
                    mark_credential_changed(connection, provider["key"], timestamp)
                invalidation_committed = True
                # The request model masks its repr, and only this call unwraps it.
                secrets.set(credential_name, payload.secret.get_secret_value())
                with connect(path, read_only=True) as connection:
                    result = get_provider(
                        connection, provider["key"], secrets, timestamp, runtime_id
                    )
        except ProviderNotFoundError as error:
            raise _not_found("provider_not_found", f"Provider {provider_key} is not registered.") from error
        except sqlite3.Error as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "operator_state_unavailable",
                    "message": (
                        "Credential metadata could not be read after prior health was invalidated."
                        if invalidation_committed
                        else "Credential metadata could not be updated; the credential store was not changed."
                    ),
                },
            ) from error
        except SecretStoreUnavailable as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "credential_store_unavailable",
                    "message": "Credential storage is unavailable and no environment fallback could be resolved.",
                },
            ) from error
        return {"provider": result}

    @application.delete(
        "/api/v1/admin/providers/{provider_key}/credential",
        tags=["operator"],
        dependencies=[Depends(operator_guard("credential.delete", admin_origins))],
    )
    def admin_delete_credential(provider_key: str) -> dict[str, Any]:
        invalidation_committed = False
        try:
            with serialized_provider_operation(provider_key) as normalized_key:
                timestamp = now_fn()
                with connect(path, read_only=True) as connection:
                    row = connection.execute(
                        "SELECT * FROM operator_providers WHERE provider_key = ?",
                        (normalized_key,),
                    ).fetchone()
                    current = secrets.get(
                        row["credential_name"], row["environment_variable"]
                    )
                    if current is not None and not current.managed:
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "code": "credential_environment_managed",
                                "message": f"Unset {row['environment_variable']} in the server environment to remove this credential.",
                            },
                        )
                    credential_name = row["credential_name"]
                if current:
                    # As with rotation, invalidate health before the external
                    # delete while excluding concurrent verification.
                    with connect(path) as connection:
                        mark_credential_changed(
                            connection, normalized_key, timestamp
                        )
                    invalidation_committed = True
                    deleted = secrets.delete(credential_name)
                else:
                    deleted = False
                with connect(path, read_only=True) as connection:
                    result = get_provider(
                        connection,
                        normalized_key,
                        secrets,
                        timestamp,
                        runtime_id,
                    )
        except ProviderNotFoundError as error:
            raise _not_found("provider_not_found", f"Provider {provider_key} is not registered.") from error
        except sqlite3.Error as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "operator_state_unavailable",
                    "message": (
                        "Credential metadata could not be read after prior health was invalidated."
                        if invalidation_committed
                        else "Credential metadata could not be updated; the credential store was not changed."
                    ),
                },
            ) from error
        except SecretStoreUnavailable as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "credential_store_unavailable",
                    "message": "Credential storage is unavailable and no environment fallback could be resolved.",
                },
            ) from error
        return {"deleted": deleted, "provider": result}

    @application.post(
        "/api/v1/admin/providers/{provider_key}/verify",
        tags=["operator"],
        dependencies=[Depends(operator_guard("provider.verify", admin_origins))],
    )
    def admin_verify_provider(
        provider_key: str, _: ProviderVerifyRequest
    ) -> dict[str, Any]:
        try:
            with serialized_provider_operation(provider_key) as normalized_key:
                # No SQLite write transaction is held while provider I/O runs.
                with connect(path) as connection:
                    return verify_provider(
                        connection,
                        normalized_key,
                        secrets,
                        verifiers,
                        now_fn(),
                        runtime_id,
                    )
        except ProviderNotFoundError as error:
            raise _not_found("provider_not_found", f"Provider {provider_key} is not registered.") from error

    @application.get(
        "/api/v1/admin/data",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_data(
        scope: Literal["watchlist", "all"] = "watchlist",
        q: str | None = None,
        page: int = 1,
        page_size: int = 25,
        health: Literal["all", "unhealthy"] = "all",
        sort: str = "symbol",
        order: Literal["asc", "desc"] = "asc",
    ) -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            return get_data_inventory(
                connection, now_fn(), scope=scope, q=q, page=page, page_size=page_size,
                health=health, sort=sort, order=order,
            )

    @application.get(
        "/api/v1/admin/universe",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_universe() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            return list_staging_symbols(connection)

    @application.get(
        "/api/v1/admin/watchlist",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_watchlist_list() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            return list_watchlist(connection)

    @application.post(
        "/api/v1/admin/watchlist/{symbol}",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_watchlist_add(symbol: str) -> dict[str, Any]:
        with connect(path) as connection:
            try:
                return add_to_watchlist(connection, symbol, now_fn())
            except SymbolNotInStagingUniverseError as error:
                raise _not_found(
                    "symbol_not_in_universe",
                    f"{error} is not a fetched symbol -- it must exist in the data library before it can be watched.",
                ) from error

    @application.delete(
        "/api/v1/admin/watchlist/{symbol}",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_watchlist_remove(symbol: str) -> dict[str, Any]:
        with connect(path) as connection:
            return remove_from_watchlist(connection, symbol)

    @application.post(
        "/api/v1/admin/data/{symbol}/test-fetch",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_data_test_fetch(symbol: str) -> dict[str, Any]:
        # Deliberately a diagnostic probe only -- no database write. Every
        # SEALED, PRODUCTION dataset snapshot in this schema is
        # architecturally "one coherent full-universe fetch"; patching a
        # single symbol into one of those would violate that invariant
        # everywhere downstream. This answers "is this symbol's real fetch
        # broken right now," nothing more. Real, persisting per-symbol
        # fetches for the extended data library go through
        # admin_library_fetch_batch below instead -- admin/production work
        # (fetching and storing data always is, per developer-letter.md),
        # writing into its own separate, always-mutable dataset snapshot,
        # never a sealed production one.
        normalized = symbol.strip().upper()
        try:
            bars = price_fetcher_fn(normalized, start_date=STAGING_UNIVERSE_START_DATE)
        except PriceFetchError as error:
            return {"symbol": normalized, "ok": False, "error": str(error)}
        if not bars:
            return {"symbol": normalized, "ok": False, "error": "Provider returned zero usable bars."}
        return {
            "symbol": normalized,
            "ok": True,
            "bar_count": len(bars),
            "period_start": min(bar.time for bar in bars),
            "period_end": max(bar.time for bar in bars),
        }

    @application.get(
        "/api/v1/admin/library-fetch",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_library_fetch_coverage() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            return get_library_fetch_coverage(connection)

    @application.post(
        "/api/v1/admin/library-fetch",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_library_fetch_batch(batch_size: int = DEFAULT_LIBRARY_FETCH_BATCH_SIZE) -> dict[str, Any]:
        # Real, per-symbol atomic fetch for the explicit stage-2 membership
        # cohort -- admin/production
        # work, deliberately NOT called "research fetch" (see developer-
        # letter.md) and deliberately NOT the live pipeline's
        # fetch_data_stage; never changes product eligibility or writes the
        # live product's dataset. Active/cohort overlaps remain active. One bad symbol in this batch never blocks the rest, and
        # never blocks the live Today-desk product's own daily refresh.
        # Naturally resumable -- already-fetched symbols are skipped, so
        # repeated clicks over multiple sessions just continue.
        safe_batch_size = max(1, min(batch_size, 100))
        with connect(path) as connection:
            return fetch_library_batch(connection, price_fetcher_fn, now_fn(), batch_size=safe_batch_size)

    @application.get(
        "/api/v1/admin/results-filings/coverage",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_results_filing_coverage() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            return get_results_filing_coverage_summary(connection)

    @application.post(
        "/api/v1/admin/results-filings/fetch",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_results_filing_fetch(
        batch_size: int = DEFAULT_RESULTS_FILING_FETCH_BATCH_SIZE,
        start_date: date = DEFAULT_RESULTS_FILING_START_DATE,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        # Bounded source ingestion only: this records SEC Item 2.02 filing
        # rows, never launches a hypothesis, and never changes live strategy
        # state. One process lock prevents two browser tabs doubling traffic.
        if not sec_user_agent_value.strip():
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "sec_user_agent_required",
                    "message": "Set HEAE_SEC_USER_AGENT to an application name and contact email before SEC ingestion.",
                },
            )
        if not results_filing_fetch_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "results_filing_fetch_in_progress",
                    "message": "Another SEC results-filing batch is already running.",
                },
            )
        try:
            safe_batch_size = max(1, min(batch_size, 100))
            with connect(path) as connection:
                return fetch_results_filing_batch(
                    connection,
                    sec_user_agent_value,
                    now_fn(),
                    batch_size=safe_batch_size,
                    start_date=start_date,
                    end_date=end_date,
                    ticker_map_fetcher=sec_ticker_fetcher_fn,
                    submission_fetcher=sec_submission_fetcher_fn,
                )
        except SecEdgarFetchError as error:
            raise HTTPException(
                status_code=502,
                detail={"code": "sec_edgar_fetch_failed", "message": str(error)},
            ) from error
        finally:
            results_filing_fetch_lock.release()

    @application.get(
        "/api/v1/admin/pipeline",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_pipeline() -> dict[str, Any]:
        try:
            with connect(path, read_only=True) as connection:
                return get_pipeline(connection)
        except PipelineNotFoundError as error:
            raise _not_found("pipeline_not_found", "The daily desk pipeline is not registered.") from error

    @application.post(
        "/api/v1/admin/pipeline/runs",
        tags=["operator"],
        dependencies=[Depends(operator_guard("pipeline.run", admin_origins))],
    )
    def admin_run_pipeline(payload: PipelineRunRequest) -> dict[str, Any]:
        try:
            with connect(path) as connection:
                return run_pipeline(
                    connection,
                    secrets,
                    now_fn(),
                    dry_run=payload.dry_run,
                    runtime_id=runtime_id,
                    fred_observation_fetcher=fred_fetcher,
                    price_fetcher=price_fetcher_fn,
                    stop_after=payload.stop_after,
                    reuse_latest_dataset=payload.reuse_latest_dataset,
                )
        except PipelineNotFoundError as error:
            raise _not_found("pipeline_not_found", "The daily desk pipeline is not available.") from error

    @application.post(
        "/api/v1/admin/pipeline/runs/start",
        tags=["operator"],
        dependencies=[Depends(operator_guard("pipeline.run", admin_origins))],
    )
    def admin_start_pipeline_run(payload: PipelineRunRequest) -> dict[str, Any]:
        # Real, direct user request: live progress ("step 1 fetching
        # 1/22..."), which needs the run to happen in the background --
        # one HTTP request can't stay open long enough to stream it, and
        # blocking the request until the whole pipeline finishes is
        # exactly the opaque black box being fixed here. This starts a
        # real background thread with its own DB connection (SQLite
        # connections aren't safe to share across threads) and returns
        # immediately; poll admin_pipeline_run_progress for live status.
        progress_run_id = str(uuid.uuid4())
        start_background_run(progress_run_id)

        def _execute() -> None:
            try:
                with connect(path) as thread_connection:
                    result = run_pipeline(
                        thread_connection,
                        secrets,
                        now_fn(),
                        dry_run=payload.dry_run,
                        runtime_id=runtime_id,
                        fred_observation_fetcher=fred_fetcher,
                        price_fetcher=price_fetcher_fn,
                        stop_after=payload.stop_after,
                        progress_run_id=progress_run_id,
                        reuse_latest_dataset=payload.reuse_latest_dataset,
                    )
                finish_background_run(progress_run_id, result)
            except Exception as error:  # a background thread's exception must be captured, not silently lost
                finish_background_run(progress_run_id, None, error=str(error))

        threading.Thread(target=_execute, daemon=True).start()
        return {"progress_run_id": progress_run_id}

    @application.get(
        "/api/v1/admin/pipeline/runs/{progress_run_id}/progress",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_pipeline_run_progress(progress_run_id: str) -> dict[str, Any]:
        progress = get_progress(progress_run_id)
        if progress is None:
            raise _not_found("progress_not_found", "No background run with this id is known to this server.")
        return progress

    @application.put(
        "/api/v1/admin/engine-mode",
        tags=["operator"],
        dependencies=[Depends(operator_guard("engine_mode.write", admin_origins))],
    )
    def admin_write_engine_mode(payload: EngineModeWriteRequest) -> dict[str, Any]:
        with connect(path) as connection:
            return {
                "engine_mode": set_engine_mode(
                    connection, payload.mode, now_fn(), payload.reason
                )
            }

    @application.get(
        "/api/v1/admin/strategies",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_strategies() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            return list_strategies(connection)

    @application.get(
        "/api/v1/admin/strategies/{strategy_key}",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_strategy(strategy_key: str) -> dict[str, Any]:
        try:
            with connect(path, read_only=True) as connection:
                return get_strategy(connection, strategy_key)
        except StrategyNotFoundError as error:
            raise _not_found("strategy_not_found", f"Strategy {strategy_key} is not registered.") from error

    @application.post(
        "/api/v1/admin/research/factor-significance/runs",
        tags=["operator"],
        dependencies=[Depends(operator_guard("research.run_factor_significance", admin_origins))],
    )
    def admin_run_factor_significance_research() -> dict[str, Any]:
        try:
            with connect(path) as connection:
                return {"run": run_factor_significance_research(connection, now_fn())}
        except DatasetNotSealedError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "dataset_not_sealed", "message": str(error)},
            ) from error

    @application.get(
        "/api/v1/admin/research/factor-significance/latest",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_latest_factor_significance_research() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            run = get_latest_factor_significance_run(connection)
        if run is None:
            raise _not_found(
                "factor_significance_run_not_found",
                "No factor-significance research run has been recorded yet.",
            )
        return {"run": run}

    @application.post(
        "/api/v1/admin/research/signal-validation/runs",
        tags=["operator"],
        dependencies=[Depends(operator_guard("research.run_signal_validation", admin_origins))],
    )
    def admin_run_signal_validation_research(payload: SignalValidationRunRequest) -> dict[str, Any]:
        try:
            with connect(path) as connection:
                return {"run": run_signal_validation_research(connection, now_fn(), payload.strategy_key)}
        except DatasetNotSealedError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "dataset_not_sealed", "message": str(error)},
            ) from error
        except UnsupportedSignalValidationFamilyError as error:
            raise HTTPException(
                status_code=422,
                detail={"code": "signal_validation_unsupported", "message": str(error)},
            ) from error

    @application.get(
        "/api/v1/admin/research/signal-validation/latest",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_latest_signal_validation_research(strategy_key: str) -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            run = get_latest_signal_validation_run(connection, strategy_key)
        if run is None:
            raise _not_found(
                "signal_validation_run_not_found",
                f"No signal-validation research run has been recorded yet for {strategy_key}.",
            )
        return {"run": run}

    @application.post(
        "/api/v1/admin/research/momentum-significance/runs",
        tags=["operator"],
        dependencies=[Depends(operator_guard("research.run_momentum_significance", admin_origins))],
    )
    def admin_run_momentum_significance_research() -> dict[str, Any]:
        try:
            with connect(path) as connection:
                return {"run": run_momentum_significance_research(connection, now_fn())}
        except DatasetNotSealedError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "dataset_not_sealed", "message": str(error)},
            ) from error

    @application.get(
        "/api/v1/admin/research/momentum-significance/latest",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_latest_momentum_significance_research() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            run = get_latest_momentum_significance_run(connection)
        if run is None:
            raise _not_found(
                "momentum_significance_run_not_found",
                "No momentum-significance research run has been recorded yet.",
            )
        return {"run": run}

    @application.post(
        "/api/v1/admin/research/timing-signal-significance/runs",
        tags=["operator"],
        dependencies=[Depends(operator_guard("research.run_timing_signal_significance", admin_origins))],
    )
    def admin_run_timing_signal_significance_research() -> dict[str, Any]:
        try:
            with connect(path) as connection:
                return {"run": run_timing_signal_significance_research(connection, now_fn())}
        except DatasetNotSealedError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "dataset_not_sealed", "message": str(error)},
            ) from error

    @application.get(
        "/api/v1/admin/research/timing-signal-significance/latest",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_latest_timing_signal_significance_research() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            run = get_latest_timing_signal_significance_run(connection)
        if run is None:
            raise _not_found(
                "timing_signal_significance_run_not_found",
                "No timing-signal-significance research run has been recorded yet.",
            )
        return {"run": run}

    @application.post(
        "/api/v1/admin/research/strategy-backtest/runs",
        tags=["operator"],
        dependencies=[Depends(operator_guard("research.run_strategy_backtest", admin_origins))],
    )
    def admin_run_strategy_backtest_research(payload: StrategyBacktestRunRequest) -> dict[str, Any]:
        try:
            with connect(path) as connection:
                return {"run": run_strategy_backtest_research(connection, now_fn(), payload.strategy_key)}
        except DatasetNotSealedError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "dataset_not_sealed", "message": str(error)},
            ) from error
        except UnsupportedStrategyBacktestFamilyError as error:
            raise HTTPException(
                status_code=422,
                detail={"code": "strategy_backtest_unsupported", "message": str(error)},
            ) from error
        except InsufficientBacktestHistoryError as error:
            raise HTTPException(
                status_code=422,
                detail={"code": "insufficient_backtest_history", "message": str(error)},
            ) from error

    @application.get(
        "/api/v1/admin/research/strategy-backtest/latest",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_latest_strategy_backtest_research(strategy_key: str) -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            run = get_latest_strategy_backtest_run(connection, strategy_key)
        if run is None:
            raise _not_found(
                "strategy_backtest_run_not_found",
                f"No strategy-backtest research run has been recorded yet for {strategy_key}.",
            )
        return {"run": run}

    @application.get(
        "/api/v1/admin/research/metric-catalog",
        tags=["operator"],
        dependencies=[Depends(direct_loopback_guard)],
    )
    def admin_research_metric_catalog() -> dict[str, Any]:
        with connect(path, read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT c.metric_key, c.category, c.granularity, c.label, c.unit, c.description,
                       c.applicable_families_json, c.sort_order,
                       EXISTS(SELECT 1 FROM research_run_metrics m WHERE m.metric_key = c.metric_key) AS has_data
                FROM research_metric_catalog c ORDER BY c.sort_order
                """
            ).fetchall()
        return {
            "metrics": [
                {
                    "metric_key": row["metric_key"],
                    "category": row["category"],
                    "granularity": row["granularity"],
                    "label": row["label"],
                    "unit": row["unit"],
                    "description": row["description"],
                    "applicable_families": json.loads(row["applicable_families_json"]),
                    "has_data": bool(row["has_data"]),
                }
                for row in rows
            ]
        }

    @application.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise _not_found("route_not_found", "API route does not exist.")
        root = application.state.frontend_dist.resolve()
        index_path = root / "index.html"
        if not index_path.is_file():
            raise _not_found("frontend_not_built", "The frontend production bundle is not present.")
        requested = (root / full_path).resolve()
        if requested.is_relative_to(root) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(index_path)

    return application


app = create_app()
