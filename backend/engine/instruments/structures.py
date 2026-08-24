from __future__ import annotations

from dataclasses import dataclass

from backend.engine.pricing.black_scholes import OptionPricingError, OptionQuote, price_option

# Conviction -> instrument expression, exactly as specified: +/-1..2.4 plain
# equity tilt (handled by the caller, no options), +/-2.5..3.4 credit
# spread, +/-3.5..4.4 debit spread, +/-4.5..5 LEAPS. Naive, fixed-%-OTM
# strikes and fixed day-counts per structure — real Black-Scholes math on
# real inputs, deliberately unoptimized selection rules (see
# docs/engine-milestones.md). NET_DEBIT_CREDIT convention: positive = debit
# paid, negative = credit received.
#
# Registered in the strategies table as `conviction_instrument_selection`
# (naive-v1, verification_status='registered_only').


class InsufficientInstrumentDataError(ValueError):
    """Inputs weren't enough to price a real structure (never fabricated)."""


@dataclass(frozen=True)
class Leg:
    action: str  # 'buy' | 'sell'
    option_type: str  # 'call' | 'put'
    strike: float
    days_to_expiry: int
    quantity: int
    theoretical_price: float
    delta: float
    gamma: float
    theta: float
    vega: float


@dataclass(frozen=True)
class StructureProposal:
    structure_type: str
    side: str  # 'long' | 'short' (directional bias, not a literal short-only position)
    legs: list[Leg]
    net_debit_credit: float  # per share/contract-unit, before quantity; positive = debit
    max_loss: float  # per contract, in dollars (already x100 multiplier)
    max_profit: float | None  # None = theoretically unbounded (long call)
    breakeven: float
    rationale: str


def conviction_from_composite(composite_score: float) -> float:
    """Maps the existing [-1, 1] cross-sectional composite score to this
    desk's [-5, +5] conviction scale."""

    return max(-5.0, min(5.0, composite_score * 5.0))


def _structure_kind(conviction: float) -> str | None:
    magnitude = abs(conviction)
    bullish = conviction > 0
    if magnitude < 2.5:
        return None
    if magnitude < 3.5:
        return "credit_put_spread" if bullish else "credit_call_spread"
    if magnitude < 4.5:
        return "bull_call_spread" if bullish else "bear_put_spread"
    return "leaps_long_call" if bullish else "leaps_long_put"


def _leg(action: str, quote: OptionQuote, quantity: int) -> Leg:
    return Leg(
        action=action,
        option_type=quote.option_type,
        strike=quote.strike,
        days_to_expiry=round(quote.time_to_expiry_years * 365),
        quantity=quantity,
        theoretical_price=quote.theoretical_price,
        delta=quote.delta,
        gamma=quote.gamma,
        theta=quote.theta,
        vega=quote.vega,
    )


def propose_structure(
    *,
    conviction: float,
    spot: float,
    volatility: float,
    risk_free_rate: float,
) -> StructureProposal | None:
    """Returns a real, Black-Scholes-priced structure for |conviction| >= 2.5,
    or None below that threshold (equity-only territory, handled by the
    caller without needing options math at all).
    """

    kind = _structure_kind(conviction)
    if kind is None:
        return None
    try:
        if kind == "credit_put_spread":
            short = price_option(option_type="put", spot=spot, strike=spot * 0.95, time_to_expiry_years=35 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            long = price_option(option_type="put", spot=spot, strike=spot * 0.90, time_to_expiry_years=35 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            net_credit = short.theoretical_price - long.theoretical_price
            max_loss = max(0.0, (short.strike - long.strike) - net_credit) * 100
            return StructureProposal(
                structure_type="credit_put_spread",
                side="long",
                legs=[_leg("sell", short, 1), _leg("buy", long, 1)],
                net_debit_credit=-net_credit,
                max_loss=max_loss,
                max_profit=max(0.0, net_credit) * 100,
                breakeven=short.strike - net_credit,
                rationale=f"Bullish conviction {conviction:+.1f}/5: sell {short.strike:.2f}p / buy {long.strike:.2f}p, 35 DTE, for a net credit.",
            )
        if kind == "credit_call_spread":
            short = price_option(option_type="call", spot=spot, strike=spot * 1.05, time_to_expiry_years=35 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            long = price_option(option_type="call", spot=spot, strike=spot * 1.10, time_to_expiry_years=35 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            net_credit = short.theoretical_price - long.theoretical_price
            max_loss = max(0.0, (long.strike - short.strike) - net_credit) * 100
            return StructureProposal(
                structure_type="credit_call_spread",
                side="short",
                legs=[_leg("sell", short, 1), _leg("buy", long, 1)],
                net_debit_credit=-net_credit,
                max_loss=max_loss,
                max_profit=max(0.0, net_credit) * 100,
                breakeven=short.strike + net_credit,
                rationale=f"Bearish conviction {conviction:+.1f}/5: sell {short.strike:.2f}c / buy {long.strike:.2f}c, 35 DTE, for a net credit.",
            )
        if kind == "bull_call_spread":
            long = price_option(option_type="call", spot=spot, strike=spot * 1.00, time_to_expiry_years=60 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            short = price_option(option_type="call", spot=spot, strike=spot * 1.08, time_to_expiry_years=60 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            net_debit = long.theoretical_price - short.theoretical_price
            max_loss = max(0.0, net_debit) * 100
            return StructureProposal(
                structure_type="bull_call_spread",
                side="long",
                legs=[_leg("buy", long, 1), _leg("sell", short, 1)],
                net_debit_credit=net_debit,
                max_loss=max_loss,
                max_profit=max(0.0, (short.strike - long.strike) - net_debit) * 100,
                breakeven=long.strike + net_debit,
                rationale=f"Bullish conviction {conviction:+.1f}/5: buy {long.strike:.2f}c / sell {short.strike:.2f}c, 60 DTE, for a net debit.",
            )
        if kind == "bear_put_spread":
            long = price_option(option_type="put", spot=spot, strike=spot * 1.00, time_to_expiry_years=60 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            short = price_option(option_type="put", spot=spot, strike=spot * 0.92, time_to_expiry_years=60 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            net_debit = long.theoretical_price - short.theoretical_price
            max_loss = max(0.0, net_debit) * 100
            return StructureProposal(
                structure_type="bear_put_spread",
                side="short",
                legs=[_leg("buy", long, 1), _leg("sell", short, 1)],
                net_debit_credit=net_debit,
                max_loss=max_loss,
                max_profit=max(0.0, (long.strike - short.strike) - net_debit) * 100,
                breakeven=long.strike - net_debit,
                rationale=f"Bearish conviction {conviction:+.1f}/5: buy {long.strike:.2f}p / sell {short.strike:.2f}p, 60 DTE, for a net debit.",
            )
        if kind == "leaps_long_call":
            long = price_option(option_type="call", spot=spot, strike=spot * 1.00, time_to_expiry_years=545 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            return StructureProposal(
                structure_type="leaps_long_call",
                side="long",
                legs=[_leg("buy", long, 1)],
                net_debit_credit=long.theoretical_price,
                max_loss=long.theoretical_price * 100,
                max_profit=None,
                breakeven=long.strike + long.theoretical_price,
                rationale=f"High bullish conviction {conviction:+.1f}/5: buy {long.strike:.2f}c, ~18-month LEAPS.",
            )
        if kind == "leaps_long_put":
            long = price_option(option_type="put", spot=spot, strike=spot * 1.00, time_to_expiry_years=545 / 365, volatility=volatility, risk_free_rate=risk_free_rate)
            return StructureProposal(
                structure_type="leaps_long_put",
                side="short",
                legs=[_leg("buy", long, 1)],
                net_debit_credit=long.theoretical_price,
                max_loss=long.theoretical_price * 100,
                max_profit=max(0.0, long.strike - long.theoretical_price) * 100,
                breakeven=long.strike - long.theoretical_price,
                rationale=f"High bearish conviction {conviction:+.1f}/5: buy {long.strike:.2f}p, ~18-month LEAPS.",
            )
    except OptionPricingError as error:
        raise InsufficientInstrumentDataError(str(error)) from error
    raise AssertionError(f"unreachable structure kind: {kind}")
