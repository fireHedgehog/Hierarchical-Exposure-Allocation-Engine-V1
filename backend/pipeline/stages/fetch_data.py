from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Callable

from backend.pipeline.stages.common import (
    FRED_OBSERVATION_WINDOW_DAYS,
    PRICE_SOFT_MAX_AGE_DAYS,
    STAGING_UNIVERSE_START_DATE,
    SERIES_METADATA,
    StageOutcome,
    FredFetcher,
    PriceFetcher,
    _asset_type_for,
    _iso_z,
    _json,
    _security_id_for,
)
from backend.providers.fred import FredFetchError, FredObservation
from backend.providers.yahoo import PriceBar, PriceFetchError
from backend.secrets import SecretStore


def run_fetch_data_stage(
    connection: sqlite3.Connection,
    secret_store: SecretStore,
    fred_fetcher: FredFetcher,
    price_fetcher: PriceFetcher,
    now: datetime,
    engine_mode: str,
    on_item_progress: Callable[[int, int, str], None] | None = None,
) -> StageOutcome:
    """Fetch real macro observations (FRED) and price bars (Yahoo) into one
    new unsealed dataset. Per-item resilient (real fix, 2026-08-28, direct
    user request): one bad symbol or series no longer aborts the whole
    fetch and discards everything already fetched -- each item is tried
    independently and failures are collected and reported by name.

    Per-symbol commit durability (real fix, 2026-08-28, direct user
    request: fetching "all in one big API call" with one commit at the
    very end was flagged as genuinely naive -- the whole run lives inside
    one open transaction on the caller's connection, so a process killed
    mid-fetch (it has happened) loses every bar already fetched, and 700+
    back-to-back requests with no pacing risks a real Yahoo block). This
    stage now writes and commits the dataset row plus every FRED
    observation first, then commits each symbol's bars right after that
    symbol is fetched -- matching the same "commit per-symbol" pattern
    already used by the separate library_fetch path. Real courtesy pacing
    between individual Yahoo requests lives in `providers/yahoo.py`
    itself (the one place every real call funnels through), not here.

    A consequence of committing progressively: once the dataset row and
    FRED data exist, a later total wipeout of the price-symbol loop can no
    longer retroactively discard what's already durable on disk. Every
    macro series failing is still a real, hard `failed` (checked before
    anything is written -- an empty dataset is never useful), but every
    price symbol failing now degrades to `completed_with_warnings` with a
    macro-only dataset, rather than discarding real, already-committed
    data to preserve an all-or-nothing illusion. The price-bar universe is
    read from `staging_symbols` (DB-driven), never a ticker list embedded
    in this code.
    """

    provider = connection.execute(
        "SELECT credential_name, environment_variable FROM operator_providers WHERE provider_key = 'fred'"
    ).fetchone()
    secret = (
        secret_store.get(provider["credential_name"], provider["environment_variable"])
        if provider is not None
        else None
    )
    if secret is None:
        return StageOutcome(
            status="blocked",
            message="No FRED credential is configured; cannot fetch real observations.",
            error_code="credential_missing",
        )

    as_of = now.date()
    observation_start = (as_of - timedelta(days=FRED_OBSERVATION_WINDOW_DAYS)).isoformat()
    observation_end = as_of.isoformat()
    # A 1-day safety margin, not the dataset's real as_of: FRED validates
    # realtime_start/realtime_end against ITS OWN server clock (observed to
    # run on US time, behind UTC), and rejects a pin later than that with a
    # real HTTP 400 -- "realtime_start can not be after today's date". Since
    # `now` here is UTC, the hours right after UTC midnight are still
    # "yesterday" for FRED. Pinning one real day earlier costs nothing (FRED
    # vintages do not change intraday) and removes this clock-skew edge case
    # entirely, rather than requesting a vintage FRED may not consider to
    # exist yet.
    realtime = (as_of - timedelta(days=1)).isoformat()

    fetched_series: dict[str, list[FredObservation]] = {}
    failed_series: dict[str, str] = {}
    total_items = len(SERIES_METADATA) + len(
        connection.execute(
            "SELECT symbol FROM staging_symbols WHERE (active = 1 OR fetch_only = 1) AND category != 'macro_series'"
        ).fetchall()
    )
    item_index = 0
    for series_id in SERIES_METADATA:
        item_index += 1
        if on_item_progress:
            on_item_progress(item_index, total_items, series_id)
        try:
            observations = fred_fetcher(
                secret.value,
                series_id,
                observation_start=observation_start,
                observation_end=observation_end,
                realtime_start=realtime,
                realtime_end=realtime,
            )
        except FredFetchError as error:
            failed_series[series_id] = str(error)
            continue
        if not observations:
            failed_series[series_id] = "FRED returned zero observations."
            continue
        fetched_series[series_id] = observations

    if not fetched_series:
        return StageOutcome(
            status="failed",
            message=f"Every FRED series failed, no dataset was written: {failed_series}",
            error_code="fred_fetch_failed",
        )

    staging_rows = connection.execute(
        """
        SELECT symbol, name, category FROM staging_symbols
        WHERE (active = 1 OR fetch_only = 1) AND category != 'macro_series'
        ORDER BY sort_order
        """
    ).fetchall()

    dataset_id = f"real-macro-{uuid.uuid4()}"
    timestamp = _iso_z(now)
    # A placeholder manifest, written now so the dataset row exists before a
    # single Yahoo request is made; replaced with the real fetched/failed
    # symbol lists once the price loop below finishes.
    manifest = _json(
        {
            "source": "fred+yahoo",
            "macro_series": list(fetched_series),
            "macro_series_failed": failed_series,
            "price_symbols": [],
            "price_symbols_failed": {},
            "engine_mode": engine_mode,
            "observation_window": {"start": observation_start, "end": observation_end},
            "realtime_vintage": realtime,
            "price_fetch_start_date": STAGING_UNIVERSE_START_DATE,
        }
    )
    connection.execute(
        """
        INSERT INTO dataset_snapshots (
            id, as_of, created_at, mode, data_classification, is_live, is_demo,
            status, immutable, source_manifest_json, engine_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (dataset_id, timestamp, timestamp, "research", "real", 0, 0, "fetched", 0, manifest, engine_mode),
    )

    total_rows = 0
    for series_id, observations in fetched_series.items():
        meta = SERIES_METADATA[series_id]
        rows = [
            (
                dataset_id,
                observation.series_id,
                observation.observation_date,
                observation.value,
                observation.realtime_start,
                observation.realtime_end,
                observation.units,
                meta["frequency"],
                "fred",
                f"{observation.observation_date}T00:00:00Z",
                f"{observation.realtime_start}T00:00:00Z",
                timestamp,
            )
            for observation in observations
        ]
        connection.executemany(
            """
            INSERT INTO fred_observations (
                dataset_snapshot_id, series_id, observation_date, value,
                realtime_start, realtime_end, units, frequency, source_key,
                observed_at, available_at, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        total_rows += len(rows)

        latest = max(observations, key=lambda item: item.observation_date)
        earliest = min(observations, key=lambda item: item.observation_date)
        connection.execute(
            """
            INSERT INTO data_assets (
                asset_key, provider_key, label, kind, symbol, frequency,
                classification, row_count, period_start, period_end,
                last_observation_at, last_fetched_at, max_age_seconds, status,
                dataset_snapshot_id, detail, updated_at
            ) VALUES (?, 'fred', ?, 'macro_release', NULL, ?, 'real', ?, ?, ?, ?, ?, ?, 'ready', ?, ?, ?)
            ON CONFLICT(asset_key) DO UPDATE SET
                label = excluded.label,
                frequency = excluded.frequency,
                row_count = excluded.row_count,
                period_start = excluded.period_start,
                period_end = excluded.period_end,
                last_observation_at = excluded.last_observation_at,
                last_fetched_at = excluded.last_fetched_at,
                max_age_seconds = excluded.max_age_seconds,
                status = excluded.status,
                dataset_snapshot_id = excluded.dataset_snapshot_id,
                detail = excluded.detail,
                updated_at = excluded.updated_at
            """,
            (
                f"fred_{series_id.lower()}",
                f"FRED {series_id} — {meta['label']}",
                meta["frequency"],
                len(observations),
                earliest.observation_date,
                latest.observation_date,
                latest.observation_date,
                timestamp,
                None if meta["max_age_days"] is None else meta["max_age_days"] * 86400,
                dataset_id,
                f"{len(observations)} real point-in-time observations fetched from FRED.",
                timestamp,
            ),
        )

    # Durable checkpoint: the dataset row and every FRED observation are
    # committed before a single Yahoo request is made below. If everything
    # after this point failed outright, this much still survives.
    connection.commit()

    fetched_bars: dict[str, list[PriceBar]] = {}
    failed_symbols: dict[str, str] = {}
    total_bars = 0
    earliest_bar_date: str | None = None
    latest_bar_date: str | None = None
    for row in staging_rows:
        symbol, name, category = row["symbol"], row["name"], row["category"]
        item_index += 1
        if on_item_progress:
            on_item_progress(item_index, total_items, symbol)
        try:
            bars = price_fetcher(symbol, start_date=STAGING_UNIVERSE_START_DATE)
        except PriceFetchError as error:
            failed_symbols[symbol] = str(error)
            continue
        if not bars:
            failed_symbols[symbol] = "Provider returned zero usable bars."
            continue
        fetched_bars[symbol] = bars

        security_id = _security_id_for(symbol, category)
        connection.execute(
            """
            INSERT OR IGNORE INTO securities (
                security_id, primary_symbol, name, asset_type, exchange, currency, sector, active
            ) VALUES (?, ?, ?, ?, NULL, 'USD', NULL, 1)
            """,
            (security_id, symbol, name, _asset_type_for(category)),
        )
        bar_rows = [
            (
                dataset_id,
                security_id,
                bar.time,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                "yahoo",
                f"{bar.time}T00:00:00Z",
                f"{bar.time}T00:00:00Z",
                timestamp,
            )
            for bar in bars
        ]
        connection.executemany(
            """
            INSERT OR IGNORE INTO symbol_bars (
                dataset_snapshot_id, security_id, time, open, high, low, close,
                volume, source_key, observed_at, available_at, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            bar_rows,
        )
        total_bars += len(bar_rows)
        dates = [bar.time for bar in bars]
        earliest_bar_date = min(filter(None, [earliest_bar_date, min(dates)]))
        latest_bar_date = max(filter(None, [latest_bar_date, max(dates)]))

        connection.execute(
            """
            INSERT INTO data_assets (
                asset_key, provider_key, label, kind, symbol, frequency,
                classification, row_count, period_start, period_end,
                last_observation_at, last_fetched_at, max_age_seconds, status,
                dataset_snapshot_id, detail, updated_at
            ) VALUES (
                'staging_price_bars', NULL, 'Staging universe daily price bars', 'price_bars', NULL, 'daily',
                'real', ?, ?, ?, ?, ?, ?, 'ready', ?, ?, ?
            )
            ON CONFLICT(asset_key) DO UPDATE SET
                row_count = excluded.row_count,
                period_start = excluded.period_start,
                period_end = excluded.period_end,
                last_observation_at = excluded.last_observation_at,
                last_fetched_at = excluded.last_fetched_at,
                max_age_seconds = excluded.max_age_seconds,
                status = excluded.status,
                dataset_snapshot_id = excluded.dataset_snapshot_id,
                detail = excluded.detail,
                updated_at = excluded.updated_at
            """,
            (
                total_bars,
                earliest_bar_date,
                latest_bar_date,
                latest_bar_date,
                timestamp,
                PRICE_SOFT_MAX_AGE_DAYS * 86400,
                dataset_id,
                f"{total_bars} real daily bars across {len(fetched_bars)} staging symbols so far (unofficial Yahoo Finance chart endpoint).",
                timestamp,
            ),
        )
        # Commit per-symbol: real, deliberate partial-progress durability,
        # the same pattern already used by library_fetch.py -- if the
        # process dies mid-fetch, every symbol fetched so far survives and
        # this run's real Yahoo requests were not wasted.
        connection.commit()

    all_failed = {**failed_series, **failed_symbols}
    final_manifest = _json(
        {
            "source": "fred+yahoo",
            "macro_series": list(fetched_series),
            "macro_series_failed": failed_series,
            "price_symbols": list(fetched_bars),
            "price_symbols_failed": failed_symbols,
            "engine_mode": engine_mode,
            "observation_window": {"start": observation_start, "end": observation_end},
            "realtime_vintage": realtime,
            "price_fetch_start_date": STAGING_UNIVERSE_START_DATE,
        }
    )
    connection.execute(
        "UPDATE dataset_snapshots SET source_manifest_json = ? WHERE id = ?",
        (final_manifest, dataset_id),
    )
    connection.commit()

    message = (
        f"Fetched {total_rows} real FRED observations across {len(fetched_series)} series "
        f"and {total_bars} real daily bars across {len(fetched_bars)} staging symbols."
    )
    if all_failed:
        failure_detail = "; ".join(f"{key}: {reason}" for key, reason in all_failed.items())
        message += f" {len(all_failed)} item(s) failed and were skipped: {failure_detail}"
    return StageOutcome(
        status="completed_with_warnings" if all_failed else "completed",
        message=message,
        records_read=total_rows + total_bars,
        records_written=total_rows + total_bars,
        dataset_snapshot_id=dataset_id,
    )
