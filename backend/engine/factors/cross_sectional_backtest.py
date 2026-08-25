from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from backend.engine.factors.momentum_v2 import compute_cross_section_v2
from backend.engine.factors.types import Bar, InsufficientPriceDataError

# The "strategy" granularity tier's first real content: does cross_sectional_
# momentum's actual composite ranking (momentum_v2.compute_cross_section_v2,
# the same function factor_engine.py calls in production) turn into a real
# equity curve if you actually trade it? Naive-v1, same contract as every
# other engine module here: real function, real data, hand-picked
# parameters (top_n, rebalance_days) accepted, never fitted or optimized --
# that is explicitly out of scope until Milestone 4 (docs/engine-milestones.md).
#
# Walk-forward, point-in-time by construction: at each rebalance date, only
# bars up to and including that date are passed to compute_cross_section_v2
# -- the same function recomputes its own horizon weights fresh each time
# from only the history available then, exactly as a live run would.
#
# Registered in the strategies table as `cross_sectional_momentum`
# (naive-v1 at the strategy level -- a new tier, not a new version; the
# ranking itself stays naive-v2, unchanged).

MIN_REBALANCES = 4  # a real minimum floor, not a fitted one -- guards a degenerate call


class InsufficientBacktestHistoryError(ValueError):
    """Not enough aligned history across the universe to run a single rebalance."""


@dataclass(frozen=True)
class RebalancePeriod:
    start_date: str
    end_date: str
    selected_symbols: tuple[str, ...]
    period_return: float  # equal-weighted mean forward return of selected symbols
    benchmark_return: float  # equal-weighted mean forward return of the WHOLE eligible universe


@dataclass(frozen=True)
class CrossSectionalBacktestResult:
    top_n: int
    rebalance_days: int
    period_start: str
    period_end: str
    periods: list[RebalancePeriod]
    total_return: float
    benchmark_total_return: float
    cagr: float | None  # None if the window is under one year -- not fabricated
    annualized_volatility: float
    sharpe_ratio: float | None  # None on ~zero volatility, never fabricated as infinity
    max_drawdown: float
    calmar_ratio: float | None  # None when max_drawdown is ~0
    portfolio_turnover: float  # mean fraction of the top-N set that changes each rebalance
    win_rate: float  # share of periods with a positive period_return
    methodology: str


def run_cross_sectional_momentum_backtest(
    bars_by_symbol: dict[str, list[Bar]],
    *,
    top_n: int = 5,
    rebalance_days: int = 21,
) -> CrossSectionalBacktestResult:
    """Naive-v1 walk-forward backtest: at each rebalance date, rank the
    universe with the real, current production ranking function
    (compute_cross_section_v2), buy the top `top_n` symbols equal-weighted,
    hold to the next rebalance, and chain the resulting real returns into an
    equity curve. `top_n` and `rebalance_days` are disclosed, hand-picked
    parameters, not fit to this universe -- the point of this pass is
    proving the walk-forward mechanics are real, not optimizing them.
    """

    symbols = sorted(bars_by_symbol)
    ordered_by_symbol = {symbol: sorted(bars_by_symbol[symbol], key=lambda bar: bar.time) for symbol in symbols}
    dates_by_symbol = {symbol: [bar.time for bar in bars] for symbol, bars in ordered_by_symbol.items()}
    closes_by_symbol = {symbol: [bar.close for bar in bars] for symbol, bars in ordered_by_symbol.items()}

    # A rebalance date must have real bars for every symbol at that index --
    # use the shortest history in the universe as the walk-forward spine so
    # every step is comparing symbols on the same real calendar position.
    min_length = min((len(bars) for bars in ordered_by_symbol.values()), default=0)
    if min_length < 300:  # ~14 months: enough for compute_cross_section_v2's own 126-day floor plus room to walk forward
        raise InsufficientBacktestHistoryError(
            f"shortest symbol history is {min_length} bars; need at least 300 to walk forward at all."
        )

    rebalance_indices = list(range(252, min_length - rebalance_days, rebalance_days))
    if len(rebalance_indices) < MIN_REBALANCES:
        raise InsufficientBacktestHistoryError(
            f"only {len(rebalance_indices)} rebalance points available; need at least {MIN_REBALANCES}."
        )

    periods: list[RebalancePeriod] = []
    previous_selection: frozenset[str] = frozenset()
    turnovers: list[float] = []

    for index in rebalance_indices:
        truncated = {
            symbol: [Bar(time=dates_by_symbol[symbol][i], close=closes_by_symbol[symbol][i]) for i in range(index + 1)]
            for symbol in symbols
        }
        try:
            ranked, _weights = compute_cross_section_v2(truncated)
        except InsufficientPriceDataError:
            continue

        selected = tuple(item.symbol for item in ranked[:top_n])
        selected_set = frozenset(selected)
        if previous_selection:
            changed = len(selected_set.symmetric_difference(previous_selection))
            turnovers.append(changed / max(len(selected_set), len(previous_selection)))
        previous_selection = selected_set

        end_index = index + rebalance_days
        selected_returns = [
            (closes_by_symbol[symbol][end_index] - closes_by_symbol[symbol][index]) / closes_by_symbol[symbol][index]
            for symbol in selected
            if closes_by_symbol[symbol][index] != 0
        ]
        benchmark_returns = [
            (closes_by_symbol[symbol][end_index] - closes_by_symbol[symbol][index]) / closes_by_symbol[symbol][index]
            for symbol in symbols
            if closes_by_symbol[symbol][index] != 0
        ]
        if not selected_returns:
            continue

        periods.append(
            RebalancePeriod(
                start_date=dates_by_symbol[symbols[0]][index],
                end_date=dates_by_symbol[symbols[0]][end_index],
                selected_symbols=selected,
                period_return=statistics.fmean(selected_returns),
                benchmark_return=statistics.fmean(benchmark_returns) if benchmark_returns else 0.0,
            )
        )

    if len(periods) < MIN_REBALANCES:
        raise InsufficientBacktestHistoryError(
            f"only {len(periods)} periods actually produced a real ranking; need at least {MIN_REBALANCES}."
        )

    period_returns = [period.period_return for period in periods]
    benchmark_returns_series = [period.benchmark_return for period in periods]
    periods_per_year = 252.0 / rebalance_days

    equity = 1.0
    equity_curve = [1.0]
    for r in period_returns:
        equity *= 1 + r
        equity_curve.append(equity)
    total_return = equity - 1.0

    benchmark_equity = 1.0
    for r in benchmark_returns_series:
        benchmark_equity *= 1 + r
    benchmark_total_return = benchmark_equity - 1.0

    num_years = len(periods) / periods_per_year
    cagr = (equity ** (1.0 / num_years) - 1.0) if num_years >= 1.0 else None

    mean_period = statistics.fmean(period_returns)
    stdev_period = statistics.pstdev(period_returns) if len(period_returns) > 1 else 0.0
    annualized_volatility = stdev_period * math.sqrt(periods_per_year)
    sharpe_ratio = (
        (mean_period * periods_per_year) / annualized_volatility if annualized_volatility > 1e-9 else None
    )

    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, (value - peak) / peak)
    calmar_ratio = (cagr / abs(max_drawdown)) if (cagr is not None and abs(max_drawdown) > 1e-9) else None

    win_rate = sum(1 for r in period_returns if r > 0) / len(period_returns)
    portfolio_turnover = statistics.fmean(turnovers) if turnovers else 0.0

    return CrossSectionalBacktestResult(
        top_n=top_n,
        rebalance_days=rebalance_days,
        period_start=periods[0].start_date,
        period_end=periods[-1].end_date,
        periods=periods,
        total_return=total_return,
        benchmark_total_return=benchmark_total_return,
        cagr=cagr,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        calmar_ratio=calmar_ratio,
        portfolio_turnover=portfolio_turnover,
        win_rate=win_rate,
        methodology=(
            f"Naive-v1 walk-forward: every {rebalance_days} trading days, rank the universe with the real "
            f"production ranking (momentum_v2.compute_cross_section_v2, recomputed from only the history "
            f"available at that date), buy the top {top_n} symbols equal-weighted, hold to the next rebalance. "
            f"Benchmark is an equal-weighted hold of the whole eligible universe over the same periods. "
            "top_n and rebalance_days are disclosed, hand-picked parameters, not fit to this universe."
        ),
    )
