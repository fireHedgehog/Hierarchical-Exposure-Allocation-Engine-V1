from __future__ import annotations

import math

import pytest

from backend.engine.pricing.black_scholes import OptionPricingError, price_option, realized_volatility


def test_put_call_parity_holds() -> None:
    """C - P = S - K*e^(-rT) — the textbook identity any correct BS
    implementation must satisfy exactly."""

    call = price_option(option_type="call", spot=100.0, strike=105.0, time_to_expiry_years=0.5, volatility=0.25, risk_free_rate=0.04)
    put = price_option(option_type="put", spot=100.0, strike=105.0, time_to_expiry_years=0.5, volatility=0.25, risk_free_rate=0.04)
    lhs = call.theoretical_price - put.theoretical_price
    rhs = 100.0 - 105.0 * math.exp(-0.04 * 0.5)
    assert lhs == pytest.approx(rhs, abs=1e-9)


def test_call_delta_in_zero_one_and_put_delta_in_minus_one_zero() -> None:
    call = price_option(option_type="call", spot=100.0, strike=100.0, time_to_expiry_years=1.0, volatility=0.3, risk_free_rate=0.03)
    put = price_option(option_type="put", spot=100.0, strike=100.0, time_to_expiry_years=1.0, volatility=0.3, risk_free_rate=0.03)
    assert 0.0 < call.delta < 1.0
    assert -1.0 < put.delta < 0.0
    assert call.delta - put.delta == pytest.approx(1.0, abs=1e-9)


def test_deep_itm_call_delta_approaches_one() -> None:
    call = price_option(option_type="call", spot=200.0, strike=50.0, time_to_expiry_years=0.1, volatility=0.2, risk_free_rate=0.03)
    assert call.delta > 0.99


def test_deep_otm_call_is_worth_close_to_zero() -> None:
    call = price_option(option_type="call", spot=50.0, strike=500.0, time_to_expiry_years=0.05, volatility=0.2, risk_free_rate=0.03)
    assert call.theoretical_price == pytest.approx(0.0, abs=0.01)


def test_more_time_or_more_volatility_never_decreases_price() -> None:
    base = price_option(option_type="call", spot=100.0, strike=100.0, time_to_expiry_years=0.25, volatility=0.2, risk_free_rate=0.03)
    more_time = price_option(option_type="call", spot=100.0, strike=100.0, time_to_expiry_years=1.0, volatility=0.2, risk_free_rate=0.03)
    more_vol = price_option(option_type="call", spot=100.0, strike=100.0, time_to_expiry_years=0.25, volatility=0.5, risk_free_rate=0.03)
    assert more_time.theoretical_price > base.theoretical_price
    assert more_vol.theoretical_price > base.theoretical_price


def test_invalid_inputs_raise_instead_of_fabricating() -> None:
    with pytest.raises(OptionPricingError):
        price_option(option_type="call", spot=0.0, strike=100.0, time_to_expiry_years=0.5, volatility=0.2, risk_free_rate=0.03)
    with pytest.raises(OptionPricingError):
        price_option(option_type="call", spot=100.0, strike=100.0, time_to_expiry_years=0.5, volatility=0.0, risk_free_rate=0.03)
    with pytest.raises(OptionPricingError):
        price_option(option_type="straddle", spot=100.0, strike=100.0, time_to_expiry_years=0.5, volatility=0.2, risk_free_rate=0.03)  # type: ignore[arg-type]


def test_realized_volatility_is_zero_for_flat_prices_and_positive_for_noisy_ones() -> None:
    # A perfectly flat series has zero variance in log returns — a valid,
    # if degenerate, real computation (not an error).
    flat = [100.0] * 90
    assert realized_volatility(flat) == pytest.approx(0.0, abs=1e-9)

    noisy = [100.0]
    for i in range(90):
        noisy.append(noisy[-1] * (1 + (0.02 if i % 2 == 0 else -0.018)))
    vol = realized_volatility(noisy)
    assert vol > 0.1  # a real, meaningfully positive annualized vol for this swingy series
