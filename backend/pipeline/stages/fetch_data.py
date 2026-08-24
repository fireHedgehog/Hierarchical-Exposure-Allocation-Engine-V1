from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta

from backend.pipeline.stages.common import (
    FRED_OBSERVATION_WINDOW_DAYS,
    PRICE_FETCH_RANGE,
    PRICE_SOFT_MAX_AGE_DAYS,
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
) -> StageOutcome:
    """Fetch real macro observations (FRED) and price bars (Yahoo) into one
    new unsealed dataset. Writes nothing if any fetch fails — no orphaned
    partial dataset. The price-bar universe is read from `staging_symbols`
    (DB-driven), never a ticker list embedded in this code.
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
    realtime = as_of.isoformat()

    fetched_series: dict[str, list[FredObservation]] = {}
    for series_id in SERIES_METADATA:
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
            return StageOutcome(
                status="failed",
                message=f"FRED fetch failed, no dataset was written: {error}",
                error_code="fred_fetch_failed",
            )
        if not observations:
            return StageOutcome(
                status="failed",
                message=f"FRED returned zero observations for {series_id}; no dataset was written.",
                error_code="fred_empty_series",
            )
        fetched_series[series_id] = observations

    staging_rows = connection.execute(
        """
        SELECT symbol, name, category FROM staging_symbols
        WHERE active = 1 AND category != 'macro_series'
        ORDER BY sort_order
        """
    ).fetchall()
    fetched_bars: dict[str, list[PriceBar]] = {}
    for row in staging_rows:
        try:
            bars = price_fetcher(row["symbol"], range_=PRICE_FETCH_RANGE)
        except PriceFetchError as error:
            return StageOutcome(
                status="failed",
                message=f"Price fetch failed, no dataset was written: {error}",
                error_code="price_fetch_failed",
            )
        if not bars:
            return StageOutcome(
                status="failed",
                message=f"No usable price bars returned for {row['symbol']}; no dataset was written.",
                error_code="price_empty_series",
            )
        fetched_bars[row["symbol"]] = bars

    dataset_id = f"real-macro-{uuid.uuid4()}"
    timestamp = _iso_z(now)
    manifest = _json(
        {
            "source": "fred+yahoo",
            "macro_series": list(SERIES_METADATA),
            "price_symbols": [row["symbol"] for row in staging_rows],
            "engine_mode": engine_mode,
            "observation_window": {"start": observation_start, "end": observation_end},
            "realtime_vintage": realtime,
            "price_fetch_range": PRICE_FETCH_RANGE,
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
                meta["max_age_days"] * 86400,
                dataset_id,
                f"{len(observations)} real point-in-time observations fetched from FRED.",
                timestamp,
            ),
        )

    category_by_symbol = {row["symbol"]: row["category"] for row in staging_rows}
    name_by_symbol = {row["symbol"]: row["name"] for row in staging_rows}
    total_bars = 0
    earliest_bar_date: str | None = None
    latest_bar_date: str | None = None
    for symbol, bars in fetched_bars.items():
        category = category_by_symbol[symbol]
        security_id = _security_id_for(symbol, category)
        connection.execute(
            """
            INSERT OR IGNORE INTO securities (
                security_id, primary_symbol, name, asset_type, exchange, currency, sector, active
            ) VALUES (?, ?, ?, ?, NULL, 'USD', NULL, 1)
            """,
            (security_id, symbol, name_by_symbol[symbol], _asset_type_for(category)),
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

    if fetched_bars:
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
                f"{total_bars} real daily bars across {len(fetched_bars)} staging symbols (unofficial Yahoo Finance chart endpoint).",
                timestamp,
            ),
        )

    return StageOutcome(
        status="completed",
        message=(
            f"Fetched {total_rows} real FRED observations across {len(SERIES_METADATA)} series "
            f"and {total_bars} real daily bars across {len(fetched_bars)} staging symbols."
        ),
        records_read=total_rows + total_bars,
        records_written=total_rows + total_bars,
        dataset_snapshot_id=dataset_id,
    )
