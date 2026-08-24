from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from backend.engine.indicators.macd import compute_macd
from backend.engine.indicators.rsi import compute_rsi
from backend.engine.timing.backtest import BacktestBar, InsufficientBacktestDataError, Trade

# naive-v2: `macd_rsi_single_name_timing` split into two independently
# registered, independently retireable components instead of one fused
# function -- the granularity gap this version closes.
#
# MACD and RSI are NOT peers in a weighted sum (unlike macro's 8 factors,
# see engine/regime/scoring_v2.py) -- they play different ROLES in a
# sequential entry/exit rule: MACD's bullish crossover is this system's only
# real entry trigger; MACD's bearish crossover AND RSI's overbought reading
# are both valid exit triggers. So the "retire one, the rest keeps working"
# mechanism here is a role-tagged signal ensemble (which components can
# trigger 'entry' vs 'exit'), not a null-tolerant weighted average -- that
# is the correct shape for a rule-based timing system, not a shortcut.
#
# Consequence, stated honestly rather than hidden: retiring `rsi_exit`
# degrades gracefully (MACD alone still forms a complete entry+exit rule --
# exactly the "I'd retire this from my desk" case the architecture was
# designed around). Retiring `macd_crossover` removes the ONLY registered
# entry trigger; with today's two registered components, that is a genuine
# structural constraint, not a bug -- the backtest returns an explicit
# 'no_entry_signal_active' status and zero trades rather than crashing or
# fabricating an entry rule that isn't registered.
#
# Registered in the strategies table as `macd_rsi_single_name_timing`
# (naive-v2, verification_status='registered_only'). v1's fused function
# (backtest.py) stays untouched and importable so any dataset snapshot
# already sealed under naive-v1 stays honestly reproducible.

MIN_BARS = 60

MACD_CROSSOVER = "macd_crossover"  # roles: entry, exit
RSI_OVERBOUGHT_EXIT = "rsi_overbought_exit"  # roles: exit only
ALL_COMPONENT_KEYS = (MACD_CROSSOVER, RSI_OVERBOUGHT_EXIT)


@dataclass(frozen=True)
class BacktestResultV2:
    symbol: str
    status: str  # 'ok' | 'no_entry_signal_active'
    active_components: tuple[str, ...]
    period_start: str
    period_end: str
    trades: list[Trade]
    trade_count: int
    win_rate: float | None
    total_return: float
    buy_hold_return: float
    sharpe_ratio: float | None
    max_drawdown: float
    average_trade_return: float | None
    methodology: str


def run_macd_rsi_backtest_v2(
    symbol: str,
    bars: list[BacktestBar],
    *,
    active_components: frozenset[str],
    rsi_period: int = 14,
    rsi_overbought: float = 70.0,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
) -> BacktestResultV2:
    """Same long-only entry/exit mechanics as v1, but every trigger is gated
    by whether its owning component is currently active (a real, per-run DB
    read in the pipeline stage, not a hand-typed flag here). Raises
    InsufficientBacktestDataError for the same real data-shortage reason as
    v1; returns an honest 'no_entry_signal_active' result (not an error, not
    fabricated trades) when configuration -- not data -- is what's missing.
    """

    ordered = sorted(bars, key=lambda bar: bar.time)
    if len(ordered) < MIN_BARS:
        raise InsufficientBacktestDataError(
            f"{symbol}: only {len(ordered)} bars available; need at least {MIN_BARS}."
        )

    macd_active = MACD_CROSSOVER in active_components
    rsi_active = RSI_OVERBOUGHT_EXIT in active_components
    active_tuple = tuple(key for key in ALL_COMPONENT_KEYS if key in active_components)

    if not macd_active:
        # No registered component can currently trigger an entry. Honest,
        # explicit, zero-trade result -- not a crash, not a silent fallback
        # to an unregistered rule.
        return BacktestResultV2(
            symbol=symbol,
            status="no_entry_signal_active",
            active_components=active_tuple,
            period_start=ordered[0].time,
            period_end=ordered[-1].time,
            trades=[],
            trade_count=0,
            win_rate=None,
            total_return=0.0,
            buy_hold_return=(ordered[-1].close - ordered[0].close) / ordered[0].close,
            sharpe_ratio=None,
            max_drawdown=0.0,
            average_trade_return=None,
            methodology=(
                "No registered entry-capable component is active for macd_rsi_single_name_timing "
                f"(active components: {list(active_tuple) or 'none'}). macd_crossover is the only "
                "registered entry trigger; retiring it removes this strategy's ability to open a "
                "position until a replacement entry signal is registered. This is a real, honest "
                "consequence of the retirement, not a computed result."
            ),
        )

    closes = [bar.close for bar in ordered]
    dates = [bar.time for bar in ordered]
    macd_line, signal_line, _histogram = compute_macd(closes, fast=macd_fast, slow=macd_slow, signal=macd_signal)
    rsi = compute_rsi(closes, period=rsi_period) if rsi_active else [None] * len(closes)

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
        overbought = rsi_active and rsi[i] is not None and rsi[i] >= rsi_overbought

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

    exit_rule = (
        "MACD bearish crossover or RSI(14) >= 70"
        if rsi_active
        else "MACD bearish crossover only (rsi_overbought_exit is retired)"
    )
    return BacktestResultV2(
        symbol=symbol,
        status="ok",
        active_components=active_tuple,
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
            f"Long-only MACD({macd_fast},{macd_slow},{macd_signal}) crossover entry, {exit_rule} exit. "
            f"Active components this run: {list(active_tuple)}. "
            "Signal and fill share the same bar's close — a known simplification. "
            "Naive, unoptimized coefficients (see docs/engine-milestones.md)."
        ),
    )
