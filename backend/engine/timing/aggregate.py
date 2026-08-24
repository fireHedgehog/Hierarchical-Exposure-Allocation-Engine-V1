from __future__ import annotations

import statistics
from dataclasses import dataclass

from backend.engine.timing.backtest import BacktestResult

# Rolls up the independent per-symbol MACD/RSI backtests (backtest.py) into
# one desk-level evaluation object. Equal-weighted mean/median across symbols
# — a naive aggregate, not a compounded portfolio equity curve (no
# correlation, no shared capital, no costs). Real numbers computed from real
# per-symbol BacktestResult objects; nothing here is typed in.


@dataclass(frozen=True)
class DeskBacktestAggregate:
    symbols_tested: int
    symbols_backtested: int
    period_start: str
    period_end: str
    total_trades: int
    mean_total_return: float
    median_total_return: float
    mean_buy_hold_return: float
    mean_excess_return: float
    mean_win_rate: float | None
    mean_sharpe_ratio: float | None
    mean_max_drawdown: float
    best_symbol: str
    best_symbol_return: float
    worst_symbol: str
    worst_symbol_return: float
    methodology: str


def aggregate_backtests(results: list[BacktestResult], symbols_tested: int) -> DeskBacktestAggregate | None:
    """Equal-weighted aggregate across all symbols that had enough bars to
    backtest this run. Returns None only when zero symbols could be
    backtested (honest empty state, never a fabricated aggregate)."""

    if not results:
        return None

    total_returns = [result.total_return for result in results]
    buy_hold_returns = [result.buy_hold_return for result in results]
    excess_returns = [result.total_return - result.buy_hold_return for result in results]
    win_rates = [result.win_rate for result in results if result.win_rate is not None]
    sharpe_ratios = [result.sharpe_ratio for result in results if result.sharpe_ratio is not None]
    drawdowns = [result.max_drawdown for result in results]
    best = max(results, key=lambda result: result.total_return)
    worst = min(results, key=lambda result: result.total_return)

    return DeskBacktestAggregate(
        symbols_tested=symbols_tested,
        symbols_backtested=len(results),
        period_start=min(result.period_start for result in results),
        period_end=max(result.period_end for result in results),
        total_trades=sum(result.trade_count for result in results),
        mean_total_return=statistics.fmean(total_returns),
        median_total_return=statistics.median(total_returns),
        mean_buy_hold_return=statistics.fmean(buy_hold_returns),
        mean_excess_return=statistics.fmean(excess_returns),
        mean_win_rate=statistics.fmean(win_rates) if win_rates else None,
        mean_sharpe_ratio=statistics.fmean(sharpe_ratios) if sharpe_ratios else None,
        mean_max_drawdown=statistics.fmean(drawdowns),
        best_symbol=best.symbol,
        best_symbol_return=best.total_return,
        worst_symbol=worst.symbol,
        worst_symbol_return=worst.total_return,
        methodology=(
            f"Equal-weighted mean/median across {len(results)} independent single-name MACD/RSI backtests "
            "(each symbol traded alone, in isolation — see its own methodology note for the exact rule). "
            "Naive aggregate: no shared capital, no cross-symbol correlation, and no transaction costs are "
            "modeled at the desk level."
        ),
    )
