from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from backend.engine.timing.backtest import BacktestBar, InsufficientBacktestDataError
from backend.engine.timing.backtest_v2 import (
    MACD_CROSSOVER,
    RSI_OVERBOUGHT_EXIT,
    run_macd_rsi_backtest_v2,
)


def _oscillating_bars(count: int = 400, base: float = 100.0, amplitude: float = 20.0, cycle_days: int = 70) -> list[BacktestBar]:
    start = date(2015, 1, 1)
    bars = []
    for i in range(count):
        price = base + amplitude * math.sin(2 * math.pi * i / cycle_days) + (i * 0.01)
        bars.append(BacktestBar(time=(start + timedelta(days=i)).isoformat(), close=max(1.0, price)))
    return bars


def test_raises_instead_of_fabricating_when_too_few_bars() -> None:
    with pytest.raises(InsufficientBacktestDataError):
        run_macd_rsi_backtest_v2("TEST", _oscillating_bars(count=30), active_components=frozenset({MACD_CROSSOVER, RSI_OVERBOUGHT_EXIT}))


def test_both_active_matches_v1_shape() -> None:
    result = run_macd_rsi_backtest_v2(
        "TEST", _oscillating_bars(), active_components=frozenset({MACD_CROSSOVER, RSI_OVERBOUGHT_EXIT})
    )
    assert result.status == "ok"
    assert result.trade_count > 0
    assert set(result.active_components) == {MACD_CROSSOVER, RSI_OVERBOUGHT_EXIT}
    for trade in result.trades:
        if trade.exit_date is not None:
            assert ("MACD crossed below signal" in trade.exit_reason) or ("overbought" in trade.exit_reason)


def test_retiring_rsi_degrades_gracefully_macd_alone_still_trades() -> None:
    """The real case the architecture is designed around: retiring the
    exit-only component must not break the strategy -- MACD alone still
    forms a complete entry+exit rule."""

    bars = _oscillating_bars()
    both = run_macd_rsi_backtest_v2("TEST", bars, active_components=frozenset({MACD_CROSSOVER, RSI_OVERBOUGHT_EXIT}))
    macd_only = run_macd_rsi_backtest_v2("TEST", bars, active_components=frozenset({MACD_CROSSOVER}))

    assert macd_only.status == "ok"
    assert macd_only.trade_count > 0
    assert macd_only.active_components == (MACD_CROSSOVER,)
    # No RSI-triggered exits when RSI is retired.
    for trade in macd_only.trades:
        if trade.exit_date is not None:
            assert "overbought" not in trade.exit_reason
    # With RSI retired some exits fire later (or not at all before an MACD
    # cross), so trade timing can differ from the both-active run -- the
    # important invariant is that it still runs and still trades, not that
    # results are identical.
    assert both.status == "ok"


def test_retiring_macd_leaves_no_entry_signal_honest_not_fabricated() -> None:
    """MACD is the only registered entry trigger today. Retiring it is a
    real structural constraint, not a bug -- must surface as an explicit,
    honest status with zero trades, never a crash or an invented rule."""

    result = run_macd_rsi_backtest_v2(
        "TEST", _oscillating_bars(), active_components=frozenset({RSI_OVERBOUGHT_EXIT})
    )
    assert result.status == "no_entry_signal_active"
    assert result.trade_count == 0
    assert result.trades == []
    assert result.total_return == 0.0
    assert result.win_rate is None
    # Buy-and-hold is still computable from real prices even with no strategy trades.
    assert result.buy_hold_return != 0.0


def test_retiring_both_components_also_honest_not_a_crash() -> None:
    result = run_macd_rsi_backtest_v2("TEST", _oscillating_bars(), active_components=frozenset())
    assert result.status == "no_entry_signal_active"
    assert result.active_components == ()
    assert result.trade_count == 0
