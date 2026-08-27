"""Scratch script for
docs/hypotheses/macro-research/exposure-policy-calibration.md (H-MACRO10).

Real checkpoint: does either gross-exposure scaling rule (naive-v1, the
real directional bug; naive-v2, the fix) beat static 1.0x exposure on
real OOS Sharpe/drawdown, applied to the same 12-sleeve equal-weight
book H-SECT04 already used. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.exposure_policy_backtest
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.engine.regime.scoring_v3 import (
    CALM_TERCILE_CUTOFF,
    HISTORICAL_DRAWDOWN_RATE_CALM,
    HISTORICAL_DRAWDOWN_RATE_MIDDLE,
    HISTORICAL_DRAWDOWN_RATE_STRESSED,
    STRESSED_TERCILE_CUTOFF,
)
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, SLEEVES, STRIDE_DAYS, _closes, _macro_composite_series
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE

PERIODS_PER_YEAR = 252 / STRIDE_DAYS
MIN_MULTIPLIER, MAX_MULTIPLIER = 0.5, 1.5


def _confidence_for(composite: float) -> float:
    if composite <= STRESSED_TERCILE_CUTOFF:
        return HISTORICAL_DRAWDOWN_RATE_STRESSED
    if composite >= CALM_TERCILE_CUTOFF:
        return HISTORICAL_DRAWDOWN_RATE_CALM
    return HISTORICAL_DRAWDOWN_RATE_MIDDLE


def _multiplier_v1(confidence: float) -> float:
    return max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, confidence * 2.0))


def _multiplier_v2(confidence: float) -> float:
    clamped = max(HISTORICAL_DRAWDOWN_RATE_CALM, min(HISTORICAL_DRAWDOWN_RATE_STRESSED, confidence))
    span = HISTORICAL_DRAWDOWN_RATE_STRESSED - HISTORICAL_DRAWDOWN_RATE_CALM
    fraction = (clamped - HISTORICAL_DRAWDOWN_RATE_CALM) / span
    return MAX_MULTIPLIER - fraction * (MAX_MULTIPLIER - MIN_MULTIPLIER)


def _run_backtest(dates: list[str], closes: dict[str, dict[str, float]], composite_series: list[tuple[str, float]], rule) -> dict:
    period_returns: list[float] = []
    multiplier_changes: list[float] = []
    previous_multiplier: float | None = None

    for i in range(0, len(dates) - STRIDE_DAYS, STRIDE_DAYS):
        anchor_date = dates[i]
        if rule is None:
            multiplier = 1.0
        else:
            candidates = [(d, s) for d, s in composite_series if d <= anchor_date]
            composite = max(candidates, key=lambda pair: pair[0])[1] if candidates else 0.0
            multiplier = rule(_confidence_for(composite))

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


def _print_result(label: str, result: dict) -> None:
    print(f"{label:22s}: {result['periods']} periods, ann. return={result['annualized_return']:+.2%}, "
          f"Sharpe={result['sharpe']:.2f}, max drawdown={result['max_drawdown']:.2%}, "
          f"multiplier turnover={result['total_multiplier_turnover']:.2f}, cumulative={result['cumulative_return']:+.1%}")


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
    print(f"Dataset: {dataset_id}\n")

    rules = [("Static 1.0x", None), ("naive-v1 (bug)", _multiplier_v1), ("naive-v2 (fixed)", _multiplier_v2)]

    for label, dates in [
        ("FULL SAMPLE (2004-2026)", common_dates),
        ("IN-SAMPLE (2004-2018)", [d for d in common_dates if d < SPLIT_DATE]),
        ("OUT-OF-SAMPLE (2019-2026)", [d for d in common_dates if d >= SPLIT_DATE]),
    ]:
        print(f"=== {label} ===")
        for rule_label, rule in rules:
            result = _run_backtest(dates, closes, composite_series, rule)
            _print_result(rule_label, result)
        print()


if __name__ == "__main__":
    main()
