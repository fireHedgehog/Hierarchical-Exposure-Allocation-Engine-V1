from __future__ import annotations

import statistics

from backend.engine.factors.types import Bar, HorizonReturn, InsufficientPriceDataError, SymbolMomentum

# Naive, first-pass cross-sectional momentum. Real prices in, real ranking
# out — the coefficients (horizons, blend weights) are deliberately
# unoptimized (see docs/engine-milestones.md, Milestone 3/4). The one
# non-negotiable: every number here traces to a fetched close price, never a
# hand-typed value.

# (lookback in trading days, blend weight)
HORIZONS: tuple[tuple[str, int, float], ...] = (
    ("1m", 21, 0.2),
    ("3m", 63, 0.3),
    ("6m", 126, 0.5),
)


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _horizon_returns(bars_by_date: list[Bar]) -> tuple[float, list[HorizonReturn]]:
    if len(bars_by_date) < 22:
        raise InsufficientPriceDataError(
            f"only {len(bars_by_date)} bars available; need at least 22 for a 1-month lookback."
        )
    latest = bars_by_date[-1]
    returns: list[HorizonReturn] = []
    weighted_sum = 0.0
    weight_total = 0.0
    for horizon, lookback_days, weight in HORIZONS:
        if len(bars_by_date) <= lookback_days:
            returns.append(HorizonReturn(horizon, lookback_days, weight, None))
            continue
        past = bars_by_date[-1 - lookback_days]
        value = (latest.close - past.close) / abs(past.close) if past.close else None
        returns.append(HorizonReturn(horizon, lookback_days, weight, value))
        if value is not None:
            weighted_sum += weight * value
            weight_total += weight
    if weight_total == 0:
        raise InsufficientPriceDataError("no horizon had enough history to compute a return.")
    return weighted_sum / weight_total, returns


def compute_cross_section(
    bars_by_symbol: dict[str, list[Bar]],
) -> list[SymbolMomentum]:
    """Rank symbols by a naive blended-momentum score, relative to each other.

    Cross-sectional by design: the composite score is a z-score within this
    call's own universe, matching "which securities are strongest or weakest
    relative to their peers" (edition-v1.md) rather than an absolute
    threshold. Raises InsufficientPriceDataError only if EVERY symbol lacks
    history; an individual thin symbol is silently excluded from ranking
    rather than failing the whole cross-section — call sites should note
    that in the result rather than treat it as an engine failure.
    """

    blended: dict[str, float] = {}
    returns_by_symbol: dict[str, list[HorizonReturn]] = {}
    latest_by_symbol: dict[str, Bar] = {}
    for symbol, bars in bars_by_symbol.items():
        ordered = sorted(bars, key=lambda bar: bar.time)
        try:
            blend, returns = _horizon_returns(ordered)
        except InsufficientPriceDataError:
            continue
        blended[symbol] = blend
        returns_by_symbol[symbol] = returns
        latest_by_symbol[symbol] = ordered[-1]

    if not blended:
        raise InsufficientPriceDataError("no symbol in the universe has enough price history to score.")

    values = list(blended.values())
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0

    results: list[SymbolMomentum] = []
    for symbol, blend in blended.items():
        z = (blend - mean) / stdev if stdev > 1e-9 else 0.0
        composite = _clamp(z / 2.0)
        direction = "bullish" if composite > 0.1 else "bearish" if composite < -0.1 else "neutral"
        results.append(
            SymbolMomentum(
                symbol=symbol,
                last_close=latest_by_symbol[symbol].close,
                last_date=latest_by_symbol[symbol].time,
                returns=returns_by_symbol[symbol],
                blended_return=blend,
                composite_score=composite,
                rank=0,  # filled below
                direction=direction,
                strength=_clamp(abs(composite), 0.0, 1.0),
            )
        )

    results.sort(key=lambda item: (-item.composite_score, item.symbol))
    ranked = [
        SymbolMomentum(
            symbol=item.symbol,
            last_close=item.last_close,
            last_date=item.last_date,
            returns=item.returns,
            blended_return=item.blended_return,
            composite_score=item.composite_score,
            rank=index,
            direction=item.direction,
            strength=item.strength,
        )
        for index, item in enumerate(results, 1)
    ]
    return ranked
