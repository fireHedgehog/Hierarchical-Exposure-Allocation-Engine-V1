from __future__ import annotations

from backend.engine.allocation.envelope import (
    InsufficientAllocationDataError,
    RiskEnvelope,
    SleeveAllocation,
    SymbolAllocationInput,
)
from backend.engine.regime.scoring_v3 import (
    CURRENT_VINTAGE_ADVERSE_FREQUENCY_ADVERSE,
    CURRENT_VINTAGE_ADVERSE_FREQUENCY_SUPPORTIVE,
)

# Registered in the strategies table as `risk_envelope_allocation` (naive-v2,
# verification_status='registered_only').
#
# Real bug in naive-v1, found by H-MACRO10 (docs/hypotheses/archive/staging_1/macro-research/
# exposure-policy-calibration.md): naive-v1's `multiplier = clamp(confidence
# * 2.0, 0.5, 1.5)` was written when `regime_confidence` meant a roughly
# symmetric v1/v2 score. Since the naive-v3 macro promotion, `confidence` is
# a one-sided adverse-frequency reference. Under naive-v1's unchanged formula this
# collapses badly: stressed (0.345*2=0.69) gets MORE exposure than calm or
# middle (both floor at 0.5, since 0.071*2 and 0.238*2 are both under the
# 0.5 floor) -- backwards, and calm/middle become indistinguishable. Live-
# verified, not just reasoned about: a real pipeline run at confidence=0.24
# published exactly a 0.50x multiplier, this exact bug, already happening.
#
# Fix: monotonically DECREASING linear interpolation between the two disclosed
# Staging V1 endpoints -- calm maps to the top of the existing 0.5x-1.5x band
# and stressed to the bottom. H-MACRO10 supports the direction correction and
# this staging policy's historical path result; exact calibration to the current
# 13-factor runtime score remains pending.

MIN_MULTIPLIER = 0.5
MAX_MULTIPLIER = 1.5


def compute_risk_envelope(
    regime_confidence: float,
    symbol_inputs: list[SymbolAllocationInput],
) -> RiskEnvelope:
    """Naive top-down risk scaling, naive-v2: the legacy `regime_confidence`
    field carries a current-vintage adverse-frequency reference (see
    scoring_v3.py) and sets a gross-exposure multiplier, correctly DECREASING
    in that reference (a
    higher adverse frequency means less exposure, not more -- naive-v1's
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
        CURRENT_VINTAGE_ADVERSE_FREQUENCY_SUPPORTIVE,
        min(CURRENT_VINTAGE_ADVERSE_FREQUENCY_ADVERSE, regime_confidence),
    )
    span = CURRENT_VINTAGE_ADVERSE_FREQUENCY_ADVERSE - CURRENT_VINTAGE_ADVERSE_FREQUENCY_SUPPORTIVE
    fraction_toward_stressed = (
        clamped_confidence - CURRENT_VINTAGE_ADVERSE_FREQUENCY_SUPPORTIVE
    ) / span
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
        f"Staging risk scaling: six-month adverse-frequency reference "
        f"{regime_confidence:.1%} maps to a {multiplier:.2f}x gross-exposure multiplier "
        f"({MIN_MULTIPLIER}x-{MAX_MULTIPLIER}x band, higher adverse frequency -> lower exposure), "
        f"moving gross exposure from {current_gross:.0%} (equal-weight baseline) to {target_gross:.0%}. "
        "The frequency is current-vintage rather than release-time PIT; the exposure band remains a staging policy."
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
