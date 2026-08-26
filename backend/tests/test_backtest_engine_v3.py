from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from backend.engine.timing.backtest import BacktestBar, InsufficientBacktestDataError
from backend.engine.timing.backtest_v3 import (
    RSI_OVERBOUGHT_EXIT,
    SHORT_TERM_REVERSAL_ENTRY,
    run_reversal_rsi_backtest_v3,
)


def _oscillating_bars(count: int = 400, base: float = 100.0, amplitude: float = 25.0, cycle_days: int = 40) -> list[BacktestBar]:
    """Steeper, shorter-cycle oscillation than the v2 test fixture, so a
    real >=3% trailing-5-day pullback (the entry threshold) actually occurs
    -- a slower cycle wouldn't reliably trigger it."""

    start = date(2015, 1, 1)
    bars = []
    for i in range(count):
        price = base + amplitude * math.sin(2 * math.pi * i / cycle_days) + (i * 0.01)
        bars.append(BacktestBar(time=(start + timedelta(days=i)).isoformat(), close=max(1.0, price)))
    return bars


def test_raises_instead_of_fabricating_when_too_few_bars() -> None:
    with pytest.raises(InsufficientBacktestDataError):
        run_reversal_rsi_backtest_v3(
            "TEST", _oscillating_bars(count=30), active_components=frozenset({SHORT_TERM_REVERSAL_ENTRY, RSI_OVERBOUGHT_EXIT})
        )


def test_both_active_trades_on_real_pullbacks() -> None:
    result = run_reversal_rsi_backtest_v3(
        "TEST", _oscillating_bars(), active_components=frozenset({SHORT_TERM_REVERSAL_ENTRY, RSI_OVERBOUGHT_EXIT})
    )
    assert result.status == "ok"
    assert result.trade_count > 0
    assert set(result.active_components) == {SHORT_TERM_REVERSAL_ENTRY, RSI_OVERBOUGHT_EXIT}
    for trade in result.trades:
        assert "pullback threshold" in trade.entry_reason
        if trade.exit_date is not None:
            assert "overbought" in trade.exit_reason


def test_retiring_rsi_leaves_positions_open_no_crash() -> None:
    """Retiring the only registered exit trigger must not crash or
    fabricate an exit -- positions simply stay open (real, honest,
    zero-trade-count-closed behavior), matching v2's same real consequence
    for its own exit-only component."""

    bars = _oscillating_bars()
    reversal_only = run_reversal_rsi_backtest_v3("TEST", bars, active_components=frozenset({SHORT_TERM_REVERSAL_ENTRY}))
    assert reversal_only.status == "ok"
    assert reversal_only.active_components == (SHORT_TERM_REVERSAL_ENTRY,)
    # No RSI-triggered exits when RSI is retired -- any trades logged are
    # either still-open (no exit_date) or none at all.
    for trade in reversal_only.trades:
        assert trade.exit_date is None


def test_retiring_reversal_entry_leaves_no_entry_signal_honest_not_fabricated() -> None:
    """short_term_reversal_entry is the only registered entry trigger.
    Retiring it is a real structural constraint, not a bug -- must surface
    as an explicit, honest status with zero trades, never a crash or an
    invented rule -- the exact same real consequence macd_crossover's own
    retirement produced in v2."""

    result = run_reversal_rsi_backtest_v3(
        "TEST", _oscillating_bars(), active_components=frozenset({RSI_OVERBOUGHT_EXIT})
    )
    assert result.status == "no_entry_signal_active"
    assert result.trade_count == 0
    assert result.trades == []
    assert result.total_return == 0.0
    assert result.win_rate is None
    assert result.buy_hold_return != 0.0


def test_retiring_both_components_also_honest_not_a_crash() -> None:
    result = run_reversal_rsi_backtest_v3("TEST", _oscillating_bars(), active_components=frozenset())
    assert result.status == "no_entry_signal_active"
    assert result.active_components == ()
    assert result.trade_count == 0
