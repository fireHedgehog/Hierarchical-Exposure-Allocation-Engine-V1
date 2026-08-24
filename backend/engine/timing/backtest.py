from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from backend.engine.indicators.macd import compute_macd
from backend.engine.indicators.rsi import compute_rsi

# Independent single-name timing, deliberately separate from the
# cross-sectional momentum in engine/factors/ (this project's non-negotiable
# rule: "cross-sectional discovery and single-name timing remain separately
# revisioned and evaluated layers"). A naive, real, long-only rule — the
# point of this milestone is a genuine simulation over real prices with a
# real trade log and real metrics, not a competitive strategy. See
# docs/engine-milestones.md.

# Registered in the strategies table as `macd_rsi_single_name_timing`
# (naive-v1, verification_status='registered_only').

MIN_BARS = 60  # real warmup for a 26-period EMA, plus room to actually trade


class InsufficientBacktestDataError(ValueError):
    """Not enough bars to run a meaningful backtest."""


@dataclass(frozen=True)
class BacktestBar:
    time: str
    close: float


@dataclass(frozen=True)
class Trade:
    entry_date: str
    entry_price: float
    entry_reason: str
    exit_date: str | None
    exit_price: float | None
    exit_reason: str | None
    return_fraction: float | None  # None while the trade is still open


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    period_start: str
    period_end: str
    trades: list[Trade]
    trade_count: int  # closed round trips only
    win_rate: float | None
    total_return: float
    buy_hold_return: float
    sharpe_ratio: float | None
    max_drawdown: float
    average_trade_return: float | None
    methodology: str


def run_macd_rsi_backtest(
    symbol: str,
    bars: list[BacktestBar],
    *,
    rsi_period: int = 14,
    rsi_overbought: float = 70.0,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
) -> BacktestResult:
    """Long-only: enter on a MACD bullish crossover, exit on a MACD bearish
    crossover or an RSI-overbought reading, whichever comes first.

    Signal and fill share the same bar's close — a known, stated
    simplification of a first-pass backtest, not a hidden one. Raises
    InsufficientBacktestDataError rather than returning a fabricated result
    when there isn't enough history to trade.
    """

    ordered = sorted(bars, key=lambda bar: bar.time)
    if len(ordered) < MIN_BARS:
        raise InsufficientBacktestDataError(
            f"{symbol}: only {len(ordered)} bars available; need at least {MIN_BARS}."
        )

    closes = [bar.close for bar in ordered]
    dates = [bar.time for bar in ordered]
    macd_line, signal_line, _histogram = compute_macd(
        closes, fast=macd_fast, slow=macd_slow, signal=macd_signal
    )
    rsi = compute_rsi(closes, period=rsi_period)

    trades: list[Trade] = []
    position_entry_index: int | None = None
    equity = 1.0
    equity_curve = [1.0]
    daily_returns: list[float] = []

    for i in range(1, len(ordered)):
        day_return = (closes[i] - closes[i - 1]) / closes[i - 1] if position_entry_index is not None else 0.0
        equity *= 1 + day_return
        equity_curve.append(equity)
        daily_returns.append(day_return)

        if macd_line[i] is None or signal_line[i] is None:
            continue
        prior_valid = macd_line[i - 1] is not None and signal_line[i - 1] is not None
        bullish_cross = prior_valid and macd_line[i - 1] <= signal_line[i - 1] and macd_line[i] > signal_line[i]
        bearish_cross = prior_valid and macd_line[i - 1] >= signal_line[i - 1] and macd_line[i] < signal_line[i]
        overbought = rsi[i] is not None and rsi[i] >= rsi_overbought

        if position_entry_index is None and bullish_cross:
            position_entry_index = i
        elif position_entry_index is not None and (bearish_cross or overbought):
            entry_index = position_entry_index
            entry_price = closes[entry_index]
            exit_price = closes[i]
            exit_reason = (
                f"MACD crossed below signal ({macd_line[i]:.3f} < {signal_line[i]:.3f})."
                if bearish_cross
                else f"RSI reached {rsi[i]:.1f}, at/above the {rsi_overbought:.0f} overbought threshold."
            )
            trades.append(
                Trade(
                    entry_date=dates[entry_index],
                    entry_price=entry_price,
                    entry_reason=(
                        f"MACD crossed above signal "
                        f"({macd_line[entry_index]:.3f} > {signal_line[entry_index]:.3f})."
                    ),
                    exit_date=dates[i],
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    return_fraction=(exit_price - entry_price) / entry_price,
                )
            )
            position_entry_index = None

    if position_entry_index is not None:
        trades.append(
            Trade(
                entry_date=dates[position_entry_index],
                entry_price=closes[position_entry_index],
                entry_reason=(
                    f"MACD crossed above signal "
                    f"({macd_line[position_entry_index]:.3f} > {signal_line[position_entry_index]:.3f})."
                ),
                exit_date=None,
                exit_price=None,
                exit_reason=None,
                return_fraction=None,
            )
        )

    closed_trades = [trade for trade in trades if trade.return_fraction is not None]
    trade_count = len(closed_trades)
    win_rate = (
        sum(1 for trade in closed_trades if trade.return_fraction > 0) / trade_count if trade_count else None
    )
    average_trade_return = (
        statistics.fmean(trade.return_fraction for trade in closed_trades) if trade_count else None
    )
    total_return = equity - 1.0
    buy_hold_return = (closes[-1] - closes[0]) / closes[0]

    mean_daily = statistics.fmean(daily_returns) if daily_returns else 0.0
    stdev_daily = statistics.pstdev(daily_returns) if len(daily_returns) > 1 else 0.0
    sharpe_ratio = (mean_daily / stdev_daily) * math.sqrt(252) if stdev_daily > 1e-12 else None

    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, (value - peak) / peak)

    return BacktestResult(
        symbol=symbol,
        period_start=dates[0],
        period_end=dates[-1],
        trades=trades,
        trade_count=trade_count,
        win_rate=win_rate,
        total_return=total_return,
        buy_hold_return=buy_hold_return,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        average_trade_return=average_trade_return,
        methodology=(
            f"Long-only MACD({macd_fast},{macd_slow},{macd_signal}) crossover entry, "
            f"MACD bearish crossover or RSI({rsi_period}) >= {rsi_overbought:.0f} exit. "
            "Signal and fill share the same bar's close — a known simplification. "
            "Naive, unoptimized coefficients (see docs/engine-milestones.md)."
        ),
    )
