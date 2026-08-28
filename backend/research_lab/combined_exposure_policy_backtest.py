"""Scratch script, real checkpoint required before promoting H-TIME02's
price-based exposure policy into production alongside H-MACRO10's live
macro-based one (docs/hypotheses/timing-research/broad-index-exposure-policy.md).

The multiplicative-composition DECISION is already made (independent
state variables, either should be able to dampen exposure on its own).
What's not yet checked: does the COMBINATION actually add value over
either overlay alone, on the same real 12-sleeve book H-MACRO10 was
itself backtested against -- or do macro-stress and SPY-downtrend
states overlap enough that multiplying just produces an over-
conservative, double-counted signal with no real diversification
benefit. Read-only against the sealed dataset, same harness as
exposure_policy_backtest.py (H-MACRO10) for direct comparability.

Run: .venv/bin/python -m backend.research_lab.combined_exposure_policy_backtest
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.research_lab.broad_index_exposure_policy_backtest import (
    EXPOSURE_TABLE,
    VOL_ELEVATED_PCT,
    VOL_HISTORY,
    VOL_WINDOW,
    _daily_returns,
    _trailing_vol_series,
)
from backend.research_lab.exposure_policy_backtest import _confidence_for, _multiplier_v2, _print_result
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, SLEEVES, STRIDE_DAYS, _closes, _macro_composite_series
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE

PERIODS_PER_YEAR = 252 / STRIDE_DAYS
PRICE_MA_LENGTH = 200  # same mid-parameter choice used for H-TIME02's crisis-window table


def _price_multiplier_series(spy_dates: list[str], spy_closes_ordered: list[float]) -> dict[str, float]:
    """SPY's own trend+vol exposure multiplier, indexed by date -- the same
    EXPOSURE_TABLE H-TIME02 backtested, just exposed as a date-keyed lookup
    for this monthly-strided harness instead of H-TIME02's daily rebalance."""
    returns = _daily_returns(spy_closes_ordered)
    vol_series = _trailing_vol_series(returns)
    out: dict[str, float] = {}
    for i in range(len(returns)):
        price_idx = i + 1
        if price_idx < PRICE_MA_LENGTH or vol_series[i] is None:
            continue
        ma = sum(spy_closes_ordered[price_idx - PRICE_MA_LENGTH + 1 : price_idx + 1]) / PRICE_MA_LENGTH
        trend = "above" if spy_closes_ordered[price_idx] > ma else "below"
        history_start = max(0, i - VOL_HISTORY + 1)
        history = [v for v in vol_series[history_start : i + 1] if v is not None]
        if len(history) < VOL_WINDOW:
            continue
        sorted_history = sorted(history)
        rank = sum(1 for v in sorted_history if v <= vol_series[i]) / len(sorted_history)
        vol_state = "elevated" if rank >= VOL_ELEVATED_PCT else "calm"
        out[spy_dates[price_idx]] = EXPOSURE_TABLE[(trend, vol_state)]
    return out


def _run_backtest(dates: list[str], closes: dict[str, dict[str, float]], composite_series: list[tuple[str, float]],
                   price_multipliers: dict[str, float], use_macro: bool, use_price: bool, combine: str = "multiply") -> dict:
    period_returns: list[float] = []
    multiplier_changes: list[float] = []
    previous_multiplier: float | None = None

    for i in range(0, len(dates) - STRIDE_DAYS, STRIDE_DAYS):
        anchor_date = dates[i]
        macro_mult = 1.0
        if use_macro:
            candidates = [(d, s) for d, s in composite_series if d <= anchor_date]
            composite = max(candidates, key=lambda pair: pair[0])[1] if candidates else 0.0
            macro_mult = _multiplier_v2(_confidence_for(composite))
        price_mult = 1.0
        if use_price:
            price_dates = [d for d in price_multipliers if d <= anchor_date]
            price_mult = price_multipliers[max(price_dates)] if price_dates else 1.0
        multiplier = min(macro_mult, price_mult) if combine == "min" else macro_mult * price_mult

        if previous_multiplier is not None:
            multiplier_changes.append(abs(multiplier - previous_multiplier))
        previous_multiplier = multiplier

        start_date, end_date = dates[i], dates[i + STRIDE_DAYS]
        mean_sleeve_return = statistics.fmean(
            closes[sleeve][end_date] / closes[sleeve][start_date] - 1.0 for sleeve in SLEEVES
        )
        period_returns.append(multiplier * mean_sleeve_return)

    cumulative = [1.0]
    for r in period_returns:
        cumulative.append(cumulative[-1] * (1.0 + r))
    peak = cumulative[0]
    max_drawdown = 0.0
    for value in cumulative:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, (value - peak) / peak)

    mean_return = statistics.fmean(period_returns)
    stdev_return = statistics.pstdev(period_returns)
    sharpe = (mean_return / stdev_return) * (PERIODS_PER_YEAR ** 0.5) if stdev_return > 1e-9 else float("nan")
    annualized_return = (cumulative[-1] ** (PERIODS_PER_YEAR / len(period_returns))) - 1.0

    return {
        "periods": len(period_returns),
        "annualized_return": annualized_return,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "total_multiplier_turnover": sum(multiplier_changes),
        "cumulative_return": cumulative[-1] - 1.0,
    }


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    all_symbols = [BENCHMARK] + SLEEVES
    closes = {symbol: _closes(connection, dataset_id, symbol) for symbol in all_symbols}
    common_dates = sorted(set.intersection(*(set(c) for c in closes.values())))
    composite_series = _macro_composite_series(connection, dataset_id)

    spy_dates = sorted(closes[BENCHMARK])
    spy_closes_ordered = [closes[BENCHMARK][d] for d in spy_dates]
    price_multipliers = _price_multiplier_series(spy_dates, spy_closes_ordered)

    print(f"Dataset: {dataset_id}\n")

    rules = [
        ("Static 1.0x", False, False, "multiply"),
        ("Macro only (naive-v2)", True, False, "multiply"),
        ("Price only (H-TIME02, MA=200)", False, True, "multiply"),
        ("Combined, multiply", True, True, "multiply"),
        ("Combined, min()", True, True, "min"),
    ]

    for label, dates in [
        ("FULL SAMPLE (2004-2026)", common_dates),
        ("IN-SAMPLE (2004-2018)", [d for d in common_dates if d < SPLIT_DATE]),
        ("OUT-OF-SAMPLE (2019-2026)", [d for d in common_dates if d >= SPLIT_DATE]),
    ]:
        print(f"=== {label} ===")
        for rule_label, use_macro, use_price, combine in rules:
            result = _run_backtest(dates, closes, composite_series, price_multipliers, use_macro, use_price, combine)
            _print_result(rule_label, result)
        print()


if __name__ == "__main__":
    main()
