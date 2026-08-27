from __future__ import annotations

import pytest

from backend.engine.allocation.envelope import InsufficientAllocationDataError, SymbolAllocationInput
from backend.engine.allocation.envelope_v2 import compute_risk_envelope
from backend.engine.regime.scoring_v3 import (
    HISTORICAL_DRAWDOWN_RATE_CALM,
    HISTORICAL_DRAWDOWN_RATE_MIDDLE,
    HISTORICAL_DRAWDOWN_RATE_STRESSED,
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
        compute_risk_envelope(HISTORICAL_DRAWDOWN_RATE_MIDDLE, [])


def test_calm_confidence_gives_the_max_multiplier() -> None:
    envelope = compute_risk_envelope(HISTORICAL_DRAWDOWN_RATE_CALM, _inputs())
    assert envelope.gross_multiplier == pytest.approx(1.5)


def test_stressed_confidence_gives_the_min_multiplier() -> None:
    envelope = compute_risk_envelope(HISTORICAL_DRAWDOWN_RATE_STRESSED, _inputs())
    assert envelope.gross_multiplier == pytest.approx(0.5)


def test_middle_confidence_sits_strictly_between() -> None:
    envelope = compute_risk_envelope(HISTORICAL_DRAWDOWN_RATE_MIDDLE, _inputs())
    assert 0.5 < envelope.gross_multiplier < 1.5


def test_this_is_the_real_bug_naive_v1_had_at_the_actual_production_range() -> None:
    """The exact real regression this paper (H-MACRO10) exists to fix: at the
    real, calibrated confidence values naive-v1 actually receives in
    production, stressed must never get MORE exposure than calm, and calm
    must never get pinned to the same floor as middle."""
    stressed = compute_risk_envelope(HISTORICAL_DRAWDOWN_RATE_STRESSED, _inputs())
    middle = compute_risk_envelope(HISTORICAL_DRAWDOWN_RATE_MIDDLE, _inputs())
    calm = compute_risk_envelope(HISTORICAL_DRAWDOWN_RATE_CALM, _inputs())
    assert calm.gross_multiplier > middle.gross_multiplier > stressed.gross_multiplier


def test_confidence_outside_the_calibrated_range_is_clamped_not_extrapolated() -> None:
    below = compute_risk_envelope(0.0, _inputs())
    above = compute_risk_envelope(0.9, _inputs())
    assert below.gross_multiplier == pytest.approx(1.5)
    assert above.gross_multiplier == pytest.approx(0.5)


def test_net_equals_gross_in_this_long_only_naive_model() -> None:
    envelope = compute_risk_envelope(HISTORICAL_DRAWDOWN_RATE_MIDDLE, _inputs())
    assert envelope.target_net_exposure == pytest.approx(envelope.target_gross_exposure)
    assert envelope.current_net_exposure == pytest.approx(envelope.current_gross_exposure)


def test_sleeves_group_by_category_with_real_aggregates() -> None:
    envelope = compute_risk_envelope(HISTORICAL_DRAWDOWN_RATE_MIDDLE, _inputs())
    by_category = {sleeve.category: sleeve for sleeve in envelope.sleeves}
    assert set(by_category) == {"broad_equity_etf", "sector_equity_etf", "bond_duration_etf"}
    sector = by_category["sector_equity_etf"]
    assert set(sector.symbols) == {"XLF", "XLK"}
    assert sector.avg_composite_score == pytest.approx((-0.2 + 0.5) / 2)
