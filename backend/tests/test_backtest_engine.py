from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from backend.engine.timing.backtest import (
    BacktestBar,
    InsufficientBacktestDataError,
    run_macd_rsi_backtest,
)


def _oscillating_bars(count: int = 400, base: float = 100.0, amplitude: float = 20.0, cycle_days: int = 70) -> list[BacktestBar]:
    start = date(2015, 1, 1)
    bars = []
    for i in range(count):
        price = base + amplitude * math.sin(2 * math.pi * i / cycle_days) + (i * 0.01)
        bars.append(BacktestBar(time=(start + timedelta(days=i)).isoformat(), close=max(1.0, price)))
    return bars


def _flat_bars(count: int = 400, price: float = 100.0) -> list[BacktestBar]:
    start = date(2015, 1, 1)
    return [BacktestBar(time=(start + timedelta(days=i)).isoformat(), close=price) for i in range(count)]


def test_raises_instead_of_fabricating_when_too_few_bars() -> None:
    with pytest.raises(InsufficientBacktestDataError):
        run_macd_rsi_backtest("TEST", _oscillating_bars(count=30))


def test_oscillating_prices_produce_real_trades_with_reasons() -> None:
    result = run_macd_rsi_backtest("TEST", _oscillating_bars())
    assert result.trade_count > 0
    for trade in result.trades:
        assert trade.entry_price > 0
        assert "MACD crossed above signal" in trade.entry_reason
        if trade.exit_date is not None:
            assert trade.exit_price is not None
            assert trade.return_fraction is not None
            assert trade.return_fraction == pytest.approx((trade.exit_price - trade.entry_price) / trade.entry_price)
            assert ("MACD crossed below signal" in trade.exit_reason) or ("overbought" in trade.exit_reason)
    assert result.win_rate is None or 0.0 <= result.win_rate <= 1.0
    assert result.max_drawdown <= 0.0
    assert result.period_start == "2015-01-01"


def test_flat_prices_produce_no_trades_and_zero_return() -> None:
    result = run_macd_rsi_backtest("FLAT", _flat_bars())
    assert result.trade_count == 0
    assert result.total_return == pytest.approx(0.0)
    assert result.buy_hold_return == pytest.approx(0.0)
    assert result.win_rate is None
    assert result.sharpe_ratio is None  # zero-variance daily returns — no ratio to report, not a fabricated one


def test_buy_hold_return_matches_first_and_last_close() -> None:
    bars = _oscillating_bars()
    result = run_macd_rsi_backtest("TEST", bars)
    ordered = sorted(bars, key=lambda bar: bar.time)
    expected = (ordered[-1].close - ordered[0].close) / ordered[0].close
    assert result.buy_hold_return == pytest.approx(expected)


def test_open_trade_at_end_of_period_has_no_return_and_is_excluded_from_trade_count() -> None:
    # A pure uptrend into the end of the window should leave a position open
    # (no bearish crossover, no overbought yet from a modest slope).
    bars = [
        BacktestBar(time=(date(2015, 1, 1) + timedelta(days=i)).isoformat(), close=100.0 + i * 0.05)
        for i in range(120)
    ]
    result = run_macd_rsi_backtest("TREND", bars)
    open_trades = [trade for trade in result.trades if trade.exit_date is None]
    if open_trades:
        assert open_trades[0].return_fraction is None
    assert result.trade_count == len([t for t in result.trades if t.return_fraction is not None])
