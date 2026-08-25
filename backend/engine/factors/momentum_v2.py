from __future__ import annotations

import statistics
from dataclasses import dataclass

from backend.engine.factors.types import Bar, HorizonReturn, InsufficientPriceDataError, SymbolMomentum
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

# naive-v2: cross-sectional momentum with statistically-informed horizon
# weights, replacing v1's hand-picked 0.2/0.3/0.5 blend (momentum.py).
#
# For each horizon (1m/3m/6m), this pools every staging symbol's own
# trailing-horizon-return vs. forward-return pairs -- walked across that
# symbol's real fetched price history, not just today's single reading --
# and runs the same real Pearson-correlation + Benjamini-Hochberg
# significance test already proven in
# engine/research/factor_symbol_correlation.py (Milestone 4, step 1),
# applied here to momentum horizons instead of macro factors. A horizon's
# blend weight is proportional to |correlation| among horizons that pass
# correction. If none pass -- real markets are noisy, and this staging
# universe is small -- every horizon falls back to equal weight rather than
# the pipeline blocking or silently keeping v1's hand-picked numbers: a real
# statistical test that finds nothing significant is still a real, honest
# result worth showing, not a reason to hide the momentum score (this
# project's "naive over broken" rule).
#
# v1's code (momentum.py) stays untouched and importable so any dataset
# snapshot already sealed under naive-v1 stays honestly reproducible.
#
# Registered in the strategies table as `cross_sectional_momentum`
# (naive-v2, verification_status='registered_only' -- one significance test
# per horizon is not the full Milestone 4 gate: decorrelation across
# horizons and a fitted, not naive-equal-or-|r|-proportional, weight still
# have not run).

HORIZON_LOOKBACKS: tuple[tuple[str, int], ...] = (("1m", 21), ("3m", 63), ("6m", 126))
FORWARD_HORIZON_TRADING_DAYS = 21
MIN_SAMPLES = 24
STRIDE_DAYS = 5  # naive spacing between sampled points; reduces, does not remove, overlap


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class HorizonWeightResult:
    horizon: str
    lookback_days: int
    weight: float
    sample_size: int
    correlation: float | None
    p_value: float | None
    adjusted_p_value: float | None
    significant: bool
    status: str  # 'ok' | 'insufficient_data'


def _pooled_ic_samples(
    bars_by_symbol: dict[str, list[Bar]],
    lookback_days: int,
    forward_days: int = FORWARD_HORIZON_TRADING_DAYS,
    stride: int = STRIDE_DAYS,
    skip_days: int = 0,
) -> tuple[list[float], list[float]]:
    """Real, pooled (horizon return, forward return) pairs across every
    staging symbol's own real price history -- no interpolation, no
    synthetic fill. Each symbol contributes independently; pooling assumes
    the same horizon->forward-return relationship holds across symbols,
    which is the naive part of this test (a per-symbol test would need far
    more history per symbol than this staging universe has).

    skip_days (default 0, unused by 1m/3m/6m) supports a Jegadeesh &
    Titman-style "12-1" specification: the horizon return is measured up to
    skip_days before the decision point, not up to it, while the forward
    return is still measured from the real decision point (now_close)
    onward -- short-term reversal and medium-term momentum are distinct
    effects, so the signal window and the entry point deliberately differ.
    """

    x: list[float] = []
    y: list[float] = []
    for bars in bars_by_symbol.values():
        ordered = sorted(bars, key=lambda bar: bar.time)
        closes = [bar.close for bar in ordered]
        n = len(closes)
        for i in range(lookback_days, n - forward_days, stride):
            past_close = closes[i - lookback_days]
            signal_close = closes[i - skip_days]
            now_close = closes[i]
            future_close = closes[i + forward_days]
            if past_close == 0 or now_close == 0:
                continue
            x.append((signal_close - past_close) / abs(past_close))
            y.append((future_close - now_close) / abs(now_close))
    return x, y


def compute_horizon_weights(bars_by_symbol: dict[str, list[Bar]]) -> list[HorizonWeightResult]:
    """Real per-horizon significance test, run fresh every call against
    whatever price history was actually fetched this run -- never a stored
    or hand-typed weight."""

    raw: list[dict[str, object]] = []
    for horizon, lookback_days in HORIZON_LOOKBACKS:
        x, y = _pooled_ic_samples(bars_by_symbol, lookback_days)
        if len(x) < MIN_SAMPLES:
            raw.append(
                {"horizon": horizon, "lookback_days": lookback_days, "sample_size": len(x), "status": "insufficient_data"}
            )
            continue
        correlation, p_value = pearson_significance(x, y)
        raw.append(
            {
                "horizon": horizon,
                "lookback_days": lookback_days,
                "sample_size": len(x),
                "correlation": correlation,
                "p_value": p_value,
                "status": "ok",
            }
        )

    testable = [item for item in raw if item["status"] == "ok"]
    p_values = [item["p_value"] for item in testable]  # type: ignore[misc]
    adjusted_p_values, significant_flags = benjamini_hochberg(p_values, alpha=0.05)
    for item, adjusted_p_value, is_significant in zip(testable, adjusted_p_values, significant_flags):
        item["adjusted_p_value"] = adjusted_p_value
        item["significant"] = is_significant

    significant_items = [item for item in testable if item.get("significant")]
    if significant_items:
        total_abs_correlation = sum(abs(item["correlation"]) for item in significant_items)  # type: ignore[arg-type]
        significant_weight_by_horizon = {
            item["horizon"]: abs(item["correlation"]) / total_abs_correlation for item in significant_items  # type: ignore[arg-type]
        }
    else:
        # No horizon cleared correction this run -- naive equal-weight
        # fallback for every horizon, not a blocked or hidden score.
        significant_weight_by_horizon = {}

    equal_weight = 1.0 / len(HORIZON_LOOKBACKS)
    raw_weight_by_horizon: dict[str, float] = {}
    for item in raw:
        horizon = item["horizon"]  # type: ignore[assignment]
        if item["status"] == "insufficient_data":
            raw_weight_by_horizon[horizon] = equal_weight  # type: ignore[index]
        else:
            raw_weight_by_horizon[horizon] = significant_weight_by_horizon.get(horizon, equal_weight)  # type: ignore[index]
    # A significant horizon's |r|-proportional share and a non-significant/
    # insufficient horizon's equal-weight fallback are drawn from different
    # scales (they can sum to more or less than 1 together) -- normalize the
    # final vector so displayed weights are always directly comparable, same
    # convention as v1's fixed 0.2/0.3/0.5 (and always > 0 in total, so the
    # blend below can never hit a zero-weight, blocked composite).
    weight_total = sum(raw_weight_by_horizon.values())
    weight_by_horizon = {horizon: value / weight_total for horizon, value in raw_weight_by_horizon.items()}

    results: list[HorizonWeightResult] = []
    for item in raw:
        horizon = item["horizon"]  # type: ignore[assignment]
        if item["status"] == "insufficient_data":
            results.append(
                HorizonWeightResult(
                    horizon=horizon,  # type: ignore[arg-type]
                    lookback_days=item["lookback_days"],  # type: ignore[arg-type]
                    weight=weight_by_horizon[horizon],  # type: ignore[index]
                    sample_size=item["sample_size"],  # type: ignore[arg-type]
                    correlation=None,
                    p_value=None,
                    adjusted_p_value=None,
                    significant=False,
                    status="insufficient_data",
                )
            )
            continue
        results.append(
            HorizonWeightResult(
                horizon=horizon,  # type: ignore[arg-type]
                lookback_days=item["lookback_days"],  # type: ignore[arg-type]
                weight=weight_by_horizon[horizon],  # type: ignore[index]
                sample_size=item["sample_size"],  # type: ignore[arg-type]
                correlation=item["correlation"],  # type: ignore[arg-type]
                p_value=item["p_value"],  # type: ignore[arg-type]
                adjusted_p_value=item["adjusted_p_value"],  # type: ignore[arg-type]
                significant=bool(item["significant"]),
                status="ok",
            )
        )
    return results


def _horizon_returns_v2(
    bars_by_date: list[Bar], weight_by_horizon: dict[str, float]
) -> tuple[float, list[HorizonReturn]]:
    if len(bars_by_date) < 22:
        raise InsufficientPriceDataError(
            f"only {len(bars_by_date)} bars available; need at least 22 for a 1-month lookback."
        )
    latest = bars_by_date[-1]
    returns: list[HorizonReturn] = []
    weighted_sum = 0.0
    weight_total = 0.0
    for horizon, lookback_days in HORIZON_LOOKBACKS:
        weight = weight_by_horizon[horizon]
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


def compute_cross_section_v2(
    bars_by_symbol: dict[str, list[Bar]],
) -> tuple[list[SymbolMomentum], list[HorizonWeightResult]]:
    """Same cross-sectional z-score ranking as v1 (momentum.py), with
    horizon blend weights now coming from a real significance test over this
    run's own fetched price history instead of hand-picked constants. See
    module docstring for the full mechanism and its honest limits."""

    horizon_weights = compute_horizon_weights(bars_by_symbol)
    weight_by_horizon = {item.horizon: item.weight for item in horizon_weights}

    blended: dict[str, float] = {}
    returns_by_symbol: dict[str, list[HorizonReturn]] = {}
    latest_by_symbol: dict[str, Bar] = {}
    for symbol, bars in bars_by_symbol.items():
        ordered = sorted(bars, key=lambda bar: bar.time)
        try:
            blend, returns = _horizon_returns_v2(ordered, weight_by_horizon)
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
    return ranked, horizon_weights
