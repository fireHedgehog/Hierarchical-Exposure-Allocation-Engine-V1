from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, NamedTuple

import httpx


class PriceBar(NamedTuple):
    symbol: str
    time: str  # ISO date (UTC midnight)
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    # Explicit dual-basis fields for honest gap/range research. Existing
    # callers that construct the original 7-field tuple keep working because
    # every new field is optional.
    raw_close: float | None = None
    adjusted_close: float | None = None
    adjusted_open: float | None = None
    adjusted_high: float | None = None
    adjusted_low: float | None = None
    adjustment_factor: float | None = None


class PriceHistory(list[PriceBar]):
    """Daily bars plus the small provider metadata needed to audit coverage."""

    def __init__(
        self,
        bars: Iterable[PriceBar] = (),
        *,
        provider_first_trade_date: str | None,
        provider_data_granularity: str | None,
        provider_exchange_timezone: str | None,
    ) -> None:
        super().__init__(bars)
        self.provider_first_trade_date = provider_first_trade_date
        self.provider_data_granularity = provider_data_granularity
        self.provider_exchange_timezone = provider_exchange_timezone


class PriceFetchError(RuntimeError):
    """A real price-bar fetch failed. Callers must write no rows on this error."""


# Unofficial, undocumented, keyless endpoint — the same one the widely-used
# `yfinance` library calls. No formal published API/terms exist for it, and
# Yahoo can rate-limit, change shape, or block a User-Agent without notice;
# that fragility is exactly the argument for Intrinio in production mode
# (see docs/engine-milestones.md). It works today and needs no registration,
# so it is the pilot-tier choice for equity/ETF/crypto-reference price bars.
CHART_ENDPOINT = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Real courtesy pacing (added 2026-08-28, direct user request: "we don't
# want to get blocked by yahoo"). This is the ONE place every real call to
# this unofficial, keyless endpoint funnels through -- the live pipeline's
# fetch_data_stage and the separate library_fetch batch path both call this
# same function per symbol, so pacing it here protects both at once rather
# than duplicating a delay in each caller. A module-level lock + timestamp
# is enough for this local-first, single-operator tool (no real concurrent-
# request fan-out to guard against, just the two admin-triggered fetch
# paths that could in principle run close together).
MIN_REQUEST_INTERVAL_SECONDS = 0.25
_pacing_lock = threading.Lock()
_last_request_at: float = 0.0


def _wait_for_pacing_slot() -> None:
    global _last_request_at
    with _pacing_lock:
        now = time.monotonic()
        wait = MIN_REQUEST_INTERVAL_SECONDS - (now - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def fetch_daily_bars(
    symbol: str,
    *,
    range_: str = "1y",
    start_date: str | None = None,
    end_date: str | None = None,
) -> PriceHistory:
    """start_date (an ISO date), when given, requests an explicit
    period1..now window instead of a relative range and takes priority over
    range_. This is not cosmetic: Yahoo's chart endpoint silently degrades
    interval=1d to a coarser real resolution once a relative range (e.g.
    range=max) spans many years -- verified directly (2026-08-26): GLD's
    real full history via range=max returned only 262 bars (weekly/monthly
    resolution in daily's clothing), while the identical span requested via
    explicit period1/period2 returned the real 5,467 true daily bars. A
    fixed-date-anchored fetch is required for genuine daily granularity over
    a multi-decade window, not just a style preference."""

    params: dict[str, str | int] = {"interval": "1d"}
    if end_date is not None and start_date is None:
        raise PriceFetchError(f"{symbol}: end_date requires an explicit start_date.")
    if start_date is not None:
        period1 = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        params["period1"] = period1
        if end_date is None:
            params["period2"] = int(datetime.now(timezone.utc).timestamp())
        else:
            try:
                end_exclusive = date.fromisoformat(end_date) + timedelta(days=1)
            except ValueError as error:
                raise PriceFetchError(f"{symbol}: invalid end_date {end_date!r}.") from error
            params["period2"] = int(
                datetime.combine(end_exclusive, datetime.min.time(), tzinfo=timezone.utc).timestamp()
            )
    else:
        params["range"] = range_
    _wait_for_pacing_slot()
    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            trust_env=False,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; HEAE-local-operator/0.1)",
            },
        ) as client:
            response = client.get(
                CHART_ENDPOINT.format(symbol=symbol),
                params=params,
            )
    except httpx.HTTPError as error:
        raise PriceFetchError(
            f"{symbol}: request failed ({error.__class__.__name__})."
        ) from error

    if response.status_code != 200:
        raise PriceFetchError(f"{symbol}: Yahoo returned HTTP {response.status_code}.")
    try:
        payload: Any = response.json()
    except ValueError as error:
        raise PriceFetchError(f"{symbol}: Yahoo returned a non-JSON response.") from error

    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict):
        raise PriceFetchError(f"{symbol}: unexpected response shape from Yahoo.")
    if chart.get("error"):
        message = chart["error"].get("description") if isinstance(chart["error"], dict) else chart["error"]
        raise PriceFetchError(f"{symbol}: Yahoo reported an error — {message}.")
    results = chart.get("result")
    if not isinstance(results, list) or not results:
        raise PriceFetchError(f"{symbol}: Yahoo returned no result series.")
    result = results[0]
    if not isinstance(result, Mapping):
        raise PriceFetchError(f"{symbol}: Yahoo result series is not an object.")
    meta = result.get("meta")
    if not isinstance(meta, Mapping):
        raise PriceFetchError(f"{symbol}: Yahoo response is missing chart metadata.")
    timestamps = result.get("timestamp")
    indicators = result.get("indicators")
    if not isinstance(indicators, Mapping):
        raise PriceFetchError(f"{symbol}: Yahoo response is missing indicator data.")
    quote_list = indicators.get("quote")
    if not isinstance(timestamps, list) or not isinstance(quote_list, list) or not quote_list:
        raise PriceFetchError(f"{symbol}: Yahoo response is missing timestamp/quote data.")
    quote = quote_list[0]
    if not isinstance(quote, Mapping):
        raise PriceFetchError(f"{symbol}: Yahoo quote series is not an object.")
    quote_series: dict[str, list[Any]] = {}
    for field in ("open", "high", "low", "close", "volume"):
        values = quote.get(field)
        if not isinstance(values, list) or len(values) != len(timestamps):
            raise PriceFetchError(
                f"{symbol}: Yahoo {field} series is missing or misaligned with timestamps."
            )
        quote_series[field] = values
    opens = quote_series["open"]
    highs = quote_series["high"]
    lows = quote_series["low"]
    closes = quote_series["close"]
    volumes = quote_series["volume"]
    # Prefer split/dividend-adjusted close for the return series this feeds —
    # unadjusted close would show a fake return spike at every split date.
    # Preserve raw close and derive O/H/L on the same adjusted basis as close.
    # The previous adapter mixed raw O/H/L with adjusted close in one bar;
    # that was safe for close-to-close returns but invalid for gaps, ATR,
    # ranges, and candles.
    adjclose_list = indicators.get("adjclose")
    adjcloses: list[Any] | None = None
    if adjclose_list is not None:
        if (
            not isinstance(adjclose_list, list)
            or not adjclose_list
            or not isinstance(adjclose_list[0], Mapping)
            or not isinstance(adjclose_list[0].get("adjclose"), list)
        ):
            raise PriceFetchError(f"{symbol}: Yahoo adjusted-close series changed shape.")
        adjcloses = adjclose_list[0]["adjclose"]
        if len(adjcloses) != len(timestamps):
            raise PriceFetchError(
                f"{symbol}: Yahoo adjusted-close series is misaligned with timestamps."
            )

    bars: list[PriceBar] = []
    for index, epoch_seconds in enumerate(timestamps):
        raw_open = opens[index] if index < len(opens) else None
        raw_high = highs[index] if index < len(highs) else None
        raw_low = lows[index] if index < len(lows) else None
        raw_close = closes[index] if index < len(closes) else None
        adjusted = adjcloses[index] if adjcloses is not None and index < len(adjcloses) else None
        close = adjusted if adjusted is not None else raw_close
        if close is None:
            continue  # a session with no trade (holiday artifact); skip rather than fabricate a bar
        # Yahoo can emit zero-valued pre-listing placeholder rows before the
        # first real trade (PRTA currently has three).  Zero is not a price and
        # cannot support either raw or adjusted OHLC research, so omit the
        # placeholder instead of rejecting the security's entire real history.
        if float(close) <= 0:
            continue
        if adjcloses is not None and adjusted is None:
            raise PriceFetchError(
                f"{symbol}: Yahoo returned a partially missing adjusted-close series."
            )
        adjustment_factor: float | None
        if adjusted is not None and raw_close not in (None, 0):
            adjustment_factor = float(adjusted) / float(raw_close)
        else:
            adjustment_factor = None

        adjusted_open = (
            None if raw_open is None or adjustment_factor is None
            else float(raw_open) * adjustment_factor
        )
        adjusted_high = (
            None if raw_high is None or adjustment_factor is None
            else float(raw_high) * adjustment_factor
        )
        adjusted_low = (
            None if raw_low is None or adjustment_factor is None
            else float(raw_low) * adjustment_factor
        )

        try:
            bar_date = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).date().isoformat()
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise PriceFetchError(f"{symbol}: Yahoo returned an invalid daily timestamp.") from error
        bars.append(
            PriceBar(
                symbol=symbol,
                time=bar_date,
                open=raw_open,
                high=raw_high,
                low=raw_low,
                close=close,
                volume=volumes[index] if index < len(volumes) else None,
                raw_close=raw_close,
                # A missing adjclose is unknown, not evidence that the factor
                # equals 1. `close` keeps its legacy raw fallback so existing
                # close-only consumers still run; every explicit adjusted
                # field remains NULL and therefore fails the research-ready
                # dual-basis contract.
                adjusted_close=adjusted,
                adjusted_open=adjusted_open,
                adjusted_high=adjusted_high,
                adjusted_low=adjusted_low,
                adjustment_factor=adjustment_factor,
            )
        )
    if not bars:
        raise PriceFetchError(f"{symbol}: Yahoo returned zero usable daily bars.")
    first_trade_raw = meta.get("firstTradeDate")
    try:
        first_trade_date = (
            (
                datetime(1970, 1, 1, tzinfo=timezone.utc)
                + timedelta(seconds=float(first_trade_raw))
            ).date().isoformat()
            if first_trade_raw is not None
            else None
        )
    except (OSError, OverflowError, TypeError, ValueError) as error:
        raise PriceFetchError(f"{symbol}: Yahoo returned an invalid firstTradeDate.") from error
    granularity = meta.get("dataGranularity")
    timezone_name = meta.get("exchangeTimezoneName")
    return PriceHistory(
        bars,
        provider_first_trade_date=first_trade_date,
        provider_data_granularity=str(granularity) if granularity is not None else None,
        provider_exchange_timezone=str(timezone_name) if timezone_name is not None else None,
    )
