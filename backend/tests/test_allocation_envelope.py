from __future__ import annotations

import pytest

from backend.engine.allocation.envelope import (
    InsufficientAllocationDataError,
    SymbolAllocationInput,
    compute_risk_envelope,
)


def _inputs() -> list[SymbolAllocationInput]:
    return [
        SymbolAllocationInput("SPY", "broad_equity_etf", 0.3, 1 / 21, 0.06),
        SymbolAllocationInput("XLF", "sector_equity_etf", -0.2, 1 / 21, 0.03),
        SymbolAllocationInput("XLK", "sector_equity_etf", 0.5, 1 / 21, 0.08),
        SymbolAllocationInput("TLT", "bond_duration_etf", -0.6, 1 / 21, 0.02),
    ]


def test_raises_instead_of_fabricating_when_no_inputs() -> None:
    with pytest.raises(InsufficientAllocationDataError):
        compute_risk_envelope(0.5, [])


def test_neutral_confidence_leaves_gross_exposure_unchanged() -> None:
    envelope = compute_risk_envelope(0.5, _inputs())
    assert envelope.gross_multiplier == pytest.approx(1.0)
    assert envelope.target_gross_exposure == pytest.approx(envelope.current_gross_exposure)


def test_high_confidence_scales_up_and_low_confidence_scales_down() -> None:
    high = compute_risk_envelope(0.95, _inputs())
    low = compute_risk_envelope(0.05, _inputs())
    assert high.gross_multiplier > 1.0
    assert low.gross_multiplier < 1.0
    assert high.target_gross_exposure > low.target_gross_exposure


def test_multiplier_is_clamped_to_a_half_to_one_and_a_half_band() -> None:
    high = compute_risk_envelope(1.0, _inputs())
    low = compute_risk_envelope(0.0, _inputs())
    assert high.gross_multiplier == pytest.approx(1.5)
    assert low.gross_multiplier == pytest.approx(0.5)


def test_net_equals_gross_in_this_long_only_naive_model() -> None:
    envelope = compute_risk_envelope(0.7, _inputs())
    assert envelope.target_net_exposure == pytest.approx(envelope.target_gross_exposure)
    assert envelope.current_net_exposure == pytest.approx(envelope.current_gross_exposure)


def test_sleeves_group_by_category_with_real_aggregates() -> None:
    envelope = compute_risk_envelope(0.5, _inputs())
    by_category = {sleeve.category: sleeve for sleeve in envelope.sleeves}
    assert set(by_category) == {"broad_equity_etf", "sector_equity_etf", "bond_duration_etf"}
    sector = by_category["sector_equity_etf"]
    assert set(sector.symbols) == {"XLF", "XLK"}
    assert sector.avg_composite_score == pytest.approx((-0.2 + 0.5) / 2)
