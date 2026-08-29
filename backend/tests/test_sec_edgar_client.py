from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from backend.providers import sec_edgar


def test_sec_request_retries_429_with_bounded_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "https://data.sec.gov/example.json")
    responses = [
        httpx.Response(429, headers={"Retry-After": "0"}, request=request),
        httpx.Response(200, json={"ok": True}, request=request),
    ]
    calls = 0

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def get(self, url: str) -> httpx.Response:
            nonlocal calls
            response = responses[calls]
            calls += 1
            return response

    monkeypatch.setattr(sec_edgar.httpx, "Client", Client)
    monkeypatch.setattr(sec_edgar, "_wait_for_pacing_slot", lambda: None)
    monkeypatch.setattr(sec_edgar.time, "sleep", lambda seconds: None)

    assert sec_edgar._request_json(str(request.url), "HEAE test@example.com") == {"ok": True}
    assert calls == 2


def test_company_ticker_map_keeps_ambiguity_and_normalizes_share_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sec_edgar,
        "_request_json",
        lambda url, user_agent: {
            "0": {"cik_str": 1067983, "ticker": "BRK.B", "title": "Berkshire Hathaway"},
            "1": {"cik_str": 1, "ticker": "DUP", "title": "One"},
            "2": {"cik_str": 2, "ticker": "DUP", "title": "Two"},
        },
    )

    mapping = sec_edgar.fetch_company_ticker_map("HEAE test@example.com")

    assert mapping["BRK-B"][0].cik == "0001067983"
    assert [identity.cik for identity in mapping["DUP"]] == ["0000000001", "0000000002"]


def test_company_ticker_map_fails_closed_on_malformed_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sec_edgar,
        "_request_json",
        lambda url, user_agent: {"0": {"ticker": "AAPL", "title": "missing CIK"}},
    )

    with pytest.raises(sec_edgar.SecEdgarFetchError, match="invalid ticker/CIK"):
        sec_edgar.fetch_company_ticker_map("HEAE test@example.com")


def test_retry_after_longer_than_local_wait_stops_resumable_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "https://data.sec.gov/example.json")
    response = httpx.Response(429, headers={"Retry-After": "60"}, request=request)

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def get(self, url: str) -> httpx.Response:
            return response

    monkeypatch.setattr(sec_edgar.httpx, "Client", Client)
    monkeypatch.setattr(sec_edgar, "_wait_for_pacing_slot", lambda: None)

    with pytest.raises(sec_edgar.SecEdgarBatchDeferred, match="resume later"):
        sec_edgar._request_json(str(request.url), "HEAE test@example.com")


def test_exhausted_503_defers_the_whole_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "https://data.sec.gov/example.json")
    response = httpx.Response(503, request=request)
    calls = 0

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def get(self, url: str) -> httpx.Response:
            nonlocal calls
            calls += 1
            return response

    monkeypatch.setattr(sec_edgar.httpx, "Client", Client)
    monkeypatch.setattr(sec_edgar, "_wait_for_pacing_slot", lambda: None)
    monkeypatch.setattr(sec_edgar.time, "sleep", lambda seconds: None)

    with pytest.raises(sec_edgar.SecEdgarBatchDeferred, match="HTTP 503"):
        sec_edgar._request_json(str(request.url), "HEAE test@example.com")
    assert calls == sec_edgar.MAX_REQUEST_ATTEMPTS


def test_fetch_selects_exact_item_202_and_preserves_acceptance_parse_basis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    # Minimal frozen excerpt of SEC's AAPL submissions shape. The explicit Z
    # is source evidence that this value is UTC; the adapter stores UTC and ET
    # rather than guessing that the wall clock was already New York time.
    main: dict[str, Any] = {
        "name": "Apple Inc.",
        "tickers": ["AAPL"],
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-26-000018", "0000320193-26-000017"],
                "filingDate": ["2026-07-30", "2026-07-20"],
                "reportDate": ["2026-07-30", "2026-07-20"],
                "acceptanceDateTime": [
                    "2026-07-30T20:30:28.000Z",
                    "2026-07-20T12:00:00.000Z",
                ],
                "form": ["8-K", "8-K"],
                "items": ["2.02,9.01", "2.03,9.01"],
                "primaryDocument": ["aapl-20260730.htm", "other.htm"],
            },
            "files": [
                {
                    "name": "CIK0000320193-submissions-001.json",
                    "filingFrom": "2005-01-01",
                    "filingTo": "2005-12-31",
                },
                {
                    "name": "outside.json",
                    "filingFrom": "1999-01-01",
                    "filingTo": "1999-12-31",
                },
            ],
        },
    }
    historical = {
        "accessionNumber": ["0000320193-05-000001"],
        "filingDate": ["2005-08-01"],
        "reportDate": ["2005-08-01"],
        "acceptanceDateTime": ["20050801170000"],
        "form": ["8-K"],
        "items": ["2.02"],
        "primaryDocument": ["old.htm"],
    }

    def fake_request(url: str, user_agent: str) -> Any:
        calls.append(url)
        return historical if url.endswith("submissions-001.json") else main

    monkeypatch.setattr(sec_edgar, "_request_json", fake_request)

    result = sec_edgar.fetch_results_filings(
        "320193",
        "HEAE test@example.com",
        start_date=date(2004, 8, 23),
        end_date=date(2026, 8, 29),
    )

    assert result.current_tickers == ("AAPL",)
    assert len(result.filings) == 2
    historical_filing, recent = result.filings
    assert historical_filing.acceptance_parse_basis == "legacy_compact_et"
    assert recent.acceptance_raw == "2026-07-30T20:30:28.000Z"
    assert recent.accepted_at_utc == "2026-07-30T20:30:28Z"
    assert recent.accepted_at_et == "2026-07-30T16:30:28-04:00"
    assert recent.acceptance_parse_basis == "explicit_utc"
    assert recent.report_date == "2026-07-30"
    assert "000032019326000018" in recent.source_url
    assert not any(url.endswith("outside.json") for url in calls)


def test_availability_range_uses_acceptance_date_in_et_not_filing_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "name": "Boundary Example",
        "tickers": ["BOUND"],
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-26-000001"],
                "filingDate": ["2026-01-01"],
                "reportDate": ["2026-01-01"],
                "acceptanceDateTime": ["2026-01-02T10:00:00.000Z"],
                "form": ["8-K"],
                "items": ["2.02"],
                "primaryDocument": ["x.htm"],
            },
            "files": [],
        },
    }
    monkeypatch.setattr(sec_edgar, "_request_json", lambda url, user_agent: payload)

    result = sec_edgar.fetch_results_filings(
        "1",
        "HEAE test@example.com",
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 2),
    )

    assert len(result.filings) == 1
    assert result.filings[0].accepted_at_et.startswith("2026-01-02T05:00:00")


def test_historical_descriptor_uses_buffer_before_acceptance_date_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = {
        column: []
        for column in (
            "accessionNumber", "filingDate", "reportDate", "acceptanceDateTime",
            "form", "items", "primaryDocument",
        )
    }
    main = {
        "name": "Boundary Example",
        "tickers": ["BOUND"],
        "filings": {
            "recent": empty,
            "files": [
                {
                    "name": "boundary.json",
                    "filingFrom": "2025-12-01",
                    "filingTo": "2025-12-29",
                }
            ],
        },
    }
    historical = {
        "accessionNumber": ["0000000001-25-000001"],
        "filingDate": ["2025-12-29"],
        "reportDate": ["2025-12-29"],
        "acceptanceDateTime": ["2026-01-02T10:00:00.000Z"],
        "form": ["8-K"],
        "items": ["2.02"],
        "primaryDocument": ["x.htm"],
    }
    calls: list[str] = []

    def fake_request(url: str, user_agent: str) -> Any:
        calls.append(url)
        return historical if url.endswith("boundary.json") else main

    monkeypatch.setattr(sec_edgar, "_request_json", fake_request)
    result = sec_edgar.fetch_results_filings(
        "1",
        "HEAE test@example.com",
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 2),
    )

    assert any(url.endswith("boundary.json") for url in calls)
    assert len(result.filings) == 1


def test_misaligned_submission_arrays_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "name": "Broken",
        "tickers": ["BROKEN"],
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-26-000001"],
                "filingDate": [],
                "reportDate": ["2026-01-01"],
                "acceptanceDateTime": ["2026-01-01T12:00:00.000Z"],
                "form": ["8-K"],
                "items": ["2.02"],
                "primaryDocument": ["x.htm"],
            },
            "files": [],
        },
    }
    monkeypatch.setattr(sec_edgar, "_request_json", lambda url, user_agent: payload)

    with pytest.raises(sec_edgar.SecEdgarFetchError, match="misaligned"):
        sec_edgar.fetch_results_filings(
            "1",
            "HEAE test@example.com",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )


@pytest.mark.parametrize(
    ("tickers", "files", "message"),
    [
        ("BROKEN", [], "tickers"),
        (["BROKEN"], None, "filings.files"),
        (["BROKEN"], [None], "malformed descriptor"),
        (
            ["BROKEN"],
            [{"name": "", "filingFrom": "2026-01-01", "filingTo": "2026-01-02"}],
            "no file name",
        ),
    ],
)
def test_submission_identity_and_history_shapes_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tickers: Any,
    files: Any,
    message: str,
) -> None:
    empty = {
        column: []
        for column in (
            "accessionNumber",
            "filingDate",
            "reportDate",
            "acceptanceDateTime",
            "form",
            "items",
            "primaryDocument",
        )
    }
    payload = {
        "name": "Broken",
        "tickers": tickers,
        "filings": {"recent": empty, "files": files},
    }
    monkeypatch.setattr(sec_edgar, "_request_json", lambda url, user_agent: payload)

    with pytest.raises(sec_edgar.SecEdgarFetchError, match=message):
        sec_edgar.fetch_results_filings(
            "1",
            "HEAE test@example.com",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )


def test_item_token_matching_does_not_accept_12_02(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "name": "Example",
        "tickers": ["EX"],
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-26-000001"],
                "filingDate": ["2026-01-01"],
                "reportDate": ["2026-01-01"],
                "acceptanceDateTime": ["2026-01-01T12:00:00.000Z"],
                "form": ["8-K"],
                "items": ["12.02"],
                "primaryDocument": ["x.htm"],
            },
            "files": [],
        },
    }
    monkeypatch.setattr(sec_edgar, "_request_json", lambda url, user_agent: payload)

    result = sec_edgar.fetch_results_filings(
        "1",
        "HEAE test@example.com",
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),
    )

    assert result.filings == ()
