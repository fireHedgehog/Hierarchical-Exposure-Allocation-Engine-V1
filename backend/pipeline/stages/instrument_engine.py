from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

from backend.engine.instruments import (
    InsufficientInstrumentDataError,
    conviction_from_composite,
    position_size,
    propose_structure,
)
from backend.engine.pricing.black_scholes import OptionPricingError, realized_volatility
from backend.pipeline.stages.common import StageOutcome, _iso_z

# Conviction -1..+5 -> instrument expression, as specified: |1.0-2.4| plain
# equity tilt (already priced for real by factor_engine — reused here, not
# recomputed), |2.5-3.4| credit spread, |3.5-4.4| debit spread, |4.5-5.0|
# LEAPS. Every strike/premium/greek is real Black-Scholes math over a real
# spot price and a real realized-volatility estimate — but realized
# volatility is NOT market-implied volatility, and there is no real
# bid/ask/open-interest, because no options-chain data source exists yet.
# That gap is recorded honestly via market_data_complete=0 and a required,
# unresolved position_blocker on every options candidate — this project's
# own readiness gates already key off exactly those fields, so an options
# candidate here correctly still fails "options_expression" readiness
# despite being a real, computed number.


def run_instrument_engine_stage(
    connection: sqlite3.Connection,
    now: datetime,
    dataset_snapshot_id: str | None,
    desk_snapshot_id: str | None,
) -> StageOutcome:
    if not dataset_snapshot_id or not desk_snapshot_id:
        return StageOutcome(
            status="blocked",
            message="No dataset or open desk snapshot is available for instrument expression.",
            error_code="no_snapshot_to_express",
        )
    desk = connection.execute(
        "SELECT id FROM desk_snapshots WHERE id = ? AND immutable = 0",
        (desk_snapshot_id,),
    ).fetchone()
    if desk is None:
        return StageOutcome(
            status="blocked",
            message="The desk snapshot from regime_filter/allocation_engine is missing or already sealed.",
            error_code="desk_not_open",
            dataset_snapshot_id=dataset_snapshot_id,
            desk_snapshot_id=desk_snapshot_id,
        )

    budget_row = connection.execute(
        "SELECT notional_budget, risk_per_position_fraction FROM staging_budget_config WHERE id = 1"
    ).fetchone()
    if budget_row is None:
        return StageOutcome(
            status="failed",
            message="No staging_budget_config row is seeded; cannot size any position.",
            error_code="budget_config_missing",
            dataset_snapshot_id=dataset_snapshot_id,
            desk_snapshot_id=desk_snapshot_id,
        )
    notional_budget = budget_row["notional_budget"]
    risk_per_position_fraction = budget_row["risk_per_position_fraction"]

    rate_row = connection.execute(
        """
        SELECT value FROM fred_observations
        WHERE dataset_snapshot_id = ? AND series_id = 'DGS10' AND value IS NOT NULL
        ORDER BY observation_date DESC LIMIT 1
        """,
        (dataset_snapshot_id,),
    ).fetchone()
    if rate_row is None:
        return StageOutcome(
            status="failed",
            message="No real DGS10 rate is available on this dataset to price options.",
            error_code="rate_missing",
            dataset_snapshot_id=dataset_snapshot_id,
            desk_snapshot_id=desk_snapshot_id,
        )
    risk_free_rate = rate_row["value"] / 100.0

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols WHERE active = 1 AND category != 'macro_series'"
    ).fetchall()
    category_by_symbol = {row["symbol"]: row["category"] for row in staging_rows}

    rows = connection.execute(
        """
        SELECT csr.symbol, csr.composite_score, sy.last_price, sy.security_id
        FROM cross_section_rows AS csr
        JOIN symbols AS sy ON sy.snapshot_id = csr.snapshot_id AND sy.symbol = csr.symbol
        WHERE csr.snapshot_id = ?
        """,
        (desk_snapshot_id,),
    ).fetchall()
    recommendation_by_symbol = {
        row["symbol"]: row
        for row in connection.execute(
            "SELECT symbol, target_weight, current_weight, delta_weight, confidence FROM symbol_recommendations WHERE snapshot_id = ?",
            (desk_snapshot_id,),
        ).fetchall()
    }

    timestamp = _iso_z(now)
    candidate_rows: list[tuple[Any, ...]] = []
    leg_rows: list[tuple[Any, ...]] = []
    greek_rows: list[tuple[Any, ...]] = []
    point_rows: list[tuple[Any, ...]] = []
    blocker_rows: list[tuple[Any, ...]] = []
    sort_order = 0
    options_priced = 0
    equity_only = 0

    for row in rows:
        symbol = row["symbol"]
        category = category_by_symbol.get(symbol)
        if category is None or category == "crypto_reference":
            continue  # BTC-USD stays research-only — never a position candidate, per roadmap.md
        conviction = conviction_from_composite(row["composite_score"])
        if abs(conviction) < 1.0:
            continue  # neutral: no expression proposed

        sort_order += 1
        candidate_id = f"instrument-{symbol.lower()}"
        recommendation = recommendation_by_symbol.get(symbol)

        if abs(conviction) < 2.5:
            # Plain equity tilt — already real (factor_engine's own weight
            # calc), reused rather than recomputed.
            if recommendation is None:
                sort_order -= 1
                continue
            equity_only += 1
            side = "long" if conviction > 0 else "short"
            target_weight = recommendation["target_weight"]
            shares = int((target_weight * notional_budget) // max(row["last_price"], 0.01))
            candidate_rows.append(
                (
                    desk_snapshot_id, candidate_id, symbol, f"{symbol} equity tilt", side, "equity",
                    target_weight, recommendation["current_weight"], recommendation["delta_weight"],
                    "portfolio_weight", recommendation["confidence"], target_weight * notional_budget, None,
                    None, None, None, shares * row["last_price"], "usd", "ongoing", "proposed",
                    "research_only_no_execution", 1, "live_market_data", "engine_factor_tilt",
                    timestamp, timestamp, timestamp, sort_order,
                )
            )
            leg_rows.append(
                (
                    desk_snapshot_id, candidate_id, 1, "buy" if side == "long" else "sell", shares, "equity",
                    symbol, None, None, None, None, None, row["last_price"], 1.0, None, None, None, None,
                    1.0 if side == "long" else -1.0, None, None, None,
                )
            )
            point_rows.append((desk_snapshot_id, candidate_id, "rationale", f"Conviction {conviction:+.1f}/5 (cross-sectional composite {row['composite_score']:+.2f}) stays below the 2.5 options threshold — expressed as a plain equity tilt.", 1))
            point_rows.append((desk_snapshot_id, candidate_id, "risk", f"Naive worst case treats the full {target_weight*notional_budget:,.0f} notional as at risk (no defined-risk structure at this conviction level).", 1))
            continue

        # Options territory: real Black-Scholes pricing from real spot +
        # real realized volatility (not market-implied — no chain data
        # source exists yet, made explicit via market_data_complete=0 below).
        bar_rows = connection.execute(
            "SELECT close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? ORDER BY time",
            (dataset_snapshot_id, row["security_id"]),
        ).fetchall()
        closes = [bar["close"] for bar in bar_rows if bar["close"] is not None]
        try:
            volatility = realized_volatility(closes, window=60)
            if volatility <= 0:
                raise OptionPricingError("zero realized volatility.")
            proposal = propose_structure(
                conviction=conviction, spot=row["last_price"], volatility=volatility, risk_free_rate=risk_free_rate
            )
        except (OptionPricingError, InsufficientInstrumentDataError):
            sort_order -= 1
            continue
        if proposal is None:
            sort_order -= 1
            continue
        options_priced += 1

        quantity, _risk_dollars = position_size(
            conviction=conviction,
            max_loss_per_unit=proposal.max_loss,
            notional_budget=notional_budget,
            risk_per_position_fraction=risk_per_position_fraction,
        )
        display_quantity = quantity if quantity > 0 else 1
        total_max_loss = proposal.max_loss * display_quantity
        total_max_profit = proposal.max_profit * display_quantity if proposal.max_profit is not None else None
        total_net_debit_credit = proposal.net_debit_credit * 100 * display_quantity
        target_weight = (total_max_loss / notional_budget) if quantity > 0 else 0.0

        candidate_rows.append(
            (
                desk_snapshot_id, candidate_id, symbol, f"{symbol} {proposal.structure_type.replace('_', ' ')}",
                proposal.side, proposal.structure_type, target_weight, 0.0, target_weight, "risk_budget",
                max(0.1, min(0.95, 0.5 + abs(conviction) / 10.0)), total_max_loss, total_max_profit,
                proposal.breakeven, proposal.breakeven, total_net_debit_credit, abs(total_net_debit_credit),
                "usd", f"{max(leg.days_to_expiry for leg in proposal.legs)}d", "proposed",
                "blocked", 0, "other", "engine_black_scholes", timestamp, timestamp, timestamp, sort_order,
            )
        )
        for leg_order, leg in enumerate(proposal.legs, 1):
            expiry = (now.date() + timedelta(days=leg.days_to_expiry)).isoformat()
            leg_rows.append(
                (
                    desk_snapshot_id, candidate_id, leg_order, leg.action, display_quantity, "option", symbol,
                    expiry, leg.strike, leg.option_type, None, None, leg.theoretical_price, 100.0,
                    leg.days_to_expiry, None, None, volatility, leg.delta, leg.gamma, leg.theta, leg.vega,
                )
            )
        sign = lambda leg: 1.0 if leg.action == "buy" else -1.0  # noqa: E731
        for greek_key, unit, values in (
            ("delta", "per_$1_underlying", [sign(leg) * leg.delta for leg in proposal.legs]),
            ("gamma", "per_$1_underlying_squared", [sign(leg) * leg.gamma for leg in proposal.legs]),
            ("theta", "per_day", [sign(leg) * leg.theta for leg in proposal.legs]),
            ("vega", "per_1pt_vol", [sign(leg) * leg.vega for leg in proposal.legs]),
        ):
            greek_rows.append((desk_snapshot_id, candidate_id, greek_key, sum(values), unit))

        point_rows.append((desk_snapshot_id, candidate_id, "rationale", proposal.rationale, 1))
        point_rows.append((desk_snapshot_id, candidate_id, "rationale", f"Realized 60-day volatility {volatility:.0%} (annualized) and the real 10-year Treasury rate {risk_free_rate:.2%} were used as the Black-Scholes inputs.", 2))
        point_rows.append((desk_snapshot_id, candidate_id, "risk", f"Maximum loss ${total_max_loss:,.0f} across {display_quantity} contract(s), sized to {risk_per_position_fraction * 100 * abs(conviction) / 5:.1f}% of the ${notional_budget:,.0f} staging budget.", 1))

        blocker_rows.append(
            (
                desk_snapshot_id, candidate_id, "theoretical_pricing_only", "Theoretical pricing only",
                "Black-Scholes price from realized (not market-implied) volatility; no real options-chain bid/ask/open-interest exists yet. Not executable.",
                1, 0, 1,
            )
        )
        if quantity == 0:
            blocker_rows.append(
                (
                    desk_snapshot_id, candidate_id, "position_sizing_rounds_to_zero", "Position sizing rounds to zero",
                    f"The {risk_per_position_fraction:.0%}-of-budget risk cap at this conviction rounds to 0 contracts for a ${proposal.max_loss:,.0f} max-loss structure; shown as a 1-contract reference.",
                    1, 0, 2,
                )
            )

    connection.executemany(
        """
        INSERT INTO position_candidates (
            snapshot_id, candidate_id, symbol, name, side, structure_type, target_weight,
            current_weight, delta_weight, allocation_basis, confidence, max_loss, max_profit,
            breakeven_low, breakeven_high, net_debit_credit, cost_estimate, cost_unit, horizon,
            status, actionability, market_data_complete, input_completeness_scope, source_key,
            observed_at, available_at, ingested_at, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        candidate_rows,
    )
    if leg_rows:
        connection.executemany(
            """
            INSERT INTO position_legs (
                snapshot_id, candidate_id, leg_order, action, quantity, instrument_type, symbol,
                expiry, strike, option_type, bid, ask, mid, multiplier, dte, open_interest, volume,
                implied_volatility, delta, gamma, theta, vega
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            leg_rows,
        )
    if greek_rows:
        connection.executemany(
            "INSERT INTO position_greeks (snapshot_id, candidate_id, greek_key, value, unit) VALUES (?, ?, ?, ?, ?)",
            greek_rows,
        )
    if point_rows:
        connection.executemany(
            "INSERT INTO position_points (snapshot_id, candidate_id, point_type, text, sort_order) VALUES (?, ?, ?, ?, ?)",
            point_rows,
        )
    if blocker_rows:
        connection.executemany(
            """
            INSERT INTO position_blockers (snapshot_id, candidate_id, blocker_key, label, detail, required, resolved, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            blocker_rows,
        )

    written = len(candidate_rows) + len(leg_rows) + len(greek_rows) + len(point_rows) + len(blocker_rows)
    return StageOutcome(
        status="completed",
        message=(
            f"Proposed {len(candidate_rows)} position candidates ({equity_only} equity tilts, "
            f"{options_priced} real Black-Scholes-priced option structures); every option candidate "
            "carries a required, unresolved theoretical-pricing blocker."
        ),
        records_read=len(rows),
        records_written=written,
        dataset_snapshot_id=dataset_snapshot_id,
        desk_snapshot_id=desk_snapshot_id,
    )
