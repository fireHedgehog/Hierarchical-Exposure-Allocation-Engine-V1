from __future__ import annotations

import pytest

from backend.engine.instruments.sizing import position_size
from backend.engine.instruments.structures import conviction_from_composite, propose_structure

# Test-only literals standing in for the database-seeded staging_budget_config
# row (backend/schema.sql) — position_size() takes these as required
# parameters rather than a module constant, precisely so no caller can
# silently fall back to a hidden hardcoded default.
NOTIONAL_BUDGET = 1_000_000.0
RISK_PER_POSITION_FRACTION = 0.02


def test_conviction_scales_composite_score_to_five_and_clamps() -> None:
    assert conviction_from_composite(0.0) == 0.0
    assert conviction_from_composite(1.0) == 5.0
    assert conviction_from_composite(-1.0) == -5.0
    assert conviction_from_composite(0.5) == pytest.approx(2.5)
    assert conviction_from_composite(2.0) == 5.0  # out-of-range input still clamps, never overshoots


@pytest.mark.parametrize(
    "conviction,expected_type,expected_side",
    [
        (2.7, "credit_put_spread", "long"),
        (4.0, "bull_call_spread", "long"),
        (4.8, "leaps_long_call", "long"),
        (-2.7, "credit_call_spread", "short"),
        (-4.0, "bear_put_spread", "short"),
        (-4.8, "leaps_long_put", "short"),
    ],
)
def test_conviction_thresholds_select_the_right_structure(conviction: float, expected_type: str, expected_side: str) -> None:
    proposal = propose_structure(conviction=conviction, spot=100.0, volatility=0.25, risk_free_rate=0.04)
    assert proposal is not None
    assert proposal.structure_type == expected_type
    assert proposal.side == expected_side


def test_below_threshold_returns_none_for_equity_only_handling() -> None:
    assert propose_structure(conviction=1.5, spot=100.0, volatility=0.25, risk_free_rate=0.04) is None
    assert propose_structure(conviction=-1.5, spot=100.0, volatility=0.25, risk_free_rate=0.04) is None
    assert propose_structure(conviction=0.3, spot=100.0, volatility=0.25, risk_free_rate=0.04) is None


def test_every_structure_has_real_priced_legs_and_bounded_max_loss() -> None:
    for conviction in (2.6, 3.6, 4.6, -2.6, -3.6, -4.6):
        proposal = propose_structure(conviction=conviction, spot=250.0, volatility=0.3, risk_free_rate=0.04)
        assert proposal is not None
        assert proposal.legs
        assert proposal.max_loss >= 0.0
        for leg in proposal.legs:
            assert leg.theoretical_price >= 0.0
            assert leg.strike > 0.0
            assert leg.days_to_expiry > 0


def test_credit_spread_max_loss_is_strike_width_minus_credit() -> None:
    proposal = propose_structure(conviction=3.0, spot=100.0, volatility=0.25, risk_free_rate=0.04)
    assert proposal is not None
    strike_width = abs(proposal.legs[0].strike - proposal.legs[1].strike)
    net_credit = -proposal.net_debit_credit
    assert proposal.max_loss == pytest.approx((strike_width - net_credit) * 100, abs=1e-6)
    assert proposal.max_profit == pytest.approx(net_credit * 100, abs=1e-6)


def test_leaps_long_call_has_unbounded_max_profit_and_bounded_loss() -> None:
    proposal = propose_structure(conviction=5.0, spot=100.0, volatility=0.3, risk_free_rate=0.04)
    assert proposal is not None
    assert proposal.max_profit is None
    assert proposal.max_loss == pytest.approx(proposal.legs[0].theoretical_price * 100, abs=1e-6)


def test_position_size_scales_with_conviction_and_never_exceeds_risk_cap() -> None:
    quantity_low, risk_low = position_size(
        conviction=2.5, max_loss_per_unit=500.0,
        notional_budget=NOTIONAL_BUDGET, risk_per_position_fraction=RISK_PER_POSITION_FRACTION,
    )
    quantity_high, risk_high = position_size(
        conviction=5.0, max_loss_per_unit=500.0,
        notional_budget=NOTIONAL_BUDGET, risk_per_position_fraction=RISK_PER_POSITION_FRACTION,
    )
    assert risk_high > risk_low
    assert risk_high <= NOTIONAL_BUDGET * RISK_PER_POSITION_FRACTION + 1e-6
    assert quantity_low * 500.0 <= risk_low + 1e-6
    assert quantity_high * 500.0 <= NOTIONAL_BUDGET * RISK_PER_POSITION_FRACTION + 1e-6


def test_position_size_returns_zero_when_max_loss_dwarfs_risk_budget() -> None:
    quantity, risk = position_size(
        conviction=1.0, max_loss_per_unit=NOTIONAL_BUDGET,
        notional_budget=NOTIONAL_BUDGET, risk_per_position_fraction=RISK_PER_POSITION_FRACTION,
    )
    assert quantity == 0
    assert risk == 0.0
