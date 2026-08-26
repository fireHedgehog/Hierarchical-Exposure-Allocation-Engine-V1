from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from backend.engine.indicators.rsi import compute_rsi
from backend.engine.timing.backtest import BacktestBar, InsufficientBacktestDataError, Trade

# naive-v3: macd_crossover retired as an entry trigger -- a real event study
# (docs/hypotheses/, docs/engine-milestones.md 0.29) found no real edge
# (r~=0.002, p~=0.66, statistically indistinguishable from a random day).
# short_term_reversal_entry replaces it: real, replicated, cost-checked
# evidence (docs/hypotheses/short-term-mean-reversion.md,
# short-term-reversal-cost-robustness.md) that a real pullback tends to
# partially reverse within about a week. rsi_overbought_exit is carried
# forward unchanged -- its own evidence was never in question, only MACD's
# entry role was.
#
# The entry threshold (REVERSAL_ENTRY_THRESHOLD, a trailing 5-day return
# below -3%) is a disclosed, hand-picked, naive parameter -- the research
# validated the *sign* (H-STREV01) and a *cross-sectional bottom-N ranking*
# (H-STREV02), not this specific absolute threshold. This is the same
# "naive but real, not fit" standard already applied to RSI's 70 threshold
# and MACD's 12/26/9 in v1/v2 -- disclosed here for the same reason, not a
# new gap this version introduces.
#
# v1's fused function (backtest.py) and v2's MACD/RSI function
# (backtest_v2.py) both stay untouched and importable so any dataset
# snapshot already sealed under either stays honestly reproducible; this is
# a NEW version row, not a rewrite.

MIN_BARS = 60
REVERSAL_LOOKBACK_DAYS = 5  # matches the confirmed H-STREV01/H-STREV02 window
REVERSAL_ENTRY_THRESHOLD = -0.03  # disclosed, hand-picked, not fit -- see module docstring

SHORT_TERM_REVERSAL_ENTRY = "short_term_reversal_entry"  # roles: entry only
RSI_OVERBOUGHT_EXIT = "rsi_overbought_exit"  # roles: exit only
ALL_COMPONENT_KEYS = (SHORT_TERM_REVERSAL_ENTRY, RSI_OVERBOUGHT_EXIT)


@dataclass(frozen=True)
class BacktestResultV3:
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


def run_reversal_rsi_backtest_v3(
    symbol: str,
    bars: list[BacktestBar],
    *,
    active_components: frozenset[str],
    rsi_period: int = 14,
    rsi_overbought: float = 70.0,
    reversal_lookback_days: int = REVERSAL_LOOKBACK_DAYS,
    reversal_entry_threshold: float = REVERSAL_ENTRY_THRESHOLD,
) -> BacktestResultV3:
    """Long-only entry on a real trailing-return pullback (short-term
    reversal), exit on RSI overbought -- every trigger gated by whether its
    owning component is currently active (a real, per-run DB read in the
    pipeline stage, not a hand-typed flag here). Raises
    InsufficientBacktestDataError for a real data-shortage reason; returns
    an honest 'no_entry_signal_active' result (not an error, not fabricated
    trades) when configuration -- not data -- is what's missing.
    """

    ordered = sorted(bars, key=lambda bar: bar.time)
    if len(ordered) < MIN_BARS:
        raise InsufficientBacktestDataError(
            f"{symbol}: only {len(ordered)} bars available; need at least {MIN_BARS}."
        )

    reversal_active = SHORT_TERM_REVERSAL_ENTRY in active_components
    rsi_active = RSI_OVERBOUGHT_EXIT in active_components
    active_tuple = tuple(key for key in ALL_COMPONENT_KEYS if key in active_components)

    if not reversal_active:
        # No registered component can currently trigger an entry. Honest,
        # explicit, zero-trade result -- not a crash, not a silent fallback
        # to an unregistered rule.
        return BacktestResultV3(
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
                f"(active components: {list(active_tuple) or 'none'}). short_term_reversal_entry is "
                "the only registered entry trigger; retiring it removes this strategy's ability to "
                "open a position until a replacement entry signal is registered. This is a real, "
                "honest consequence of the retirement, not a computed result."
            ),
        )

    closes = [bar.close for bar in ordered]
    dates = [bar.time for bar in ordered]
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

        trailing_return = None
        if i >= reversal_lookback_days and closes[i - reversal_lookback_days] != 0:
            trailing_return = (closes[i] - closes[i - reversal_lookback_days]) / abs(closes[i - reversal_lookback_days])
        pullback_trigger = trailing_return is not None and trailing_return < reversal_entry_threshold
        overbought = rsi_active and rsi[i] is not None and rsi[i] >= rsi_overbought

        if position_entry_index is None and pullback_trigger:
            position_entry_index = i
        elif position_entry_index is not None and overbought:
            entry_index = position_entry_index
            entry_price = closes[entry_index]
            exit_price = closes[i]
            trades.append(
                Trade(
                    entry_date=dates[entry_index],
                    entry_price=entry_price,
                    entry_reason=(
                        f"Trailing {reversal_lookback_days}-day return "
                        f"{trailing_return_at_entry_pct(closes, entry_index, reversal_lookback_days):+.1%} "
                        f"< {reversal_entry_threshold:+.1%} pullback threshold."
                    ),
                    exit_date=dates[i],
                    exit_price=exit_price,
                    exit_reason=f"RSI reached {rsi[i]:.1f}, at/above the {rsi_overbought:.0f} overbought threshold.",
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
                    f"Trailing {reversal_lookback_days}-day return "
                    f"{trailing_return_at_entry_pct(closes, position_entry_index, reversal_lookback_days):+.1%} "
                    f"< {reversal_entry_threshold:+.1%} pullback threshold."
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

    return BacktestResultV3(
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
            f"Long-only trailing-{reversal_lookback_days}-day-return < {reversal_entry_threshold:+.1%} pullback "
            f"entry, RSI(14) >= {rsi_overbought:.0f} overbought exit. "
            f"Active components this run: {list(active_tuple)}. "
            "Signal and fill share the same bar's close -- a known simplification. "
            "Entry threshold is naive/hand-picked, not fit to this universe (see docs/engine-milestones.md); "
            "the underlying reversal effect itself is real, replicated research evidence, cost-checked at "
            "the cross-sectional strategy level but not yet at this exact single-name specification."
        ),
    )


def trailing_return_at_entry_pct(closes: list[float], index: int, lookback_days: int) -> float:
    past_close = closes[index - lookback_days]
    return (closes[index] - past_close) / abs(past_close) if past_close != 0 else 0.0
