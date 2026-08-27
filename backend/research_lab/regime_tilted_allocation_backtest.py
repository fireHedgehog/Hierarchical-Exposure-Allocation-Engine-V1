"""Scratch script for
docs/hypotheses/asset-selection-research/regime-tilted-allocation-backtest.md.

H-SECT04: does a regime-tilted 12-sleeve allocation beat monthly-
rebalanced equal-weight on real out-of-sample Sharpe, without a
materially worse drawdown or turnover -- the actual allocation-level
test H-SECT02/03 only established the underlying correlation for.
Gross returns only, no transaction costs (disclosed gap). Read-only
against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.regime_tilted_allocation_backtest
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, SLEEVES, STRIDE_DAYS, _closes, _macro_composite_series
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE
from backend.engine.regime.scoring_v3 import CALM_TERCILE_CUTOFF, STRESSED_TERCILE_CUTOFF

TILT_UP = 1.5
TILT_DOWN = 0.67
STRESSED_OVERWEIGHT = ["XLU", "XLP"]
STRESSED_UNDERWEIGHT = ["QQQ", "XLY"]
PERIODS_PER_YEAR = 252 / STRIDE_DAYS


def _regime_bucket(composite: float) -> str:
    if composite <= STRESSED_TERCILE_CUTOFF:
        return "stressed"
    if composite >= CALM_TERCILE_CUTOFF:
        return "calm"
    return "neutral"


def _target_weights(bucket: str) -> dict[str, float]:
    base = 1.0 / len(SLEEVES)
    weights = {sleeve: base for sleeve in SLEEVES}
    if bucket == "stressed":
        for sleeve in STRESSED_OVERWEIGHT:
            weights[sleeve] = base * TILT_UP
        for sleeve in STRESSED_UNDERWEIGHT:
            weights[sleeve] = base * TILT_DOWN
    elif bucket == "calm":
        for sleeve in STRESSED_OVERWEIGHT:
            weights[sleeve] = base * TILT_DOWN
        for sleeve in STRESSED_UNDERWEIGHT:
            weights[sleeve] = base * TILT_UP
    total = sum(weights.values())
    return {sleeve: w / total for sleeve, w in weights.items()}


def _equal_weights() -> dict[str, float]:
    base = 1.0 / len(SLEEVES)
    return {sleeve: base for sleeve in SLEEVES}


def _run_backtest(dates: list[str], closes: dict[str, dict[str, float]], composite_series: list[tuple[str, float]], tilted: bool) -> dict:
    rebalance_indices = list(range(0, len(dates) - STRIDE_DAYS, STRIDE_DAYS))
    period_returns: list[float] = []
    turnovers: list[float] = []
    previous_weights: dict[str, float] | None = None

    for i in rebalance_indices:
        anchor_date = dates[i]
        if tilted:
            candidates = [(d, s) for d, s in composite_series if d <= anchor_date]
            bucket = _regime_bucket(max(candidates, key=lambda pair: pair[0])[1]) if candidates else "neutral"
            weights = _target_weights(bucket)
        else:
            weights = _equal_weights()

        if previous_weights is not None:
            turnovers.append(sum(abs(weights[s] - previous_weights[s]) for s in SLEEVES))
        previous_weights = weights

        start_date, end_date = dates[i], dates[i + STRIDE_DAYS]
        period_return = sum(
            weights[sleeve] * (closes[sleeve][end_date] / closes[sleeve][start_date] - 1.0) for sleeve in SLEEVES
        )
        period_returns.append(period_return)

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
        "annualized_vol": stdev_return * (PERIODS_PER_YEAR ** 0.5),
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "total_turnover": sum(turnovers),
        "cumulative_return": cumulative[-1] - 1.0,
    }


def _print_result(label: str, result: dict) -> None:
    print(f"{label}: {result['periods']} periods, ann. return={result['annualized_return']:+.2%}, "
          f"ann. vol={result['annualized_vol']:.2%}, Sharpe={result['sharpe']:.2f}, "
          f"max drawdown={result['max_drawdown']:.2%}, total turnover={result['total_turnover']:.2f}, "
          f"cumulative={result['cumulative_return']:+.1%}")


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

    spy_full = closes[BENCHMARK][common_dates[-1]] / closes[BENCHMARK][common_dates[0]] - 1.0
    print(f"Dataset: {dataset_id}")
    print(f"SPY buy-and-hold, full sample: {spy_full:+.1%} (reference only, not a strategy)\n")

    for label, dates in [
        ("FULL SAMPLE (2004-2026)", common_dates),
        ("IN-SAMPLE (2004-2018)", [d for d in common_dates if d < SPLIT_DATE]),
        ("OUT-OF-SAMPLE (2019-2026)", [d for d in common_dates if d >= SPLIT_DATE]),
    ]:
        print(f"=== {label} ===")
        static_result = _run_backtest(dates, closes, composite_series, tilted=False)
        tilted_result = _run_backtest(dates, closes, composite_series, tilted=True)
        _print_result("Equal-weight (static)", static_result)
        _print_result("Regime-tilted          ", tilted_result)
        sharpe_diff = tilted_result["sharpe"] - static_result["sharpe"]
        print(f"Sharpe difference (tilted - static): {sharpe_diff:+.3f}\n")


if __name__ == "__main__":
    main()
