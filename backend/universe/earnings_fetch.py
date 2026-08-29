"""Resumable admin ingestion for the disposable SEC results-filing ledger.

The filename remains stable to avoid pointless module churn, but the data
contract is deliberately *not* an earnings-event contract. Item 2.02 filing
rows and SEC acceptance timestamps are source proxies awaiting later event
classification and issuer-release timestamp work.
"""

from __future__ import annotations

import sqlite3
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

from backend.pipeline.stages.common import _iso_z
from backend.providers.sec_edgar import (
    SecEdgarBatchDeferred,
    SecEdgarFetchError,
    SecSubmissionHistory,
    SecTickerIdentity,
    fetch_company_ticker_map,
    fetch_results_filings,
    normalize_sec_ticker,
)


SOURCE_KEY = "sec_edgar"
RESULTS_CONTRACT_REVISION = "sec-current-cik-item-2.02-v2"
RESULTS_UNIVERSE_STAGE = "stage-2"
DEFAULT_BATCH_SIZE = 25
DEFAULT_START_DATE = date(2004, 8, 23)  # modern Form 8-K Item 2.02 regime
DEFAULT_END_DATE = date(2026, 8, 27)  # last fully completed ET day for this checkpoint
MAX_BATCH_SIZE = 100
_ET = ZoneInfo("America/New_York")

TickerMapFetcher = Callable[[str], dict[str, tuple[SecTickerIdentity, ...]]]
SubmissionFetcher = Callable[..., SecSubmissionHistory]


def _identity_revision(identities: tuple[SecTickerIdentity, ...]) -> str:
    payload = [
        {"cik": identity.cik, "ticker": identity.ticker, "title": identity.title}
        for identity in identities
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _issuer_form_class(forms_seen: frozenset[str]) -> str:
    has_8k = bool({"8-K", "8-K/A"} & forms_seen)
    has_6k = bool({"6-K", "6-K/A"} & forms_seen)
    if has_8k and has_6k:
        return "mixed"
    if has_8k:
        return "domestic_8k"
    if has_6k:
        return "foreign_6k"
    return "unknown"


def _coverage_status(history: SecSubmissionHistory, issuer_form_class: str) -> str:
    if history.filings:
        return "retrieved_current_cik_8k_2_02_rows"
    if history.scoped_submission_row_count == 0:
        return "no_filings_in_requested_range"
    if history.items_metadata_missing_count:
        return "item_metadata_missing"
    if issuer_form_class == "foreign_6k":
        return "foreign_6k_unsupported"
    return "no_matching_2_02_in_current_cik"


def _write_success_status(
    connection: sqlite3.Connection,
    *,
    security_id: str,
    symbol: str,
    resolved_cik: str | None,
    identity_revision: str,
    identity_status: str,
    issuer_form_class: str,
    coverage_status: str,
    start_date: date,
    end_date: date,
    first_result_filing_date: str | None,
    last_result_filing_date: str | None,
    filing_count: int,
    items_metadata_missing_count: int,
    row_parse_error_count: int,
    attempted_at: str,
    coverage_complete: bool,
) -> None:
    covered_from = start_date.isoformat() if coverage_complete else None
    covered_to = end_date.isoformat() if coverage_complete else None
    connection.execute(
        """
        INSERT INTO staging_results_filing_fetch_status (
            security_id, source_key, contract_revision, identity_revision,
            requested_symbol, resolved_cik, last_attempted_cik,
            last_attempt_identity_revision,
            identity_status, lineage_scope, issuer_form_class, coverage_status,
            last_requested_from, last_requested_to, covered_from, covered_to,
            first_result_filing_date, last_result_filing_date, filing_count,
            items_metadata_missing_count, row_parse_error_count,
            last_successful_at, last_attempted_at, attempt_count, last_error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'current_cik_only', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, NULL)
        ON CONFLICT(security_id, source_key) DO UPDATE SET
            contract_revision = excluded.contract_revision,
            identity_revision = excluded.identity_revision,
            requested_symbol = excluded.requested_symbol,
            resolved_cik = excluded.resolved_cik,
            last_attempted_cik = excluded.last_attempted_cik,
            last_attempt_identity_revision = excluded.last_attempt_identity_revision,
            identity_status = excluded.identity_status,
            lineage_scope = excluded.lineage_scope,
            issuer_form_class = excluded.issuer_form_class,
            coverage_status = excluded.coverage_status,
            last_requested_from = excluded.last_requested_from,
            last_requested_to = excluded.last_requested_to,
            covered_from = excluded.covered_from,
            covered_to = excluded.covered_to,
            first_result_filing_date = excluded.first_result_filing_date,
            last_result_filing_date = excluded.last_result_filing_date,
            filing_count = excluded.filing_count,
            items_metadata_missing_count = excluded.items_metadata_missing_count,
            row_parse_error_count = excluded.row_parse_error_count,
            last_successful_at = excluded.last_successful_at,
            last_attempted_at = excluded.last_attempted_at,
            attempt_count = staging_results_filing_fetch_status.attempt_count + 1,
            last_error = NULL
        """,
        (
            security_id,
            SOURCE_KEY,
            RESULTS_CONTRACT_REVISION,
            identity_revision,
            symbol,
            resolved_cik,
            resolved_cik,
            identity_revision,
            identity_status,
            issuer_form_class,
            coverage_status,
            start_date.isoformat(),
            end_date.isoformat(),
            covered_from,
            covered_to,
            first_result_filing_date,
            last_result_filing_date,
            filing_count,
            items_metadata_missing_count,
            row_parse_error_count,
            attempted_at,
            attempted_at,
        ),
    )


def _write_failure_status(
    connection: sqlite3.Connection,
    *,
    security_id: str,
    symbol: str,
    resolved_cik: str,
    identity_revision: str,
    start_date: date,
    end_date: date,
    attempted_at: str,
    error: str,
) -> None:
    """Record an attempt without erasing any earlier successful coverage."""

    connection.execute(
        """
        INSERT INTO staging_results_filing_fetch_status (
            security_id, source_key, contract_revision, identity_revision,
            requested_symbol, resolved_cik, last_attempted_cik,
            last_attempt_identity_revision,
            identity_status, lineage_scope, issuer_form_class, coverage_status,
            last_requested_from, last_requested_to, covered_from, covered_to,
            first_result_filing_date, last_result_filing_date, filing_count,
            items_metadata_missing_count, row_parse_error_count,
            last_successful_at, last_attempted_at, attempt_count, last_error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'matched', 'current_cik_only', 'unknown', 'failed',
                  ?, ?, NULL, NULL, NULL, NULL, 0, 0, 0, NULL, ?, 1, ?)
        ON CONFLICT(security_id, source_key) DO UPDATE SET
            requested_symbol = excluded.requested_symbol,
            contract_revision = CASE
                WHEN staging_results_filing_fetch_status.last_successful_at IS NULL
                THEN excluded.contract_revision
                ELSE staging_results_filing_fetch_status.contract_revision
            END,
            identity_revision = CASE
                WHEN staging_results_filing_fetch_status.last_successful_at IS NULL
                THEN excluded.identity_revision
                ELSE staging_results_filing_fetch_status.identity_revision
            END,
            resolved_cik = CASE
                WHEN staging_results_filing_fetch_status.last_successful_at IS NULL
                THEN excluded.resolved_cik
                ELSE staging_results_filing_fetch_status.resolved_cik
            END,
            last_attempted_cik = excluded.last_attempted_cik,
            last_attempt_identity_revision = excluded.last_attempt_identity_revision,
            last_requested_from = CASE
                WHEN staging_results_filing_fetch_status.last_successful_at IS NULL
                THEN excluded.last_requested_from
                ELSE staging_results_filing_fetch_status.last_requested_from
            END,
            last_requested_to = CASE
                WHEN staging_results_filing_fetch_status.last_successful_at IS NULL
                THEN excluded.last_requested_to
                ELSE staging_results_filing_fetch_status.last_requested_to
            END,
            coverage_status = CASE
                WHEN staging_results_filing_fetch_status.last_successful_at IS NULL THEN 'failed'
                ELSE staging_results_filing_fetch_status.coverage_status
            END,
            last_attempted_at = excluded.last_attempted_at,
            attempt_count = staging_results_filing_fetch_status.attempt_count + 1,
            last_error = excluded.last_error
        """,
        (
            security_id,
            SOURCE_KEY,
            RESULTS_CONTRACT_REVISION,
            identity_revision,
            symbol,
            resolved_cik,
            resolved_cik,
            identity_revision,
            start_date.isoformat(),
            end_date.isoformat(),
            attempted_at,
            error,
        ),
    )


def _candidate_rows(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
    batch_size: int,
    ticker_map: dict[str, tuple[SecTickerIdentity, ...]],
) -> list[dict]:
    rows = connection.execute(
        """
        WITH cohort AS (
            SELECT DISTINCT symbol
            FROM staging_universe_membership
            WHERE stage = ?
        ),
        security_map AS (
            SELECT primary_symbol, MIN(security_id) AS security_id, COUNT(*) AS match_count
            FROM securities
            GROUP BY primary_symbol
        )
        SELECT s.symbol, s.sort_order, security_map.security_id,
               status.contract_revision AS status_contract_revision,
               status.identity_revision AS status_identity_revision,
               status.requested_symbol AS status_requested_symbol,
               status.resolved_cik AS status_resolved_cik,
               status.identity_status AS status_identity_status,
               status.coverage_status AS status_coverage_status,
               status.covered_from AS status_covered_from,
               status.covered_to AS status_covered_to
        FROM cohort
        JOIN staging_symbols AS s ON s.symbol = cohort.symbol
        JOIN security_map
          ON security_map.primary_symbol = s.symbol AND security_map.match_count = 1
        LEFT JOIN staging_results_filing_fetch_status AS status
          ON status.security_id = security_map.security_id AND status.source_key = ?
        ORDER BY s.sort_order
        """,
        (RESULTS_UNIVERSE_STAGE, SOURCE_KEY),
    ).fetchall()
    due: list[dict] = []
    for row in rows:
        item = dict(row)
        identities = tuple(ticker_map.get(normalize_sec_ticker(row["symbol"]), ()))
        identity_revision = _identity_revision(identities)
        unique_ciks = {identity.cik for identity in identities}
        expected_cik = next(iter(unique_ciks)) if len(unique_ciks) == 1 else None
        identity_changed = (
            row["status_identity_revision"] != identity_revision
            or (
                expected_cik is not None
                and row["status_resolved_cik"] != expected_cik
            )
        )
        no_status = row["status_contract_revision"] is None
        contract_changed = row["status_contract_revision"] != RESULTS_CONTRACT_REVISION
        symbol_changed = row["status_requested_symbol"] != row["symbol"]
        source_failed = row["status_coverage_status"] == "failed"
        # Unmatched/ambiguous identities need a company-ticker-map revision
        # before another submissions request can help. A mismatch is different:
        # company_tickers and the issuer submissions payload can converge while
        # the company-ticker-map revision remains unchanged, so it stays
        # retryable on the next bounded batch.
        identity_is_terminal = len(unique_ciks) != 1
        coverage_missing = (
            row["status_covered_from"] is None
            or row["status_covered_to"] is None
            or row["status_covered_from"] > start_date.isoformat()
            or row["status_covered_to"] < end_date.isoformat()
        )
        if (
            no_status
            or contract_changed
            or symbol_changed
            or identity_changed
            or source_failed
            or (not identity_is_terminal and coverage_missing)
        ):
            item["current_identity_revision"] = identity_revision
            item["retry_order"] = 2 if source_failed else (0 if no_status else 1)
            due.append(item)
    due.sort(key=lambda item: (item["retry_order"], item["sort_order"]))
    return due[:batch_size]


def _mapping_counts(connection: sqlite3.Connection) -> tuple[int, int]:
    row = connection.execute(
        """
        WITH cohort AS (
            SELECT DISTINCT symbol
            FROM staging_universe_membership
            WHERE stage = ?
        ),
        security_map AS (
            SELECT primary_symbol, COUNT(*) AS match_count
            FROM securities
            GROUP BY primary_symbol
        )
        SELECT COUNT(*) AS eligible,
               SUM(CASE WHEN security_map.match_count = 1 THEN 1 ELSE 0 END) AS mapped
        FROM cohort
        LEFT JOIN security_map ON security_map.primary_symbol = cohort.symbol
        """,
        (RESULTS_UNIVERSE_STAGE,),
    ).fetchone()
    return row["eligible"], row["mapped"] or 0


def _remaining(
    connection: sqlite3.Connection,
    start_date: date,
    end_date: date,
    ticker_map: dict[str, tuple[SecTickerIdentity, ...]],
) -> int:
    return len(
        _candidate_rows(
            connection,
            start_date=start_date,
            end_date=end_date,
            batch_size=2_147_483_647,
            ticker_map=ticker_map,
        )
    )


def _remaining_from_stored_status(
    connection: sqlite3.Connection,
    start_date: date,
    end_date: date,
) -> int:
    row = connection.execute(
        """
        WITH cohort AS (
            SELECT DISTINCT symbol
            FROM staging_universe_membership
            WHERE stage = ?
        ),
        security_map AS (
            SELECT primary_symbol, MIN(security_id) AS security_id,
                   COUNT(*) AS match_count
            FROM securities
            GROUP BY primary_symbol
        )
        SELECT COUNT(*) AS remaining
        FROM cohort
        JOIN security_map
          ON security_map.primary_symbol = cohort.symbol
         AND security_map.match_count = 1
        LEFT JOIN staging_results_filing_fetch_status AS status
          ON status.security_id = security_map.security_id
         AND status.source_key = ?
        WHERE status.security_id IS NULL
           OR status.contract_revision IS NULL
           OR status.contract_revision != ?
           OR status.identity_revision IS NULL
           OR status.coverage_status = 'failed'
           OR status.last_attempted_cik IS NOT status.resolved_cik
           OR status.last_attempt_identity_revision IS NOT status.identity_revision
           OR (
               status.identity_status IN ('matched', 'mismatch')
               AND (
                   status.covered_from IS NULL OR status.covered_to IS NULL
                   OR status.covered_from > ? OR status.covered_to < ?
               )
           )
        """,
        (
            RESULTS_UNIVERSE_STAGE,
            SOURCE_KEY,
            RESULTS_CONTRACT_REVISION,
            start_date.isoformat(),
            end_date.isoformat(),
        ),
    ).fetchone()
    return row["remaining"]


def _unlink_security_filings(
    connection: sqlite3.Connection,
    *,
    security_id: str,
) -> None:
    connection.execute(
        "DELETE FROM staging_results_filing_securities "
        "WHERE security_id = ? AND source_key = ?",
        (security_id, SOURCE_KEY),
    )


def _store_filings_and_links(
    connection: sqlite3.Connection,
    *,
    security_id: str,
    symbol: str,
    history: SecSubmissionHistory,
    retrieved_at: str,
    start_date: date,
    end_date: date,
) -> set[str]:
    # Reconcile the successfully inspected window. Corrected CIK mappings
    # remove old-issuer links; same-CIK rows inside the requested acceptance
    # window are replaced by the source response. Rows outside a narrower
    # refresh window remain intact.
    connection.execute(
        """
        DELETE FROM staging_results_filing_securities
        WHERE security_id = ? AND source_key = ?
          AND accession_number IN (
              SELECT accession_number FROM staging_results_filings
              WHERE source_key = ?
                AND (
                    cik != ?
                    OR substr(sec_accepted_at_et, 1, 10) BETWEEN ? AND ?
                )
          )
        """,
        (
            security_id,
            SOURCE_KEY,
            SOURCE_KEY,
            history.cik,
            start_date.isoformat(),
            end_date.isoformat(),
        ),
    )

    seen: set[str] = set()
    for filing in history.filings:
        connection.execute(
            """
            INSERT INTO staging_results_filings (
                source_key, accession_number, cik, form, items, filing_date,
                report_date, sec_accepted_at_raw, sec_accepted_at_utc,
                sec_accepted_at_et, acceptance_parse_basis, timing_basis,
                timing_quality, primary_document, source_url, retrieved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sec_acceptance_proxy',
                      'filing_acceptance_proxy_not_first_public', ?, ?, ?)
            ON CONFLICT(source_key, accession_number) DO UPDATE SET
                cik = excluded.cik,
                form = excluded.form,
                items = excluded.items,
                filing_date = excluded.filing_date,
                report_date = excluded.report_date,
                sec_accepted_at_raw = excluded.sec_accepted_at_raw,
                sec_accepted_at_utc = excluded.sec_accepted_at_utc,
                sec_accepted_at_et = excluded.sec_accepted_at_et,
                acceptance_parse_basis = excluded.acceptance_parse_basis,
                primary_document = excluded.primary_document,
                source_url = excluded.source_url,
                retrieved_at = excluded.retrieved_at
            """,
            (
                SOURCE_KEY,
                filing.accession_number,
                filing.cik,
                filing.form,
                filing.items,
                filing.filing_date,
                filing.report_date,
                filing.acceptance_raw,
                filing.accepted_at_utc,
                filing.accepted_at_et,
                filing.acceptance_parse_basis,
                filing.primary_document,
                filing.source_url,
                retrieved_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO staging_results_filing_securities (
                source_key, accession_number, security_id, symbol_at_fetch, linked_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_key, accession_number, security_id) DO UPDATE SET
                symbol_at_fetch = excluded.symbol_at_fetch,
                linked_at = excluded.linked_at
            """,
            (SOURCE_KEY, filing.accession_number, security_id, symbol, retrieved_at),
        )
        seen.add(filing.accession_number)
    return seen


def fetch_results_filing_batch(
    connection: sqlite3.Connection,
    user_agent: str,
    now: datetime,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    start_date: date = DEFAULT_START_DATE,
    end_date: date | None = None,
    ticker_map_fetcher: TickerMapFetcher = fetch_company_ticker_map,
    submission_fetcher: SubmissionFetcher = fetch_results_filings,
) -> dict:
    """Fetch one bounded source-ingestion batch; never run a hypothesis."""

    if end_date is None:
        # Stable across a multi-day manual backfill. A later refresh advances
        # end_date explicitly instead of making yesterday's completed symbols
        # jump ahead of still-unattempted symbols every morning.
        end_date = DEFAULT_END_DATE
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    if end_date >= now.astimezone(_ET).date():
        raise ValueError("end_date must be a fully completed ET calendar date")
    if not user_agent.strip():
        raise SecEdgarFetchError(
            "Set HEAE_SEC_USER_AGENT to a descriptive application name and contact email before SEC ingestion."
        )
    safe_batch_size = max(1, min(int(batch_size), MAX_BATCH_SIZE))

    attempted_at = _iso_z(now)
    ticker_map = ticker_map_fetcher(user_agent)
    candidates = _candidate_rows(
        connection,
        start_date=start_date,
        end_date=end_date,
        batch_size=safe_batch_size,
        ticker_map=ticker_map,
    )

    processed: list[dict] = []
    failed: list[dict] = []
    batch_deferred: dict[str, str] | None = None
    history_cache: dict[str, SecSubmissionHistory | SecEdgarFetchError] = {}
    issuer_filings_seen: set[tuple[str, str]] = set()

    for row in candidates:
        symbol = row["symbol"]
        security_id = row["security_id"]
        normalized_symbol = normalize_sec_ticker(symbol)
        identities = tuple(ticker_map.get(normalized_symbol, ()))
        identity_revision = row["current_identity_revision"]

        if not identities:
            _unlink_security_filings(connection, security_id=security_id)
            _write_success_status(
                connection,
                security_id=security_id,
                symbol=symbol,
                resolved_cik=None,
                identity_revision=identity_revision,
                identity_status="unmatched",
                issuer_form_class="unknown",
                coverage_status="unmatched",
                start_date=start_date,
                end_date=end_date,
                first_result_filing_date=None,
                last_result_filing_date=None,
                filing_count=0,
                items_metadata_missing_count=0,
                row_parse_error_count=0,
                attempted_at=attempted_at,
                coverage_complete=False,
            )
            connection.commit()
            processed.append({"symbol": symbol, "status": "unmatched", "filing_count": 0})
            continue

        unique_ciks = {identity.cik for identity in identities}
        if len(unique_ciks) != 1:
            _unlink_security_filings(connection, security_id=security_id)
            _write_success_status(
                connection,
                security_id=security_id,
                symbol=symbol,
                resolved_cik=None,
                identity_revision=identity_revision,
                identity_status="ambiguous",
                issuer_form_class="unknown",
                coverage_status="ambiguous",
                start_date=start_date,
                end_date=end_date,
                first_result_filing_date=None,
                last_result_filing_date=None,
                filing_count=0,
                items_metadata_missing_count=0,
                row_parse_error_count=0,
                attempted_at=attempted_at,
                coverage_complete=False,
            )
            connection.commit()
            processed.append({"symbol": symbol, "status": "ambiguous", "filing_count": 0})
            continue

        cik = next(iter(unique_ciks))
        if cik not in history_cache:
            try:
                history_cache[cik] = submission_fetcher(
                    cik,
                    user_agent,
                    start_date=start_date,
                    end_date=end_date,
                )
            except SecEdgarBatchDeferred as error:
                message = str(error)
                _write_failure_status(
                    connection,
                    security_id=security_id,
                    symbol=symbol,
                    resolved_cik=cik,
                    identity_revision=identity_revision,
                    start_date=start_date,
                    end_date=end_date,
                    attempted_at=attempted_at,
                    error=message,
                )
                connection.commit()
                failed.append({"symbol": symbol, "error": message})
                batch_deferred = {"symbol": symbol, "error": message}
                break
            except SecEdgarFetchError as error:
                history_cache[cik] = error
            except Exception as error:
                history_cache[cik] = SecEdgarFetchError(
                    f"Unexpected SEC adapter failure ({error.__class__.__name__}): {error}"
                )
        history_or_error = history_cache[cik]

        if isinstance(history_or_error, SecEdgarFetchError):
            message = str(history_or_error)
            _write_failure_status(
                connection,
                security_id=security_id,
                symbol=symbol,
                resolved_cik=cik,
                identity_revision=identity_revision,
                start_date=start_date,
                end_date=end_date,
                attempted_at=attempted_at,
                error=message,
            )
            connection.commit()
            failed.append({"symbol": symbol, "error": message})
            continue

        history = history_or_error
        form_class = _issuer_form_class(history.forms_seen)
        if normalized_symbol not in history.current_tickers:
            _unlink_security_filings(connection, security_id=security_id)
            _write_success_status(
                connection,
                security_id=security_id,
                symbol=symbol,
                resolved_cik=cik,
                identity_revision=identity_revision,
                identity_status="mismatch",
                issuer_form_class=form_class,
                coverage_status="identity_mismatch",
                start_date=start_date,
                end_date=end_date,
                first_result_filing_date=history.first_result_filing_date,
                last_result_filing_date=history.last_result_filing_date,
                filing_count=0,
                items_metadata_missing_count=history.items_metadata_missing_count,
                row_parse_error_count=history.row_parse_error_count,
                attempted_at=attempted_at,
                coverage_complete=False,
            )
            connection.commit()
            processed.append(
                {"symbol": symbol, "status": "identity_mismatch", "filing_count": 0}
            )
            continue

        accessions = _store_filings_and_links(
            connection,
            security_id=security_id,
            symbol=symbol,
            history=history,
            retrieved_at=attempted_at,
            start_date=start_date,
            end_date=end_date,
        )
        issuer_filings_seen.update((SOURCE_KEY, accession) for accession in accessions)
        coverage = _coverage_status(history, form_class)
        _write_success_status(
            connection,
            security_id=security_id,
            symbol=symbol,
            resolved_cik=cik,
            identity_revision=identity_revision,
            identity_status="matched",
            issuer_form_class=form_class,
            coverage_status=coverage,
            start_date=start_date,
            end_date=end_date,
            first_result_filing_date=history.first_result_filing_date,
            last_result_filing_date=history.last_result_filing_date,
            filing_count=len(history.filings),
            items_metadata_missing_count=history.items_metadata_missing_count,
            row_parse_error_count=history.row_parse_error_count,
            attempted_at=attempted_at,
            coverage_complete=True,
        )
        connection.commit()
        processed.append(
            {"symbol": symbol, "status": coverage, "filing_count": len(history.filings)}
        )

    statuses = Counter(item["status"] for item in processed)
    eligible, mapped = _mapping_counts(connection)
    return {
        "source": SOURCE_KEY,
        "contract_revision": RESULTS_CONTRACT_REVISION,
        "record_kind": "sec_8k_item_2_02_filing_rows",
        "timing_basis": "sec_acceptance_proxy_not_first_public",
        "lineage_scope": "current_cik_only",
        "requested_from": start_date.isoformat(),
        "requested_to": end_date.isoformat(),
        "processed": processed,
        "failed": failed,
        "batch_deferred": batch_deferred,
        "issuer_filings_seen": len(issuer_filings_seen),
        "coverage": dict(sorted(statuses.items())),
        "remaining_fetchable": _remaining(connection, start_date, end_date, ticker_map),
        "blocked_by_security_mapping": max(eligible - mapped, 0),
    }


def get_results_filing_coverage_summary(
    connection: sqlite3.Connection,
    *,
    start_date: date = DEFAULT_START_DATE,
    end_date: date | None = None,
) -> dict:
    if end_date is None:
        end_date = DEFAULT_END_DATE
    eligible, mapped = _mapping_counts(connection)
    rows = connection.execute(
        """
        WITH cohort AS (
            SELECT DISTINCT symbol
            FROM staging_universe_membership
            WHERE stage = ?
        )
        SELECT status.coverage_status, COUNT(*) AS symbols,
               SUM(status.filing_count) AS filing_links
        FROM staging_results_filing_fetch_status AS status
        JOIN securities AS sec ON sec.security_id = status.security_id
        JOIN cohort ON cohort.symbol = sec.primary_symbol
        WHERE status.source_key = ? AND status.contract_revision = ?
        GROUP BY status.coverage_status
        ORDER BY status.coverage_status
        """,
        (RESULTS_UNIVERSE_STAGE, SOURCE_KEY, RESULTS_CONTRACT_REVISION),
    ).fetchall()
    by_status = {
        row["coverage_status"]: {
            "symbols": row["symbols"],
            "filing_links": row["filing_links"] or 0,
        }
        for row in rows
    }
    attempted = sum(item["symbols"] for item in by_status.values())
    raw_issuer_filings = connection.execute(
        "SELECT COUNT(*) AS n FROM staging_results_filings WHERE source_key = ?",
        (SOURCE_KEY,),
    ).fetchone()["n"]
    linked = connection.execute(
        """
        WITH cohort AS (
            SELECT DISTINCT symbol
            FROM staging_universe_membership
            WHERE stage = ?
        )
        SELECT COUNT(DISTINCT links.accession_number) AS issuer_filings,
               COUNT(*) AS security_links
        FROM staging_results_filing_securities AS links
        JOIN securities AS sec ON sec.security_id = links.security_id
        JOIN cohort ON cohort.symbol = sec.primary_symbol
        WHERE links.source_key = ?
        """,
        (RESULTS_UNIVERSE_STAGE, SOURCE_KEY),
    ).fetchone()
    issuer_filings = linked["issuer_filings"] or 0
    security_links = linked["security_links"] or 0
    return {
        "source": SOURCE_KEY,
        "contract_revision": RESULTS_CONTRACT_REVISION,
        "record_kind": "sec_8k_item_2_02_filing_rows",
        "timing_basis": "sec_acceptance_proxy_not_first_public",
        "lineage_scope": "current_cik_only",
        "requested_from": start_date.isoformat(),
        "requested_to": end_date.isoformat(),
        "eligible_symbols": eligible,
        "mapped_security_symbols": mapped,
        "blocked_by_security_mapping": max(eligible - mapped, 0),
        "attempted_symbols": attempted,
        "remaining_fetchable": _remaining_from_stored_status(
            connection, start_date, end_date
        ),
        "issuer_filings": issuer_filings,
        "raw_cached_issuer_filings": raw_issuer_filings,
        "orphan_cached_issuer_filings": max(raw_issuer_filings - issuer_filings, 0),
        "security_filing_links": security_links,
        "by_status": by_status,
    }
