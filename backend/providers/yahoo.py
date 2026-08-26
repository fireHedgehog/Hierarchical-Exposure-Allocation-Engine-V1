from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, NamedTuple

import httpx


class PriceBar(NamedTuple):
    symbol: str
    time: str  # ISO date (UTC midnight)
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None


class PriceFetchError(RuntimeError):
    """A real price-bar fetch failed. Callers must write no rows on this error."""


# Unofficial, undocumented, keyless endpoint — the same one the widely-used
# `yfinance` library calls. No formal published API/terms exist for it, and
# Yahoo can rate-limit, change shape, or block a User-Agent without notice;
# that fragility is exactly the argument for Intrinio in production mode
# (see docs/engine-milestones.md). It works today and needs no registration,
# so it is the pilot-tier choice for equity/ETF/crypto-reference price bars.
CHART_ENDPOINT = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def fetch_daily_bars(symbol: str, *, range_: str = "1y", start_date: str | None = None) -> list[PriceBar]:
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
    if start_date is not None:
        period1 = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        params["period1"] = period1
        params["period2"] = int(datetime.now(timezone.utc).timestamp())
    else:
        params["range"] = range_
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
    timestamps = result.get("timestamp")
    quote_list = result.get("indicators", {}).get("quote")
    if not isinstance(timestamps, list) or not isinstance(quote_list, list) or not quote_list:
        raise PriceFetchError(f"{symbol}: Yahoo response is missing timestamp/quote data.")
    quote = quote_list[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    # Prefer split/dividend-adjusted close for the return series this feeds —
    # unadjusted close would show a fake return spike at every split date.
    adjclose_list = result.get("indicators", {}).get("adjclose")
    adjcloses = adjclose_list[0].get("adjclose") if adjclose_list else None

    bars: list[PriceBar] = []
    for index, epoch_seconds in enumerate(timestamps):
        adjusted = adjcloses[index] if adjcloses and index < len(adjcloses) else None
        close = adjusted if adjusted is not None else (closes[index] if index < len(closes) else None)
        if close is None:
            continue  # a session with no trade (holiday artifact); skip rather than fabricate a bar
        bar_date = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).date().isoformat()
        bars.append(
            PriceBar(
                symbol=symbol,
                time=bar_date,
                open=opens[index] if index < len(opens) else None,
                high=highs[index] if index < len(highs) else None,
                low=lows[index] if index < len(lows) else None,
                close=close,
                volume=volumes[index] if index < len(volumes) else None,
            )
        )
    if not bars:
        raise PriceFetchError(f"{symbol}: Yahoo returned zero usable daily bars.")
    return bars
