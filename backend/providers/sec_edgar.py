"""Narrow SEC EDGAR adapter for auditable Item 2.02 filing rows.

The adapter deliberately stops at source facts. It retrieves Form 8-K/8-K/A
rows whose SEC structured ``items`` field contains the exact token ``2.02``.
Those rows are not automatically quarterly earnings events, and the EDGAR
acceptance timestamp is not automatically the issuer's first-public time.
"""

from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import httpx


COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSIONS_FILE_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVES_FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
ARCHIVES_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{accession_dashed}-index.htm"
)

# SEC permits no more than 10 requests/second. Four/second is deliberately
# conservative for a local, resumable admin action. Retries also pass through
# this process-local pacer; the API endpoint adds a separate one-process lock.
MIN_REQUEST_INTERVAL_SECONDS = 0.25
MAX_REQUEST_ATTEMPTS = 3
RETRYABLE_HTTP_STATUSES = frozenset({429, 502, 503, 504})
MAX_RETRY_DELAY_SECONDS = 30.0
DESCRIPTOR_BOUNDARY_BUFFER_DAYS = 7
_pacing_lock = threading.Lock()
_last_request_at = 0.0
_ET = ZoneInfo("America/New_York")


class SecEdgarFetchError(RuntimeError):
    """A source request or source-contract parse failed."""


class SecEdgarBatchDeferred(SecEdgarFetchError):
    """The SEC asked this whole batch to stop and resume later."""


@dataclass(frozen=True)
class SecTickerIdentity:
    cik: str
    ticker: str
    title: str


@dataclass(frozen=True)
class SecResultsFiling:
    accession_number: str
    cik: str
    form: str
    items: str
    filing_date: str
    report_date: str | None
    acceptance_raw: str
    accepted_at_utc: str
    accepted_at_et: str
    acceptance_parse_basis: str
    primary_document: str | None
    source_url: str


@dataclass(frozen=True)
class SecSubmissionHistory:
    cik: str
    company_name: str
    current_tickers: tuple[str, ...]
    forms_seen: frozenset[str]
    first_result_filing_date: str | None
    last_result_filing_date: str | None
    filings: tuple[SecResultsFiling, ...]
    scoped_submission_row_count: int
    items_metadata_missing_count: int
    row_parse_error_count: int


def _wait_for_pacing_slot() -> None:
    global _last_request_at
    with _pacing_lock:
        now = time.monotonic()
        wait = MIN_REQUEST_INTERVAL_SECONDS - (now - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def _retry_delay(response: httpx.Response | None, attempt_index: int) -> float:
    if response is not None:
        raw = response.headers.get("Retry-After", "").strip()
        try:
            seconds = float(raw)
            if math.isfinite(seconds):
                return max(seconds, 0.0)
        except ValueError:
            pass
        try:
            retry_at = parsedate_to_datetime(raw)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0.0)
        except (TypeError, ValueError):
            pass
    return min(0.5 * (2**attempt_index), 2.0)


def _request_json(url: str, user_agent: str) -> Any:
    if not user_agent.strip():
        raise SecEdgarFetchError(
            "SEC automated access requires a declared HEAE_SEC_USER_AGENT with contact information."
        )

    last_error: httpx.HTTPError | None = None
    for attempt_index in range(MAX_REQUEST_ATTEMPTS):
        _wait_for_pacing_slot()
        response: httpx.Response | None = None
        try:
            with httpx.Client(
                timeout=httpx.Timeout(30.0, connect=5.0),
                follow_redirects=False,
                trust_env=False,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                    "User-Agent": user_agent.strip(),
                },
            ) as client:
                response = client.get(url)
        except httpx.HTTPError as error:
            last_error = error
            if attempt_index + 1 < MAX_REQUEST_ATTEMPTS:
                time.sleep(_retry_delay(None, attempt_index))
                continue
            raise SecEdgarFetchError(
                f"SEC request failed after {MAX_REQUEST_ATTEMPTS} attempts "
                f"({error.__class__.__name__})."
            ) from error

        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as error:
                raise SecEdgarFetchError("SEC returned a non-JSON response.") from error

        if response.status_code in RETRYABLE_HTTP_STATUSES:
            delay = _retry_delay(response, attempt_index)
            if delay > MAX_RETRY_DELAY_SECONDS:
                raise SecEdgarBatchDeferred(
                    f"SEC requested a {delay:.0f}-second retry delay; stop this batch and resume later."
                )
            if attempt_index + 1 < MAX_REQUEST_ATTEMPTS:
                time.sleep(delay)
                continue
            if response.status_code in {429, 503} or response.headers.get(
                "Retry-After", ""
            ).strip():
                raise SecEdgarBatchDeferred(
                    f"SEC remained unavailable with HTTP {response.status_code}; "
                    "stop this batch and resume later."
                )
        raise SecEdgarFetchError(f"SEC returned HTTP {response.status_code} for {url}.")

    # Defensive only; every loop path returns, continues, or raises.
    raise SecEdgarFetchError(
        f"SEC request failed ({last_error.__class__.__name__ if last_error else 'unknown error'})."
    )


def normalize_sec_ticker(raw: str) -> str:
    """Normalize SEC/Yahoo class-share punctuation only; never invent a map."""

    return raw.strip().upper().replace(".", "-")


def fetch_company_ticker_map(user_agent: str) -> dict[str, tuple[SecTickerIdentity, ...]]:
    payload = _request_json(COMPANY_TICKERS_URL, user_agent)
    if not isinstance(payload, Mapping):
        raise SecEdgarFetchError("SEC company_tickers.json has an unexpected shape.")

    grouped: dict[str, dict[str, SecTickerIdentity]] = {}
    invalid_rows = 0
    for raw in payload.values():
        if not isinstance(raw, Mapping):
            invalid_rows += 1
            continue
        ticker = normalize_sec_ticker(str(raw.get("ticker") or ""))
        cik_raw = raw.get("cik_str")
        if not ticker or cik_raw in (None, ""):
            invalid_rows += 1
            continue
        try:
            cik = f"{int(cik_raw):010d}"
        except (TypeError, ValueError):
            invalid_rows += 1
            continue
        identity = SecTickerIdentity(cik=cik, ticker=ticker, title=str(raw.get("title") or ""))
        grouped.setdefault(ticker, {})[cik] = identity
    if invalid_rows or not grouped:
        raise SecEdgarFetchError(
            "SEC company_tickers.json contained missing or invalid ticker/CIK rows."
        )
    return {
        ticker: tuple(sorted(identities.values(), key=lambda item: item.cik))
        for ticker, identities in grouped.items()
    }


def _filing_arrays(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    filings = payload.get("filings")
    if isinstance(filings, Mapping) and isinstance(filings.get("recent"), Mapping):
        return filings["recent"]
    return payload


def _filing_rows(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    arrays = _filing_arrays(payload)
    accessions = arrays.get("accessionNumber")
    if not isinstance(accessions, list):
        raise SecEdgarFetchError("SEC submissions payload is missing accessionNumber rows.")
    columns = (
        "accessionNumber",
        "filingDate",
        "reportDate",
        "acceptanceDateTime",
        "form",
        "items",
        "primaryDocument",
    )
    rows: list[dict[str, str]] = []
    for column in columns:
        values = arrays.get(column)
        if not isinstance(values, list) or len(values) != len(accessions):
            raise SecEdgarFetchError(
                f"SEC submissions column {column} is missing or misaligned."
            )
    for index in range(len(accessions)):
        row: dict[str, str] = {}
        for column in columns:
            values = arrays[column]
            value = values[index]
            row[column] = "" if value is None else str(value)
        rows.append(row)
    return rows


def _overlaps_requested_period(descriptor: Mapping[str, Any], start: date, end: date) -> bool:
    try:
        filing_from = date.fromisoformat(str(descriptor.get("filingFrom") or ""))
        filing_to = date.fromisoformat(str(descriptor.get("filingTo") or ""))
    except ValueError:
        # Unknown source metadata is fetched and parsed rather than silently
        # assumed out of scope.
        return True
    # Descriptor bounds are filing dates, while the final contract is SEC
    # acceptance date in ET. Pull adjacent filing-date boundaries, then make
    # the final inclusive decision row by row on the acceptance instant.
    buffer = timedelta(days=DESCRIPTOR_BOUNDARY_BUFFER_DAYS)
    return filing_to >= start - buffer and filing_from <= end + buffer


def _parse_acceptance(raw: str) -> tuple[datetime, datetime, str]:
    """Return the same instant in UTC and New York plus the parsing contract."""

    try:
        if re.fullmatch(r"\d{14}", raw):
            local = datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=_ET)
            return local.astimezone(timezone.utc), local, "legacy_compact_et"

        explicit_utc = raw.endswith("Z")
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_ET)
            basis = "naive_et"
        else:
            basis = "explicit_utc" if explicit_utc else "explicit_offset"
        return parsed.astimezone(timezone.utc), parsed.astimezone(_ET), basis
    except ValueError as error:
        raise SecEdgarFetchError(f"SEC returned an invalid acceptanceDateTime: {raw!r}.") from error


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _iso_offset(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _filing_from_row(cik: str, row: Mapping[str, str]) -> SecResultsFiling:
    accepted_utc, accepted_et, parse_basis = _parse_acceptance(row["acceptanceDateTime"])
    accession = row["accessionNumber"]
    accession_compact = accession.replace("-", "")
    document = row["primaryDocument"].strip() or None
    cik_numeric = str(int(cik))
    if document:
        source_url = ARCHIVES_FILING_URL.format(
            cik=cik_numeric, accession=accession_compact, document=document
        )
    else:
        source_url = ARCHIVES_INDEX_URL.format(
            cik=cik_numeric,
            accession=accession_compact,
            accession_dashed=accession,
        )
    return SecResultsFiling(
        accession_number=accession,
        cik=cik,
        form=row["form"].upper(),
        items=row["items"],
        filing_date=row["filingDate"],
        report_date=row["reportDate"] or None,
        acceptance_raw=row["acceptanceDateTime"],
        accepted_at_utc=_iso_utc(accepted_utc),
        accepted_at_et=_iso_offset(accepted_et),
        acceptance_parse_basis=parse_basis,
        primary_document=document,
        source_url=source_url,
    )


def fetch_results_filings(
    cik: str,
    user_agent: str,
    *,
    start_date: date,
    end_date: date,
) -> SecSubmissionHistory:
    """Inspect one current CIK's submissions slice for exact Item 2.02 rows."""

    normalized_cik = f"{int(cik):010d}"
    main_payload = _request_json(SUBMISSIONS_URL.format(cik=normalized_cik), user_agent)
    if not isinstance(main_payload, Mapping):
        raise SecEdgarFetchError("SEC submissions JSON has an unexpected shape.")
    raw_current_tickers = main_payload.get("tickers")
    if not isinstance(raw_current_tickers, list) or any(
        not isinstance(ticker, str) or not ticker.strip() for ticker in raw_current_tickers
    ):
        raise SecEdgarFetchError("SEC submissions tickers is missing or malformed.")
    current_tickers = tuple(normalize_sec_ticker(ticker) for ticker in raw_current_tickers)

    payloads: list[Mapping[str, Any]] = [main_payload]
    filings_payload = main_payload.get("filings")
    if not isinstance(filings_payload, Mapping):
        raise SecEdgarFetchError("SEC submissions JSON is missing the filings object.")
    descriptors = filings_payload.get("files")
    if not isinstance(descriptors, list):
        raise SecEdgarFetchError("SEC submissions filings.files is missing or malformed.")
    for descriptor in descriptors:
        if not isinstance(descriptor, Mapping):
            raise SecEdgarFetchError("SEC submissions filings.files contains a malformed descriptor.")
        name = str(descriptor.get("name") or "").strip()
        if not name:
            raise SecEdgarFetchError("SEC submissions historical descriptor has no file name.")
        if not _overlaps_requested_period(descriptor, start_date, end_date):
            continue
        historical = _request_json(SUBMISSIONS_FILE_URL.format(name=name), user_agent)
        if not isinstance(historical, Mapping):
            raise SecEdgarFetchError(
                f"SEC historical submissions file {name} has an unexpected shape."
            )
        payloads.append(historical)

    rows_by_accession: dict[str, dict[str, str]] = {}
    for payload in payloads:
        for row in _filing_rows(payload):
            accession = row["accessionNumber"].strip()
            if accession:
                rows_by_accession[accession] = row

    scoped_rows: list[dict[str, str]] = []
    row_parse_error_count = 0
    for row in rows_by_accession.values():
        try:
            filing_day = date.fromisoformat(row["filingDate"])
        except ValueError as error:
            raise SecEdgarFetchError(
                f"SEC returned an invalid filingDate for accession {row['accessionNumber']}."
            ) from error
        if start_date <= filing_day <= end_date:
            scoped_rows.append(row)

    forms_seen = frozenset(row["form"].upper() for row in scoped_rows if row["form"])
    items_metadata_missing_count = sum(
        1
        for row in scoped_rows
        if row["form"].upper() in {"8-K", "8-K/A"} and not row["items"].strip()
    )

    selected: list[SecResultsFiling] = []
    for row in rows_by_accession.values():
        if row["form"].upper() not in {"8-K", "8-K/A"}:
            continue
        item_tokens = {token.strip() for token in row["items"].split(",") if token.strip()}
        if "2.02" not in item_tokens:
            continue
        if not row["acceptanceDateTime"]:
            raise SecEdgarFetchError(
                f"SEC Item 2.02 row {row['accessionNumber']} has no acceptanceDateTime."
            )
        try:
            filing = _filing_from_row(normalized_cik, row)
            accepted_day_et = datetime.fromisoformat(filing.accepted_at_et).date()
        except (SecEdgarFetchError, ValueError) as error:
            raise SecEdgarFetchError(
                f"SEC Item 2.02 row {row['accessionNumber']} has an invalid acceptance timestamp."
            ) from error
        # Availability, not SEC's separate filingDate label, defines the
        # requested boundary for timing research.
        if start_date <= accepted_day_et <= end_date:
            selected.append(filing)

    selected.sort(key=lambda item: (item.accepted_at_utc, item.accession_number))
    result_dates = sorted(item.filing_date for item in selected)
    return SecSubmissionHistory(
        cik=normalized_cik,
        company_name=str(main_payload.get("name") or ""),
        current_tickers=current_tickers,
        forms_seen=forms_seen,
        first_result_filing_date=result_dates[0] if result_dates else None,
        last_result_filing_date=result_dates[-1] if result_dates else None,
        filings=tuple(selected),
        scoped_submission_row_count=len(scoped_rows),
        items_metadata_missing_count=items_metadata_missing_count,
        row_parse_error_count=row_parse_error_count,
    )
