from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.engine.factors import (
    Bar,
    InsufficientPriceDataError,
    compute_cross_section,
    suggested_weight,
)


def _trending_bars(start_price: float, daily_drift: float, count: int = 200, start: date = date(2026, 1, 1)) -> list[Bar]:
    price = start_price
    bars = []
    for offset in range(count):
        bars.append(Bar(time=(start + timedelta(days=offset)).isoformat(), close=price))
        price = price * (1 + daily_drift)
    return bars


def test_every_output_traces_to_real_bars() -> None:
    universe = {
        "UP": _trending_bars(100.0, 0.002),
        "DOWN": _trending_bars(100.0, -0.002),
        "FLAT": _trending_bars(100.0, 0.0),
    }
    ranked = compute_cross_section(universe)
    assert {item.symbol for item in ranked} == {"UP", "DOWN", "FLAT"}
    for item in ranked:
        assert -1.0 <= item.composite_score <= 1.0
        assert 0.0 <= item.strength <= 1.0
        assert item.returns  # every symbol carries its underlying horizon returns as evidence


def test_ranking_is_relative_not_absolute() -> None:
    """The same UP series scores differently depending on its peers — this is
    cross-sectional discovery, not an absolute threshold."""

    up = _trending_bars(100.0, 0.002)
    down = _trending_bars(100.0, -0.002)
    flat = _trending_bars(100.0, 0.0)

    against_weak_peers = compute_cross_section({"UP": up, "DOWN": down, "DOWN2": down})
    against_strong_peers = compute_cross_section({"UP": up, "UP2": up, "UP3": up})

    up_vs_weak = next(item for item in against_weak_peers if item.symbol == "UP")
    up_vs_strong = next(item for item in against_strong_peers if item.symbol == "UP")
    assert up_vs_weak.rank == 1
    assert up_vs_weak.composite_score > 0
    # Tied with identical peers, z-score collapses to 0 — genuinely neutral among equals.
    assert up_vs_strong.composite_score == pytest.approx(0.0, abs=1e-9)

    ranked = compute_cross_section({"UP": up, "DOWN": down, "FLAT": flat})
    by_symbol = {item.symbol: item for item in ranked}
    assert by_symbol["UP"].rank < by_symbol["FLAT"].rank < by_symbol["DOWN"].rank
    assert by_symbol["UP"].direction == "bullish"
    assert by_symbol["DOWN"].direction == "bearish"


def test_thin_symbol_is_excluded_not_fatal() -> None:
    universe = {
        "ENOUGH": _trending_bars(100.0, 0.001, count=200),
        "THIN": _trending_bars(100.0, 0.001, count=5),
    }
    ranked = compute_cross_section(universe)
    assert {item.symbol for item in ranked} == {"ENOUGH"}


def test_all_symbols_thin_raises_instead_of_fabricating() -> None:
    universe = {"THIN": _trending_bars(100.0, 0.001, count=5)}
    with pytest.raises(InsufficientPriceDataError):
        compute_cross_section(universe)


def test_suggested_weight_neutral_score_returns_baseline() -> None:
    assert suggested_weight(0.0, base_weight=0.05) == pytest.approx(0.05)


def test_suggested_weight_tilts_and_clamps() -> None:
    base = 0.05
    assert suggested_weight(1.0, base_weight=base) == pytest.approx(base * 2.0)
    assert suggested_weight(-1.0, base_weight=base) == pytest.approx(base * 0.2)
    # Even an out-of-range score can't blow past the clamp bounds.
    assert suggested_weight(5.0, base_weight=base) == pytest.approx(base * 2.0)
    assert suggested_weight(-5.0, base_weight=base) == pytest.approx(base * 0.2)
