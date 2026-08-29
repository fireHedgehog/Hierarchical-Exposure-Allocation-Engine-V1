from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from backend.database import connect, initialize_database
from backend.providers.sec_edgar import (
    SecEdgarBatchDeferred,
    SecEdgarFetchError,
    SecResultsFiling,
    SecSubmissionHistory,
    SecTickerIdentity,
)
from backend.universe.earnings_fetch import (
    fetch_results_filing_batch,
    get_results_filing_coverage_summary,
)


NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def _history(
    symbol: str,
    cik: str,
    *,
    forms: frozenset[str],
    filings: tuple[SecResultsFiling, ...] = (),
    current_tickers: tuple[str, ...] | None = None,
    scoped_rows: int = 1,
    missing_items: int = 0,
    parse_errors: int = 0,
) -> SecSubmissionHistory:
    dates = sorted(filing.filing_date for filing in filings)
    return SecSubmissionHistory(
        cik=cik,
        company_name=symbol,
        current_tickers=current_tickers or (symbol,),
        forms_seen=forms,
        first_result_filing_date=dates[0] if dates else None,
        last_result_filing_date=dates[-1] if dates else None,
        filings=filings,
        scoped_submission_row_count=scoped_rows,
        items_metadata_missing_count=missing_items,
        row_parse_error_count=parse_errors,
    )


def _filing(cik: str) -> SecResultsFiling:
    return SecResultsFiling(
        accession_number="0000000001-26-000001",
        cik=cik,
        form="8-K",
        items="2.02,9.01",
        filing_date="2026-07-30",
        report_date="2026-07-30",
        acceptance_raw="2026-07-30T20:30:28.000Z",
        accepted_at_utc="2026-07-30T20:30:28Z",
        accepted_at_et="2026-07-30T16:30:28-04:00",
        acceptance_parse_basis="explicit_utc",
        primary_document="earnings.htm",
        source_url="https://www.sec.gov/Archives/example.htm",
    )


def _stage_symbols(connection, count: int) -> list[str]:
    requested = ("AAPL", "NVDA", "MSFT", "AMZN")[:count]
    present = {
        row["symbol"]
        for row in connection.execute(
            f"SELECT symbol FROM staging_symbols WHERE symbol IN ({','.join('?' for _ in requested)})",
            requested,
        ).fetchall()
    }
    assert present == set(requested)
    return list(requested)


def _seed_security_mappings(connection, symbols: list[str]) -> dict[str, str]:
    connection.execute(
        f"""
        DELETE FROM securities
        WHERE primary_symbol IN (
            SELECT symbol FROM staging_universe_membership WHERE stage = 'stage-2'
        )
          AND primary_symbol NOT IN ({','.join('?' for _ in symbols)})
        """,
        symbols,
    )
    mapping = {}
    for symbol in symbols:
        rows = connection.execute(
            "SELECT security_id FROM securities WHERE primary_symbol = ?",
            (symbol,),
        ).fetchall()
        assert len(rows) == 1
        mapping[symbol] = rows[0]["security_id"]
    connection.commit()
    return mapping


def test_batch_records_filing_rows_and_honest_coverage_gaps(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "results-filings.db")
    with connect(database) as connection:
        symbols = _stage_symbols(connection, 4)
        security_ids = _seed_security_mappings(connection, symbols)
        ciks = {symbol: f"{index + 1:010d}" for index, symbol in enumerate(symbols)}
        ticker_map = {
            symbol: (SecTickerIdentity(cik=ciks[symbol], ticker=symbol, title=symbol),)
            for symbol in symbols[:3]
        }
        filing = _filing(ciks[symbols[0]])
        histories = {
            ciks[symbols[0]]: _history(
                symbols[0], ciks[symbols[0]], forms=frozenset({"8-K"}), filings=(filing,)
            ),
            ciks[symbols[1]]: _history(
                symbols[1], ciks[symbols[1]], forms=frozenset({"6-K"})
            ),
            ciks[symbols[2]]: _history(
                symbols[2],
                ciks[symbols[2]],
                forms=frozenset({"8-K"}),
                current_tickers=("NOT-THE-SYMBOL",),
            ),
        }
        submission_calls: list[str] = []

        def submission_fetcher(cik: str, user_agent: str, *, start_date: date, end_date: date):
            submission_calls.append(cik)
            return histories[cik]

        result = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=4,
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=submission_fetcher,
        )

        assert result["issuer_filings_seen"] == 1
        assert set(result["coverage"]) == {
            "retrieved_current_cik_8k_2_02_rows",
            "foreign_6k_unsupported",
            "identity_mismatch",
            "unmatched",
        }
        stored = connection.execute("SELECT * FROM staging_results_filings").fetchone()
        assert stored["sec_accepted_at_raw"] == "2026-07-30T20:30:28.000Z"
        assert stored["sec_accepted_at_et"] == "2026-07-30T16:30:28-04:00"
        assert stored["acceptance_parse_basis"] == "explicit_utc"
        assert stored["timing_quality"] == "filing_acceptance_proxy_not_first_public"
        link = connection.execute("SELECT * FROM staging_results_filing_securities").fetchone()
        assert link["security_id"] == security_ids[symbols[0]]

        status_by_symbol = {
            row["requested_symbol"]: row
            for row in connection.execute(
                "SELECT * FROM staging_results_filing_fetch_status"
            ).fetchall()
        }
        assert status_by_symbol[symbols[0]]["lineage_scope"] == "current_cik_only"
        assert status_by_symbol[symbols[1]]["coverage_status"] == "foreign_6k_unsupported"
        assert status_by_symbol[symbols[2]]["identity_status"] == "mismatch"
        assert status_by_symbol[symbols[3]]["identity_status"] == "unmatched"
        assert len(submission_calls) == 3


def test_shared_cik_is_one_issuer_filing_with_two_security_links(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "shared-cik.db")
    with connect(database) as connection:
        symbols = _stage_symbols(connection, 2)
        _seed_security_mappings(connection, symbols)
        shared_cik = "0000000123"
        ticker_map = {
            symbol: (SecTickerIdentity(cik=shared_cik, ticker=symbol, title="Shared issuer"),)
            for symbol in symbols
        }
        calls = 0

        def submission_fetcher(cik: str, user_agent: str, *, start_date: date, end_date: date):
            nonlocal calls
            calls += 1
            return _history(
                symbols[0],
                shared_cik,
                forms=frozenset({"8-K"}),
                filings=(_filing(shared_cik),),
                current_tickers=tuple(symbols),
            )

        result = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=2,
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=submission_fetcher,
        )

        assert calls == 1
        assert result["issuer_filings_seen"] == 1
        assert connection.execute("SELECT COUNT(*) FROM staging_results_filings").fetchone()[0] == 1
        assert (
            connection.execute("SELECT COUNT(*) FROM staging_results_filing_securities").fetchone()[0]
            == 2
        )


def test_successful_coverage_resumes_when_end_date_moves_forward(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "resume.db")
    with connect(database) as connection:
        symbol = _stage_symbols(connection, 1)[0]
        _seed_security_mappings(connection, [symbol])
        cik = "0000000456"
        ticker_map = {symbol: (SecTickerIdentity(cik=cik, ticker=symbol, title=symbol),)}
        calls = 0

        def submission_fetcher(cik: str, user_agent: str, *, start_date: date, end_date: date):
            nonlocal calls
            calls += 1
            return _history(symbol, cik, forms=frozenset({"8-K"}))

        first_end = date(2026, 8, 1)
        fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            end_date=first_end,
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=submission_fetcher,
        )
        same = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            end_date=first_end,
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=submission_fetcher,
        )
        assert same["processed"] == []
        assert calls == 1

        fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            end_date=date(2026, 8, 28),
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=submission_fetcher,
        )
        assert calls == 2
        status = connection.execute(
            "SELECT * FROM staging_results_filing_fetch_status"
        ).fetchone()
        assert status["covered_to"] == "2026-08-28"
        assert status["attempt_count"] == 2


def test_failed_extension_preserves_previous_successful_coverage(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "preserve-success.db")
    with connect(database) as connection:
        symbol = _stage_symbols(connection, 1)[0]
        _seed_security_mappings(connection, [symbol])
        cik = "0000000789"
        ticker_map = {symbol: (SecTickerIdentity(cik=cik, ticker=symbol, title=symbol),)}
        first_end = date(2026, 8, 1)
        fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            end_date=first_end,
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=lambda *args, **kwargs: _history(
                symbol, cik, forms=frozenset({"8-K"}), filings=(_filing(cik),)
            ),
        )

        def fail(*args, **kwargs):
            raise SecEdgarFetchError("temporary SEC outage")

        result = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            end_date=date(2026, 8, 28),
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=fail,
        )

        status = connection.execute(
            "SELECT * FROM staging_results_filing_fetch_status"
        ).fetchone()
        assert result["failed"][0]["symbol"] == symbol
        assert status["coverage_status"] == "retrieved_current_cik_8k_2_02_rows"
        assert status["covered_to"] == first_end.isoformat()
        assert status["last_error"] == "temporary SEC outage"
        assert status["attempt_count"] == 2


def test_fetch_does_not_create_security_master_rows(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "no-security-mutation.db")
    with connect(database) as connection:
        before = connection.execute("SELECT COUNT(*) FROM securities").fetchone()[0]
        result = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=-1,
            ticker_map_fetcher=lambda user_agent: {},
        )
        after = connection.execute("SELECT COUNT(*) FROM securities").fetchone()[0]

        assert before == after
        assert len(result["processed"]) == 1
        assert result["processed"][0]["status"] == "unmatched"
        assert result["blocked_by_security_mapping"] == 0


def test_cik_change_failure_keeps_old_success_identity_and_links_retryable(
    tmp_path: Path,
) -> None:
    database = initialize_database(tmp_path / "cik-change-failure.db")
    with connect(database) as connection:
        symbol = _stage_symbols(connection, 1)[0]
        _seed_security_mappings(connection, [symbol])
        old_cik = "0000000101"
        new_cik = "0000000202"
        old_map = {
            symbol: (SecTickerIdentity(cik=old_cik, ticker=symbol, title="Old issuer"),)
        }
        fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            ticker_map_fetcher=lambda user_agent: old_map,
            submission_fetcher=lambda *args, **kwargs: _history(
                symbol, old_cik, forms=frozenset({"8-K"}), filings=(_filing(old_cik),)
            ),
        )

        new_map = {
            symbol: (SecTickerIdentity(cik=new_cik, ticker=symbol, title="New issuer"),)
        }

        def fail(*args, **kwargs):
            raise SecEdgarFetchError("new CIK unavailable")

        result = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            ticker_map_fetcher=lambda user_agent: new_map,
            submission_fetcher=fail,
        )
        status = connection.execute(
            "SELECT * FROM staging_results_filing_fetch_status"
        ).fetchone()

        assert result["failed"][0]["symbol"] == symbol
        assert status["resolved_cik"] == old_cik
        assert status["last_attempted_cik"] == new_cik
        assert status["coverage_status"] == "retrieved_current_cik_8k_2_02_rows"
        assert connection.execute(
            "SELECT COUNT(*) FROM staging_results_filing_securities"
        ).fetchone()[0] == 1
        assert result["remaining_fetchable"] == 1
        assert get_results_filing_coverage_summary(connection)["remaining_fetchable"] == 1


def test_batch_defer_stops_before_requesting_another_cik_and_remains_resumable(
    tmp_path: Path,
) -> None:
    database = initialize_database(tmp_path / "batch-deferred.db")
    with connect(database) as connection:
        symbols = _stage_symbols(connection, 2)
        _seed_security_mappings(connection, symbols)
        ciks = {symbol: f"{index + 501:010d}" for index, symbol in enumerate(symbols)}
        ticker_map = {
            symbol: (SecTickerIdentity(cik=ciks[symbol], ticker=symbol, title=symbol),)
            for symbol in symbols
        }
        calls: list[str] = []

        def defer(cik: str, *args, **kwargs):
            calls.append(cik)
            raise SecEdgarBatchDeferred("SEC asked this batch to resume later")

        result = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=2,
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=defer,
        )

        assert calls == [ciks[symbols[0]]]
        assert result["batch_deferred"]["symbol"] == symbols[0]
        assert result["failed"][0]["symbol"] == symbols[0]
        assert result["remaining_fetchable"] == 2
        status = connection.execute(
            "SELECT * FROM staging_results_filing_fetch_status"
        ).fetchone()
        assert status["coverage_status"] == "failed"
        assert status["last_error"] == "SEC asked this batch to resume later"


def test_identity_mismatch_retries_when_company_map_is_unchanged(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "identity-mismatch-retry.db")
    with connect(database) as connection:
        symbol = _stage_symbols(connection, 1)[0]
        _seed_security_mappings(connection, [symbol])
        cik = "0000000606"
        ticker_map = {
            symbol: (SecTickerIdentity(cik=cik, ticker=symbol, title=symbol),)
        }
        calls = 0

        def submission_fetcher(*args, **kwargs):
            nonlocal calls
            calls += 1
            current_tickers = ("NOT-YET-SYNCHRONIZED",) if calls == 1 else (symbol,)
            return _history(
                symbol,
                cik,
                forms=frozenset({"8-K"}),
                filings=(_filing(cik),),
                current_tickers=current_tickers,
            )

        first = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=submission_fetcher,
        )

        assert first["processed"][0]["status"] == "identity_mismatch"
        assert first["remaining_fetchable"] == 1
        assert get_results_filing_coverage_summary(connection)["remaining_fetchable"] == 1

        second = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=submission_fetcher,
        )

        assert second["processed"][0]["status"] == "retrieved_current_cik_8k_2_02_rows"
        assert second["remaining_fetchable"] == 0
        assert calls == 2


def test_identity_becoming_unmatched_unlinks_stale_rows_and_then_resumes(
    tmp_path: Path,
) -> None:
    database = initialize_database(tmp_path / "identity-unmatched.db")
    with connect(database) as connection:
        symbol = _stage_symbols(connection, 1)[0]
        _seed_security_mappings(connection, [symbol])
        cik = "0000000303"
        ticker_map = {
            symbol: (SecTickerIdentity(cik=cik, ticker=symbol, title=symbol),)
        }
        fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            ticker_map_fetcher=lambda user_agent: ticker_map,
            submission_fetcher=lambda *args, **kwargs: _history(
                symbol, cik, forms=frozenset({"8-K"}), filings=(_filing(cik),)
            ),
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM staging_results_filing_securities"
        ).fetchone()[0] == 1

        unmatched = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            ticker_map_fetcher=lambda user_agent: {},
        )
        same_again = fetch_results_filing_batch(
            connection,
            "HEAE test@example.com",
            NOW,
            batch_size=1,
            ticker_map_fetcher=lambda user_agent: {},
        )
        status = connection.execute(
            "SELECT * FROM staging_results_filing_fetch_status"
        ).fetchone()

        assert unmatched["processed"][0]["status"] == "unmatched"
        assert same_again["processed"] == []
        assert status["identity_status"] == "unmatched"
        assert connection.execute(
            "SELECT COUNT(*) FROM staging_results_filing_securities"
        ).fetchone()[0] == 0


def test_results_fetch_rejects_unfinished_et_date(tmp_path: Path) -> None:
    database = initialize_database(tmp_path / "unfinished-et-date.db")
    with connect(database) as connection:
        try:
            fetch_results_filing_batch(
                connection,
                "HEAE test@example.com",
                NOW,
                end_date=date(2026, 8, 29),
                ticker_map_fetcher=lambda user_agent: {},
            )
        except ValueError as error:
            assert "fully completed ET" in str(error)
        else:
            raise AssertionError("unfinished ET date was accepted")
