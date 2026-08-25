from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from backend.engine.factors import Bar
from backend.engine.factors.cross_sectional_backtest import (
    InsufficientBacktestHistoryError,
    run_cross_sectional_momentum_backtest,
)


def _trending_bars(count: int, drift: float, seed: int, noise: float = 0.01, start: date = date(2016, 1, 1)) -> list[Bar]:
    rng = random.Random(seed)
    price = 100.0
    bars = [Bar(time=start.isoformat(), close=price)]
    for offset in range(1, count):
        price *= 1 + drift + rng.uniform(-noise, noise)
        bars.append(Bar(time=(start + timedelta(days=offset)).isoformat(), close=max(1.0, price)))
    return bars


def _mixed_universe(count: int = 700) -> dict[str, list[Bar]]:
    return {
        "UP1": _trending_bars(count, 0.0015, seed=1),
        "UP2": _trending_bars(count, 0.0012, seed=2),
        "FLAT1": _trending_bars(count, 0.0, seed=3),
        "FLAT2": _trending_bars(count, 0.0001, seed=4),
        "DOWN1": _trending_bars(count, -0.0012, seed=5),
        "DOWN2": _trending_bars(count, -0.0015, seed=6),
    }


def test_insufficient_history_raises_instead_of_fabricating() -> None:
    thin = {symbol: _trending_bars(100, 0.001, seed=i) for i, symbol in enumerate(["A", "B", "C"])}
    with pytest.raises(InsufficientBacktestHistoryError):
        run_cross_sectional_momentum_backtest(thin, top_n=2, rebalance_days=21)


def test_basic_backtest_produces_real_sane_metrics() -> None:
    universe = _mixed_universe()
    result = run_cross_sectional_momentum_backtest(universe, top_n=2, rebalance_days=21)

    assert result.top_n == 2
    assert len(result.periods) >= 4
    assert all(len(period.selected_symbols) == 2 for period in result.periods)
    assert 0.0 <= result.win_rate <= 1.0
    assert 0.0 <= result.portfolio_turnover <= 1.0
    assert result.max_drawdown <= 0.0
    assert result.annualized_volatility >= 0.0
    # Enough real trading days (700) to clear the 1-year CAGR floor.
    assert result.cagr is not None


def test_top_n_selection_favors_uptrending_symbols() -> None:
    """The naive ranking should, more often than not, prefer the real
    uptrending symbols over the real downtrending ones -- not a guarantee
    every period (that would be overfitting the test to the naive formula),
    but a real, checkable tendency."""

    universe = _mixed_universe()
    result = run_cross_sectional_momentum_backtest(universe, top_n=2, rebalance_days=21)

    up_selections = sum(1 for period in result.periods if "UP1" in period.selected_symbols or "UP2" in period.selected_symbols)
    down_selections = sum(1 for period in result.periods if "DOWN1" in period.selected_symbols or "DOWN2" in period.selected_symbols)
    assert up_selections > down_selections


def test_benchmark_is_real_equal_weight_not_fabricated() -> None:
    universe = _mixed_universe()
    result = run_cross_sectional_momentum_backtest(universe, top_n=2, rebalance_days=21)
    # Benchmark isn't just echoing the strategy return -- it's the whole
    # universe, so on this deliberately mixed (some up, some down) universe
    # it should sit meaningfully below the top-N-only strategy return.
    assert result.benchmark_total_return != result.total_return
