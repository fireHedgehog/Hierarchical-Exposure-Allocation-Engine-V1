from __future__ import annotations

import statistics
from dataclasses import dataclass

from backend.engine.factors.momentum_v2 import _pooled_ic_samples
from backend.engine.factors.types import Bar, HorizonReturn, InsufficientPriceDataError, SymbolMomentum
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

# naive-v3: adds Jegadeesh & Titman's (1993) 12-1 momentum (trailing
# 12-month return, most recent month skipped) as a 4th horizon in the live
# blend, alongside the existing 1m/3m/6m -- promoted out of `draft` after
# two independent real checks: 0.16 found it genuinely diversifying (0.08
# correlation with 1m, not flagged redundant, raised effective number of
# bets from 1.74 to 2.11), and 0.26 found it a real, significant forward-
# return predictor (r=+0.067) distinct in direction from 1m/3m's own
# significant REVERSAL finding -- the exact reason the two effects need
# their own separately time-windowed horizon rather than being blended
# into the same 1m/3m/6m calendar buckets. This version registers no new
# research; the evidence was already real and standing, only the promotion
# decision is new.
#
# HORIZON_LOOKBACKS now carries a third element, skip_days, needed only by
# this new horizon -- the existing three keep skip_days=0 (unchanged
# behavior). _pooled_ic_samples already supported skip_days (added for the
# same 12-1 research test, 0.26); reused here unchanged from momentum_v2.py
# rather than duplicated, since it is pure and version-agnostic.
#
# v2's code (momentum_v2.py) stays untouched and importable so any dataset
# snapshot already sealed under naive-v2 stays honestly reproducible.
#
# Registered in the strategies table as `cross_sectional_momentum`
# (naive-v3, verification_status='registered_only' -- promoting a real,
# significant single-horizon IC test into the live blend is not the full
# Milestone 4 gate: decorrelation across all four horizons together and a
# fitted, not naive-|r|-proportional-or-equal, weight still have not run).

HORIZON_LOOKBACKS: tuple[tuple[str, int, int], ...] = (
    ("1m", 21, 0),
    ("3m", 63, 0),
    ("6m", 126, 0),
    ("12m_skip1m", 252, 21),
)
FORWARD_HORIZON_TRADING_DAYS = 21
MIN_SAMPLES = 24
STRIDE_DAYS = 5  # naive spacing between sampled points; reduces, does not remove, overlap


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class HorizonWeightResult:
    horizon: str
    lookback_days: int
    weight: float  # signed: negative for a significantly reversal-shaped horizon, not just magnitude
    sample_size: int
    correlation: float | None
    p_value: float | None
    adjusted_p_value: float | None
    significant: bool
    status: str  # 'ok' | 'insufficient_data'


def compute_horizon_weights(bars_by_symbol: dict[str, list[Bar]]) -> list[HorizonWeightResult]:
    """Real per-horizon significance test, run fresh every call against
    whatever price history was actually fetched this run -- never a stored
    or hand-typed weight. Same mechanism as momentum_v2.py, generalized to
    a fourth horizon with its own skip_days."""

    raw: list[dict[str, object]] = []
    for horizon, lookback_days, skip_days in HORIZON_LOOKBACKS:
        x, y = _pooled_ic_samples(bars_by_symbol, lookback_days, skip_days=skip_days)
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
    # magnitude vector so it's always directly comparable, same convention as
    # v1's fixed 0.2/0.3/0.5. Normalization operates on magnitude only, before
    # sign is applied below, so it stays numerically stable regardless of how
    # many horizons turn out to be significant and reversal-shaped.
    weight_total = sum(raw_weight_by_horizon.values())
    magnitude_by_horizon = {horizon: value / weight_total for horizon, value in raw_weight_by_horizon.items()}
    # Sign the weight by the correlation's own real direction, not just its
    # magnitude (0.42's fix, unchanged here). Only applied where real,
    # corrected significance exists; every other horizon keeps today's
    # naive positive-momentum assumption.
    sign_by_horizon = {
        item["horizon"]: (-1.0 if item.get("correlation", 0) < 0 else 1.0)  # type: ignore[arg-type]
        for item in testable
        if item.get("significant")
    }
    weight_by_horizon = {
        horizon: magnitude * sign_by_horizon.get(horizon, 1.0) for horizon, magnitude in magnitude_by_horizon.items()
    }

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


def _horizon_returns_v3(
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
    for horizon, lookback_days, skip_days in HORIZON_LOOKBACKS:
        weight = weight_by_horizon[horizon]
        if len(bars_by_date) <= lookback_days:
            returns.append(HorizonReturn(horizon, lookback_days, weight, None))
            continue
        past = bars_by_date[-1 - lookback_days]
        # skip_days shifts the signal point back from the latest close (0
        # for 1m/3m/6m, unchanged) -- 12-1's own defining feature: the
        # horizon return is measured up to one month ago, not to today,
        # since the most recent month is a real, distinct reversal effect
        # this horizon deliberately excludes.
        signal = bars_by_date[-1 - skip_days] if skip_days else latest
        value = (signal.close - past.close) / abs(past.close) if past.close else None
        returns.append(HorizonReturn(horizon, lookback_days, weight, value))
        if value is not None:
            weighted_sum += weight * value
            # abs(weight): normalizes by magnitude, not the signed sum -- a
            # significantly reversal-shaped horizon's negative weight must
            # still count toward the total, not partially cancel it out and
            # destabilize the final division.
            weight_total += abs(weight)
    if weight_total == 0:
        raise InsufficientPriceDataError("no horizon had enough history to compute a return.")
    return weighted_sum / weight_total, returns


def compute_cross_section_v3(
    bars_by_symbol: dict[str, list[Bar]],
) -> tuple[list[SymbolMomentum], list[HorizonWeightResult]]:
    """Same cross-sectional z-score ranking as v2, now blending 4 horizons
    (1m/3m/6m/12m_skip1m) instead of 3 -- horizon weights still come from a
    real significance test over this run's own fetched price history. See
    module docstring for the full mechanism and its honest limits."""

    horizon_weights = compute_horizon_weights(bars_by_symbol)
    weight_by_horizon = {item.horizon: item.weight for item in horizon_weights}

    blended: dict[str, float] = {}
    returns_by_symbol: dict[str, list[HorizonReturn]] = {}
    latest_by_symbol: dict[str, Bar] = {}
    for symbol, bars in bars_by_symbol.items():
        ordered = sorted(bars, key=lambda bar: bar.time)
        try:
            blend, returns = _horizon_returns_v3(ordered, weight_by_horizon)
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
