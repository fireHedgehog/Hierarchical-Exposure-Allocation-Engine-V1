"""Atomic, resumable price fetch for extended data-library symbols.

Fetching is admin work. It writes only the mutable research-library dataset,
never a sealed live-pipeline snapshot and never live strategy state. Completion
is recorded by a versioned per-symbol receipt; the presence of one bar is not
treated as proof that a multi-decade response was complete.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime, timedelta

from backend.pipeline.stages.common import (
    STAGING_UNIVERSE_START_DATE,
    PriceFetcher,
    _iso_z,
)
from backend.providers.yahoo import PriceBar, PriceFetchError, PriceHistory


LIBRARY_DATASET_ID = "library-fetch-ongoing"
DEFAULT_BATCH_SIZE = 25
LIBRARY_UNIVERSE_STAGE = "stage-2"
DUAL_BASIS_CONTRACT_REVISION = "yahoo-adjclose-scaled-ohlc-v2"
# Keep the target stable across multi-day manual batches. Advancing this date
# is a deliberate new library refresh, not an accidental consequence of
# clicking "continue" tomorrow and starting again at symbol one.
LIBRARY_CONTRACT_THROUGH = "2026-08-27"


def _ensure_library_dataset(connection: sqlite3.Connection, now: datetime) -> None:
    timestamp = _iso_z(now)
    connection.execute(
        """
        INSERT OR IGNORE INTO dataset_snapshots (
            id, as_of, created_at, mode, data_classification, is_live, is_demo,
            status, immutable, source_manifest_json
        ) VALUES (?, ?, ?, 'research', 'real', 0, 0, 'ongoing', 0, '{}')
        """,
        (LIBRARY_DATASET_ID, timestamp, timestamp),
    )


def _candidate_rows(
    connection: sqlite3.Connection,
    *,
    requested_to: str,
    batch_size: int,
) -> list[sqlite3.Row]:
    return connection.execute(
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
        ),
        library_bars AS (
            SELECT security_id, COUNT(*) AS bar_count,
                   MIN(time) AS first_bar, MAX(time) AS last_bar
            FROM symbol_bars
            WHERE dataset_snapshot_id = ?
            GROUP BY security_id
        )
        SELECT s.symbol, s.name, s.category, security_map.security_id,
               CASE WHEN status.coverage_status = 'failed' THEN 1 ELSE 0 END AS retry_order
        FROM cohort
        JOIN staging_symbols AS s ON s.symbol = cohort.symbol
        JOIN security_map
          ON security_map.primary_symbol = s.symbol
         AND security_map.match_count = 1
        LEFT JOIN staging_price_fetch_status AS status
          ON status.dataset_snapshot_id = ?
         AND status.symbol = s.symbol
         AND status.source_key = 'yahoo'
        LEFT JOIN library_bars ON library_bars.security_id = security_map.security_id
        WHERE (
              status.symbol IS NULL
              OR status.security_id IS NULL
              OR status.security_id != security_map.security_id
              OR status.coverage_status != 'accepted'
              OR status.contract_revision != ?
              OR status.requested_from > ?
              OR status.requested_to < ?
              OR status.provider_first_trade_date IS NULL
              OR status.provider_data_granularity != '1d'
              OR status.provider_exchange_timezone IS NULL
              OR library_bars.bar_count IS NULL
              OR library_bars.bar_count != status.returned_bar_count
              OR library_bars.first_bar != status.returned_from
              OR library_bars.last_bar != status.returned_to
          )
        ORDER BY retry_order, s.sort_order
        LIMIT ?
        """,
        (
            LIBRARY_UNIVERSE_STAGE,
            LIBRARY_DATASET_ID,
            LIBRARY_DATASET_ID,
            DUAL_BASIS_CONTRACT_REVISION,
            STAGING_UNIVERSE_START_DATE,
            requested_to,
            batch_size,
        ),
    ).fetchall()


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
        (LIBRARY_UNIVERSE_STAGE,),
    ).fetchone()
    return row["eligible"], row["mapped"] or 0


def _remaining(connection: sqlite3.Connection, *, requested_to: str) -> int:
    eligible, mapped = _mapping_counts(connection)
    fetchable = len(
        _candidate_rows(
            connection,
            requested_to=requested_to,
            batch_size=2_147_483_647,
        )
    )
    return fetchable + max(eligible - mapped, 0)


def _write_status(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    requested_to: str,
    attempted_at: str,
    coverage_status: str,
    security_id: str,
    bars: list[PriceBar] | None,
    error: str | None,
) -> None:
    prior = connection.execute(
        """
        SELECT coverage_status
        FROM staging_price_fetch_status
        WHERE dataset_snapshot_id = ? AND symbol = ? AND source_key = 'yahoo'
        """,
        (LIBRARY_DATASET_ID, symbol),
    ).fetchone()
    if (
        coverage_status == "failed"
        and prior is not None
        and prior["coverage_status"] == "accepted"
    ):
        # A failed refresh attempt is not allowed to erase the last accepted
        # coverage receipt. Only the latest attempt/error changes.
        connection.execute(
            """
            UPDATE staging_price_fetch_status
            SET last_attempt_status = 'failed', last_attempted_at = ?, last_error = ?
            WHERE dataset_snapshot_id = ? AND symbol = ? AND source_key = 'yahoo'
            """,
            (attempted_at, error, LIBRARY_DATASET_ID, symbol),
        )
        return

    returned_from = min((bar.time for bar in bars), default=None) if bars else None
    returned_to = max((bar.time for bar in bars), default=None) if bars else None
    returned_count = len(bars) if bars else 0
    completed_at = attempted_at if coverage_status == "accepted" else None
    first_trade_date = getattr(bars, "provider_first_trade_date", None)
    data_granularity = getattr(bars, "provider_data_granularity", None)
    exchange_timezone = getattr(bars, "provider_exchange_timezone", None)
    connection.execute(
        """
        INSERT INTO staging_price_fetch_status (
            dataset_snapshot_id, symbol, source_key, security_id, contract_revision,
            requested_from, requested_to, returned_from, returned_to,
            returned_bar_count, provider_first_trade_date,
            provider_data_granularity, provider_exchange_timezone,
            coverage_status, completed_at, last_attempt_status,
            last_attempted_at, last_error
        ) VALUES (?, ?, 'yahoo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(dataset_snapshot_id, symbol, source_key) DO UPDATE SET
            security_id = excluded.security_id,
            contract_revision = excluded.contract_revision,
            requested_from = excluded.requested_from,
            requested_to = excluded.requested_to,
            returned_from = excluded.returned_from,
            returned_to = excluded.returned_to,
            returned_bar_count = excluded.returned_bar_count,
            provider_first_trade_date = excluded.provider_first_trade_date,
            provider_data_granularity = excluded.provider_data_granularity,
            provider_exchange_timezone = excluded.provider_exchange_timezone,
            coverage_status = excluded.coverage_status,
            completed_at = excluded.completed_at,
            last_attempt_status = excluded.last_attempt_status,
            last_attempted_at = excluded.last_attempted_at,
            last_error = excluded.last_error
        """,
        (
            LIBRARY_DATASET_ID,
            symbol,
            security_id,
            DUAL_BASIS_CONTRACT_REVISION,
            STAGING_UNIVERSE_START_DATE,
            requested_to,
            returned_from,
            returned_to,
            returned_count,
            first_trade_date,
            data_granularity,
            exchange_timezone,
            coverage_status,
            completed_at,
            coverage_status,
            attempted_at,
            error,
        ),
    )


def _source_range_is_usable(open_: float, high: float, low: float, close: float) -> bool:
    # Yahoo occasionally reports an auction/open/close outside its continuous
    # high-low range, especially for non-US listings. Preserve those source
    # fields: open and close still support the declared gap/acceptance work,
    # while research expands high/low to the observed open-close envelope for
    # its explicitly secondary range diagnostics. The only impossible range
    # we reject here is high below low. This is semantic, not a threshold fit.
    return high >= low


def _validate_full_response(
    connection: sqlite3.Connection,
    *,
    security_id: str,
    bars: list[PriceBar],
    requested_to: str,
) -> str | None:
    window = [
        bar
        for bar in bars
        if STAGING_UNIVERSE_START_DATE <= bar.time <= requested_to
    ]
    if not window:
        return "Provider returned no bars inside the requested date window."
    if len({bar.time for bar in window}) != len(window):
        return "Provider returned duplicate daily timestamps."

    first_trade_date = getattr(bars, "provider_first_trade_date", None)
    granularity = getattr(bars, "provider_data_granularity", None)
    exchange_timezone = getattr(bars, "provider_exchange_timezone", None)
    if not first_trade_date or granularity != "1d" or not exchange_timezone:
        return (
            "Provider response lacks firstTradeDate, daily granularity, or exchange-timezone "
            "metadata required to audit a first library fetch."
        )

    required_fields = (
        "raw_close",
        "adjusted_close",
        "adjusted_open",
        "adjusted_high",
        "adjusted_low",
        "adjustment_factor",
    )
    incomplete = [
        bar.time
        for bar in window
        if any(getattr(bar, field) is None for field in required_fields)
    ]
    if incomplete:
        return (
            f"Provider returned {len(incomplete)} bars without the full dual-basis OHLC contract "
            f"(first {incomplete[0]})."
        )

    numeric_fields = (
        "open",
        "high",
        "low",
        "raw_close",
        "adjusted_close",
        "adjusted_open",
        "adjusted_high",
        "adjusted_low",
        "adjustment_factor",
    )
    for bar in window:
        values = {field: getattr(bar, field) for field in numeric_fields}
        if any(not math.isfinite(float(value)) for value in values.values()):
            return f"Provider returned a non-finite price field on {bar.time}."
        if any(float(values[field]) <= 0 for field in numeric_fields):
            return f"Provider returned a non-positive price or adjustment factor on {bar.time}."
        if not _source_range_is_usable(
            float(values["open"]),
            float(values["high"]),
            float(values["low"]),
            float(values["raw_close"]),
        ):
            return f"Provider returned an invalid raw OHLC relationship on {bar.time}."
        if not _source_range_is_usable(
            float(values["adjusted_open"]),
            float(values["adjusted_high"]),
            float(values["adjusted_low"]),
            float(values["adjusted_close"]),
        ):
            return f"Provider returned an invalid adjusted OHLC relationship on {bar.time}."
        expected_adjusted = float(values["raw_close"]) * float(values["adjustment_factor"])
        if not math.isclose(
            expected_adjusted,
            float(values["adjusted_close"]),
            rel_tol=1e-8,
            abs_tol=1e-8,
        ):
            return f"Provider returned an inconsistent adjustment factor on {bar.time}."
        if bar.volume is not None and (
            not math.isfinite(float(bar.volume)) or float(bar.volume) < 0
        ):
            return f"Provider returned invalid volume on {bar.time}."

    # The first library refetch is not allowed to forget history already held
    # in an older real dataset. Pick the strongest single-dataset baseline;
    # never sum duplicate snapshots of the same bars.
    existing = connection.execute(
        """
        SELECT bars.dataset_snapshot_id,
               COUNT(*) AS bar_count,
               MIN(bars.time) AS first_bar,
               MAX(bars.time) AS last_bar
        FROM symbol_bars AS bars
        JOIN dataset_snapshots AS dataset
          ON dataset.id = bars.dataset_snapshot_id
        WHERE bars.security_id = ?
          AND bars.source_key = 'yahoo'
          AND dataset.data_classification = 'real'
          AND bars.time >= ? AND bars.time <= ?
          AND bars.close > 0
        GROUP BY bars.dataset_snapshot_id
        ORDER BY bar_count DESC, first_bar ASC, last_bar DESC
        LIMIT 1
        """,
        (security_id, STAGING_UNIVERSE_START_DATE, requested_to),
    ).fetchone()
    returned_from = min(bar.time for bar in window)
    returned_to = max(bar.time for bar in window)
    expected_from = max(STAGING_UNIVERSE_START_DATE, first_trade_date)
    first_trade_gap = (date.fromisoformat(returned_from) - date.fromisoformat(expected_from)).days
    if first_trade_gap < 0 or first_trade_gap > 7:
        return (
            f"Provider response starts at {returned_from}, but source metadata implies "
            f"{expected_from}."
        )
    first_day = date.fromisoformat(expected_from)
    last_day = date.fromisoformat(requested_to)
    weekday_count = 0
    cursor = first_day
    while cursor <= last_day:
        weekday_count += int(cursor.weekday() < 5)
        cursor += timedelta(days=1)
    # This is only a truncation guard, not a homemade exchange calendar.
    # U.S. holidays and occasional halts comfortably fit inside the 10%
    # allowance; a sparse/coarsened response cannot masquerade as daily.
    minimum_daily_rows = max(1, math.floor(weekday_count * 0.90))
    if len(window) < minimum_daily_rows:
        return (
            f"Provider returned only {len(window)} rows across {weekday_count} weekdays; "
            f"daily coverage requires at least {minimum_daily_rows}."
        )
    if returned_to != requested_to:
        return (
            f"Provider response ends at {returned_to}, before the explicit "
            f"library contract cutoff {requested_to}."
        )

    if existing is not None and existing["bar_count"]:
        # A refetch may add history, but a shorter response must never erase a
        # longer prior response and then call itself complete. The reference
        # may be this mutable library or an older sealed real dataset.
        if len(window) < existing["bar_count"]:
            return (
                f"Provider returned {len(window)} bars, fewer than the best existing "
                f"{existing['bar_count']} rows in dataset {existing['dataset_snapshot_id']}."
            )
        if existing["first_bar"] and returned_from > existing["first_bar"]:
            return (
                "Provider response starts later than the best existing "
                f"requested-window history in dataset {existing['dataset_snapshot_id']}."
            )
        if existing["last_bar"] and returned_to < existing["last_bar"]:
            return (
                "Provider response ends earlier than the best existing "
                f"requested-window history in dataset {existing['dataset_snapshot_id']}."
            )
        existing_dates = {
            row["time"]
            for row in connection.execute(
                """
                SELECT time FROM symbol_bars
                WHERE dataset_snapshot_id = ? AND security_id = ?
                  AND source_key = 'yahoo' AND time >= ? AND time <= ?
                  AND close > 0
                """,
                (
                    existing["dataset_snapshot_id"],
                    security_id,
                    STAGING_UNIVERSE_START_DATE,
                    requested_to,
                ),
            ).fetchall()
        }
        returned_dates = {bar.time for bar in window}
        missing_dates = sorted(existing_dates - returned_dates)
        if missing_dates:
            return (
                f"Provider response omits {len(missing_dates)} dates held by the best existing "
                f"dataset (first {missing_dates[0]})."
            )
    return None


def fetch_library_batch(
    connection: sqlite3.Connection,
    price_fetcher: PriceFetcher,
    now: datetime,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    """Fetch and atomically replace one bounded batch of mutable library rows."""

    safe_batch_size = max(1, min(int(batch_size), 100))
    _ensure_library_dataset(connection, now)
    attempted_at = _iso_z(now)
    requested_to = LIBRARY_CONTRACT_THROUGH
    connection.commit()

    candidates = _candidate_rows(
        connection,
        requested_to=requested_to,
        batch_size=safe_batch_size,
    )
    fetched: list[dict] = []
    failed: list[dict] = []

    for row in candidates:
        symbol = row["symbol"]
        security_id = row["security_id"]
        try:
            bars = price_fetcher(
                symbol,
                start_date=STAGING_UNIVERSE_START_DATE,
                end_date=requested_to,
            )
        except PriceFetchError as error:
            message = str(error)
            _write_status(
                connection,
                symbol=symbol,
                requested_to=requested_to,
                attempted_at=attempted_at,
                coverage_status="failed",
                security_id=security_id,
                bars=None,
                error=message,
            )
            connection.commit()
            failed.append({"symbol": symbol, "error": message})
            continue
        except Exception as error:
            message = f"Unexpected provider adapter failure ({error.__class__.__name__}): {error}"
            _write_status(
                connection,
                symbol=symbol,
                requested_to=requested_to,
                attempted_at=attempted_at,
                coverage_status="failed",
                security_id=security_id,
                bars=None,
                error=message,
            )
            connection.commit()
            failed.append({"symbol": symbol, "error": message})
            continue
        if not bars:
            message = "Provider returned zero usable bars."
            _write_status(
                connection,
                symbol=symbol,
                requested_to=requested_to,
                attempted_at=attempted_at,
                coverage_status="failed",
                security_id=security_id,
                bars=None,
                error=message,
            )
            connection.commit()
            failed.append({"symbol": symbol, "error": message})
            continue

        validation_error = _validate_full_response(
            connection,
            security_id=security_id,
            bars=bars,
            requested_to=requested_to,
        )
        if validation_error:
            _write_status(
                connection,
                symbol=symbol,
                requested_to=requested_to,
                attempted_at=attempted_at,
                coverage_status="failed",
                security_id=security_id,
                bars=bars,
                error=validation_error,
            )
            connection.commit()
            failed.append({"symbol": symbol, "error": validation_error})
            continue

        window_bars = [
            bar
            for bar in bars
            if STAGING_UNIVERSE_START_DATE <= bar.time <= requested_to
        ]
        # Mutable staging, deliberate replacement: validation completed before
        # this transaction, so a short/partial response never destroys the
        # longer legacy window. Sealed datasets are never targeted here.
        connection.execute(
            """
            DELETE FROM symbol_bars
            WHERE dataset_snapshot_id = ? AND security_id = ?
              AND time >= ? AND time <= ?
            """,
            (LIBRARY_DATASET_ID, security_id, STAGING_UNIVERSE_START_DATE, requested_to),
        )
        connection.executemany(
            """
            INSERT INTO symbol_bars (
                dataset_snapshot_id, security_id, time, open, high, low, close,
                volume, raw_close, adjusted_close, adjusted_open, adjusted_high,
                adjusted_low, adjustment_factor, source_key, observed_at,
                available_at, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    LIBRARY_DATASET_ID,
                    security_id,
                    bar.time,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume,
                    bar.raw_close,
                    bar.adjusted_close,
                    bar.adjusted_open,
                    bar.adjusted_high,
                    bar.adjusted_low,
                    bar.adjustment_factor,
                    "yahoo",
                    None,
                    None,
                    attempted_at,
                )
                for bar in window_bars
            ],
        )
        _write_status(
            connection,
            symbol=symbol,
            requested_to=requested_to,
            attempted_at=attempted_at,
            coverage_status="accepted",
            security_id=security_id,
            bars=bars,
            error=None,
        )
        # Per-symbol commit: a process death loses at most the current symbol.
        connection.commit()
        fetched.append(
            {
                "symbol": symbol,
                "bar_count": len(window_bars),
                "period_start": min(bar.time for bar in window_bars),
                "period_end": max(bar.time for bar in window_bars),
                "contract_revision": DUAL_BASIS_CONTRACT_REVISION,
            }
        )

    eligible, mapped = _mapping_counts(connection)
    return {
        "dataset_snapshot_id": LIBRARY_DATASET_ID,
        "universe_stage": LIBRARY_UNIVERSE_STAGE,
        "contract_revision": DUAL_BASIS_CONTRACT_REVISION,
        "requested_from": STAGING_UNIVERSE_START_DATE,
        "requested_to": requested_to,
        "fetched": fetched,
        "failed": failed,
        "remaining": _remaining(connection, requested_to=requested_to),
        "blocked_by_security_mapping": max(eligible - mapped, 0),
    }


def get_library_fetch_coverage(connection: sqlite3.Connection) -> dict:
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
        ),
        library_bars AS (
            SELECT security_id, COUNT(*) AS bar_count,
                   MIN(time) AS first_bar, MAX(time) AS last_bar
            FROM symbol_bars
            WHERE dataset_snapshot_id = ?
            GROUP BY security_id
        )
        SELECT COUNT(*) AS eligible,
               SUM(CASE WHEN security_map.match_count = 1 THEN 1 ELSE 0 END) AS mapped,
               SUM(CASE
                   WHEN status.coverage_status = 'accepted'
                    AND status.security_id = security_map.security_id
                    AND status.contract_revision = ?
                    AND status.requested_from <= ?
                    AND status.requested_to >= ?
                    AND status.provider_first_trade_date IS NOT NULL
                    AND status.provider_data_granularity = '1d'
                    AND status.provider_exchange_timezone IS NOT NULL
                    AND library_bars.bar_count = status.returned_bar_count
                    AND library_bars.first_bar = status.returned_from
                    AND library_bars.last_bar = status.returned_to
                   THEN 1 ELSE 0 END) AS accepted,
               SUM(CASE
                   WHEN status.last_attempt_status = 'failed'
                   THEN 1 ELSE 0 END) AS failed
        FROM cohort
        JOIN staging_symbols AS s ON s.symbol = cohort.symbol
        LEFT JOIN security_map ON security_map.primary_symbol = s.symbol
        LEFT JOIN staging_price_fetch_status AS status
          ON status.dataset_snapshot_id = ?
         AND status.symbol = s.symbol
         AND status.source_key = 'yahoo'
        LEFT JOIN library_bars ON library_bars.security_id = security_map.security_id
        """,
        (
            LIBRARY_UNIVERSE_STAGE,
            LIBRARY_DATASET_ID,
            DUAL_BASIS_CONTRACT_REVISION,
            STAGING_UNIVERSE_START_DATE,
            LIBRARY_CONTRACT_THROUGH,
            LIBRARY_DATASET_ID,
        ),
    ).fetchone()
    eligible = row["eligible"]
    mapped = row["mapped"] or 0
    return {
        "dataset_snapshot_id": LIBRARY_DATASET_ID,
        "universe_stage": LIBRARY_UNIVERSE_STAGE,
        "contract_revision": DUAL_BASIS_CONTRACT_REVISION,
        "requested_from": STAGING_UNIVERSE_START_DATE,
        "requested_to": LIBRARY_CONTRACT_THROUGH,
        "eligible_symbols": eligible,
        "mapped_security_symbols": mapped,
        "blocked_by_security_mapping": max(eligible - mapped, 0),
        "accepted_symbols": row["accepted"] or 0,
        "failed_symbols": row["failed"] or 0,
        "remaining_symbols": _remaining(
            connection,
            requested_to=LIBRARY_CONTRACT_THROUGH,
        ),
    }
