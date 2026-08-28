"""Real, per-symbol price fetch for extended data-library symbols
(staging_symbols `fetch_only = 1` -- the stage-2 universe's real index/
thematic-ETF constituents, see loader.py).

This is admin/production work, not research -- a real, deliberate naming
correction (see developer-letter.md's "A precise line worth stating
explicitly" note): `research_lab/` scripts only ever read a dataset an
earlier fetch already produced, they never call a provider or write a
row. Fetching and storing data has always been an admin concern in this
project (`fetch_data_stage`), and this is that same kind of work, just
scoped to the extended library instead of the live product's 32 active
symbols -- never "research fetch."

Deliberately NOT the live pipeline's `fetch_data_stage`: that stage is one
atomic, all-or-nothing operation across every `active = 1` symbol, shared
with the live Today-desk product's daily refresh -- one bad symbol among
hundreds of library names must never be able to abort that. This module
fetches one symbol at a time, writes each one's real bars immediately
(one symbol's failure never blocks the rest of the batch, and never
touches the live product's dataset at all), and is naturally resumable:
already-fetched symbols are skipped on the next call, so "fetch a batch,
come back later for more" works with zero extra bookkeeping.

Writes into one stable, always-mutable `dataset_snapshots` row
(LIBRARY_DATASET_ID, mode='research', immutable=0, never sealed) --
genuinely separate from every sealed, immutable production snapshot the
live pipeline produces. `mode='research'` here describes what the DATA
is *for* (real cross-sectional research use, not the live product), not
who wrote it -- this admin-owned fetch path is what populates it.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from backend.pipeline.stages.common import (
    STAGING_UNIVERSE_START_DATE,
    PriceFetcher,
    _asset_type_for,
    _iso_z,
    _security_id_for,
)
from backend.providers.yahoo import PriceFetchError

LIBRARY_DATASET_ID = "library-fetch-ongoing"
DEFAULT_BATCH_SIZE = 25


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


def fetch_library_batch(
    connection: sqlite3.Connection,
    price_fetcher: PriceFetcher,
    now: datetime,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    _ensure_library_dataset(connection, now)
    timestamp = _iso_z(now)

    candidates = connection.execute(
        """
        SELECT s.symbol, s.name, s.category FROM staging_symbols AS s
        WHERE s.fetch_only = 1
          AND NOT EXISTS (
              SELECT 1 FROM symbol_bars AS b
              JOIN securities AS sec ON sec.security_id = b.security_id
              WHERE sec.primary_symbol = s.symbol AND b.dataset_snapshot_id = ?
          )
        ORDER BY s.sort_order
        LIMIT ?
        """,
        (LIBRARY_DATASET_ID, batch_size),
    ).fetchall()

    fetched: list[dict] = []
    failed: list[dict] = []
    for row in candidates:
        symbol, name, category = row["symbol"], row["name"], row["category"]
        try:
            bars = price_fetcher(symbol, start_date=STAGING_UNIVERSE_START_DATE)
        except PriceFetchError as error:
            failed.append({"symbol": symbol, "error": str(error)})
            continue
        if not bars:
            failed.append({"symbol": symbol, "error": "Provider returned zero usable bars."})
            continue

        security_id = _security_id_for(symbol, category)
        connection.execute(
            """
            INSERT OR IGNORE INTO securities (
                security_id, primary_symbol, name, asset_type, exchange, currency, sector, active
            ) VALUES (?, ?, ?, ?, NULL, 'USD', NULL, 1)
            """,
            (security_id, symbol, name, _asset_type_for(category)),
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO symbol_bars (
                dataset_snapshot_id, security_id, time, open, high, low, close,
                volume, source_key, observed_at, available_at, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    LIBRARY_DATASET_ID, security_id, bar.time, bar.open, bar.high, bar.low,
                    bar.close, bar.volume, "yahoo", f"{bar.time}T00:00:00Z", f"{bar.time}T00:00:00Z", timestamp,
                )
                for bar in bars
            ],
        )
        # Commit per-symbol: real, deliberate partial-progress durability --
        # if the process dies mid-batch, everything fetched so far survives
        # and won't be re-fetched next time.
        connection.commit()
        fetched.append({"symbol": symbol, "bar_count": len(bars)})

    remaining = connection.execute(
        """
        SELECT COUNT(*) AS n FROM staging_symbols AS s
        WHERE s.fetch_only = 1
          AND NOT EXISTS (
              SELECT 1 FROM symbol_bars AS b
              JOIN securities AS sec ON sec.security_id = b.security_id
              WHERE sec.primary_symbol = s.symbol AND b.dataset_snapshot_id = ?
          )
        """,
        (LIBRARY_DATASET_ID,),
    ).fetchone()["n"]

    return {
        "dataset_snapshot_id": LIBRARY_DATASET_ID,
        "fetched": fetched,
        "failed": failed,
        "remaining": remaining,
    }
