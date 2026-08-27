from __future__ import annotations

from backend.engine.allocation.envelope import (
    InsufficientAllocationDataError,
    RiskEnvelope,
    SleeveAllocation,
    SymbolAllocationInput,
)
from backend.engine.regime.scoring_v3 import (
    HISTORICAL_DRAWDOWN_RATE_CALM,
    HISTORICAL_DRAWDOWN_RATE_STRESSED,
)

# Registered in the strategies table as `risk_envelope_allocation` (naive-v2,
# verification_status='registered_only').
#
# Real bug in naive-v1, found by H-MACRO10 (docs/hypotheses/macro-research/
# exposure-policy-calibration.md): naive-v1's `multiplier = clamp(confidence
# * 2.0, 0.5, 1.5)` was written when `regime_confidence` meant a roughly
# symmetric v1/v2 score. Since the naive-v3 macro promotion, `confidence` is
# a real, calibrated, one-sided P(drawdown) -- 0.071 (calm) to 0.345
# (stressed), see scoring_v3.py. Under naive-v1's unchanged formula this
# collapses badly: stressed (0.345*2=0.69) gets MORE exposure than calm or
# middle (both floor at 0.5, since 0.071*2 and 0.238*2 are both under the
# 0.5 floor) -- backwards, and calm/middle become indistinguishable. Live-
# verified, not just reasoned about: a real pipeline run at confidence=0.24
# published exactly a 0.50x multiplier, this exact bug, already happening.
#
# Fix: real, monotonically DECREASING linear interpolation between the same
# two real, disclosed, already-validated calibration endpoints
# (HISTORICAL_DRAWDOWN_RATE_CALM/STRESSED, H-MACRO09/OOS/threshold-
# sensitivity) -- calm maps to the top of the existing 0.5x-1.5x band,
# stressed to the bottom, same band as naive-v1, not a new one. No new
# numbers invented; reuses the real calibration this project already earned.

MIN_MULTIPLIER = 0.5
MAX_MULTIPLIER = 1.5


def compute_risk_envelope(
    regime_confidence: float,
    symbol_inputs: list[SymbolAllocationInput],
) -> RiskEnvelope:
    """Naive top-down risk scaling, naive-v2: regime confidence (a real,
    calibrated P(drawdown), 0.071-0.345 -- see scoring_v3.py) sets a
    gross-exposure multiplier, now correctly DECREASING in confidence (a
    higher drawdown probability means less exposure, not more -- naive-v1's
    formula had this backwards after the naive-v3 confidence semantics
    changed underneath it). Long-only for now, so net == gross -- a stated
    simplification, not a hidden one. Sleeve targets aggregate the
    per-symbol momentum tilts factor_engine already computed, scaled by the
    same multiplier.
    """

    if not symbol_inputs:
        raise InsufficientAllocationDataError("no symbol allocation inputs provided.")

    current_gross = sum(item.base_weight for item in symbol_inputs)
    current_net = current_gross

    clamped_confidence = max(
        HISTORICAL_DRAWDOWN_RATE_CALM, min(HISTORICAL_DRAWDOWN_RATE_STRESSED, regime_confidence)
    )
    span = HISTORICAL_DRAWDOWN_RATE_STRESSED - HISTORICAL_DRAWDOWN_RATE_CALM
    fraction_toward_stressed = (clamped_confidence - HISTORICAL_DRAWDOWN_RATE_CALM) / span
    multiplier = MAX_MULTIPLIER - fraction_toward_stressed * (MAX_MULTIPLIER - MIN_MULTIPLIER)
    multiplier = max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, multiplier))  # defensive, already in-range by construction

    target_gross = current_gross * multiplier
    target_net = target_gross

    by_category: dict[str, list[SymbolAllocationInput]] = {}
    for item in symbol_inputs:
        by_category.setdefault(item.category, []).append(item)
    sleeves = [
        SleeveAllocation(
            category=category,
            symbols=[item.symbol for item in items],
            avg_composite_score=sum(item.composite_score for item in items) / len(items),
            base_weight_sum=sum(item.base_weight for item in items),
            target_weight_sum=sum(item.target_weight for item in items) * multiplier,
        )
        for category, items in sorted(by_category.items())
    ]
    summary = (
        f"Naive risk scaling (v2, direction-corrected): regime confidence {regime_confidence:.1%} "
        f"(P of a real drawdown) maps to a {multiplier:.2f}x gross-exposure multiplier "
        f"({MIN_MULTIPLIER}x-{MAX_MULTIPLIER}x band, higher drawdown risk -> lower exposure), "
        f"moving gross exposure from {current_gross:.0%} (equal-weight baseline) to {target_gross:.0%}."
    )
    return RiskEnvelope(
        current_gross_exposure=current_gross,
        current_net_exposure=current_net,
        target_gross_exposure=target_gross,
        target_net_exposure=target_net,
        gross_multiplier=multiplier,
        sleeves=sleeves,
        summary=summary,
    )
