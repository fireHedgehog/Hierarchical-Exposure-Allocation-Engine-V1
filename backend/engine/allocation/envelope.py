from __future__ import annotations

from dataclasses import dataclass


class InsufficientAllocationDataError(ValueError):
    """No symbol allocation inputs were provided to build an envelope from."""


@dataclass(frozen=True)
class SymbolAllocationInput:
    symbol: str
    category: str
    composite_score: float
    base_weight: float
    target_weight: float  # from factor_engine's suggested_weight — a within-universe tilt


@dataclass(frozen=True)
class SleeveAllocation:
    category: str
    symbols: list[str]
    avg_composite_score: float
    base_weight_sum: float
    target_weight_sum: float


@dataclass(frozen=True)
class RiskEnvelope:
    current_gross_exposure: float
    current_net_exposure: float
    target_gross_exposure: float
    target_net_exposure: float
    gross_multiplier: float
    sleeves: list[SleeveAllocation]
    summary: str


def compute_risk_envelope(
    regime_confidence: float,
    symbol_inputs: list[SymbolAllocationInput],
) -> RiskEnvelope:
    """Naive top-down risk scaling: regime confidence (already a real,
    computed value from regime_filter) sets a gross-exposure multiplier
    against the equal-weight baseline. Long-only for now, so net == gross —
    a stated simplification, not a hidden one. Sleeve targets aggregate the
    per-symbol momentum tilts factor_engine already computed, scaled by the
    same multiplier.
    """

    if not symbol_inputs:
        raise InsufficientAllocationDataError("no symbol allocation inputs provided.")

    current_gross = sum(item.base_weight for item in symbol_inputs)
    current_net = current_gross
    multiplier = max(0.5, min(1.5, regime_confidence * 2.0))
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
        f"Naive risk scaling: regime confidence {regime_confidence:.0%} maps to a "
        f"{multiplier:.2f}x gross-exposure multiplier (0.5x-1.5x band), moving gross "
        f"exposure from {current_gross:.0%} (equal-weight baseline) to {target_gross:.0%}."
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
