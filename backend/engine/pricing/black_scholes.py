from __future__ import annotations

import math
from dataclasses import dataclass

# Real options math (textbook Black-Scholes-Merton, no dividend yield),
# deliberately used INSTEAD OF fabricating strikes/premiums. No free
# options-chain data source exists (see docs/engine-milestones.md), so this
# project has no market-implied volatility or live quotes to work with yet.
# What it DOES have, for real: the underlying's actual traded price and its
# actual historical return series. Black-Scholes fed by realized (not
# implied) volatility is a well-known, honest simplification — the price it
# produces is a theoretical estimate, not a tradeable quote, and every
# caller must label it that way.


class OptionPricingError(ValueError):
    """Inputs were not economically valid (non-positive price/vol/time)."""


@dataclass(frozen=True)
class OptionQuote:
    option_type: str  # 'call' | 'put'
    strike: float
    time_to_expiry_years: float
    theoretical_price: float
    delta: float
    gamma: float
    theta: float  # per calendar day
    vega: float  # per 1 percentage point (0.01) change in volatility


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def price_option(
    *,
    option_type: str,
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    volatility: float,
    risk_free_rate: float,
) -> OptionQuote:
    if spot <= 0 or strike <= 0 or time_to_expiry_years <= 0 or volatility <= 0:
        raise OptionPricingError(
            "spot, strike, volatility, and time to expiry must all be positive "
            f"(got spot={spot}, strike={strike}, t={time_to_expiry_years}, vol={volatility})."
        )
    if option_type not in ("call", "put"):
        raise OptionPricingError(f"option_type must be 'call' or 'put', got {option_type!r}.")

    sqrt_t = math.sqrt(time_to_expiry_years)
    d1 = (
        math.log(spot / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry_years
    ) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    discount = math.exp(-risk_free_rate * time_to_expiry_years)

    if option_type == "call":
        price = spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        theta_annual = -(spot * _norm_pdf(d1) * volatility) / (2 * sqrt_t) - risk_free_rate * strike * discount * _norm_cdf(d2)
    else:
        price = strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1.0
        theta_annual = -(spot * _norm_pdf(d1) * volatility) / (2 * sqrt_t) + risk_free_rate * strike * discount * _norm_cdf(-d2)

    gamma = _norm_pdf(d1) / (spot * volatility * sqrt_t)
    vega_per_unit_vol = spot * _norm_pdf(d1) * sqrt_t

    return OptionQuote(
        option_type=option_type,
        strike=strike,
        time_to_expiry_years=time_to_expiry_years,
        theoretical_price=max(price, 0.0),
        delta=delta,
        gamma=gamma,
        theta=theta_annual / 365.0,
        vega=vega_per_unit_vol / 100.0,
    )


def realized_volatility(closes: list[float], *, window: int = 60, trading_days_per_year: int = 252) -> float:
    """Annualized realized volatility from daily log returns over the
    trailing `window` bars — a real, computable proxy for implied
    volatility, explicitly NOT the same as market-implied volatility."""

    if len(closes) < 2:
        raise OptionPricingError("need at least 2 closes to compute a return.")
    tail = closes[-(window + 1):] if len(closes) > window else closes
    log_returns = [
        math.log(tail[i] / tail[i - 1]) for i in range(1, len(tail)) if tail[i - 1] > 0 and tail[i] > 0
    ]
    if len(log_returns) < 2:
        raise OptionPricingError("not enough valid daily returns to compute volatility.")
    mean = sum(log_returns) / len(log_returns)
    variance = sum((value - mean) ** 2 for value in log_returns) / (len(log_returns) - 1)
    daily_vol = math.sqrt(variance)
    return daily_vol * math.sqrt(trading_days_per_year)
