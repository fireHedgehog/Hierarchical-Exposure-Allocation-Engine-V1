"""Scratch script for docs/hypotheses/short-term-reversal-cost-robustness.md
(H-STREV02).

Real walk-forward, tradable version of H-STREV01's confirmed gross IC:
weekly rebalance, buy the biggest trailing-5-day losers, hold a week, chain
into a real equity curve -- gross, and net at several disclosed real
round-trip cost assumptions, scaled by actually-measured turnover each
period. Read-only against the sealed dataset -- never writes anywhere.

Run: .venv/bin/python -m backend.research_lab.short_term_reversal_cost_robustness
"""

from __future__ import annotations

import math
import statistics

from backend.database import connect, resolve_database_path

TOP_N = 5
REBALANCE_DAYS = 5  # weekly, matching H-STREV01's own confirmed window
LOOKBACK_DAYS = 5  # the trailing signal window
COST_LEVELS_BPS = (5, 10, 25, 50)  # real, disclosed round-trip cost assumptions


def _security_id_for(symbol: str, category: str) -> str:
    # Reproduced, not imported -- see backend/research_lab/README.md.
    slug = symbol.lower().replace("-", "")
    if category == "crypto_reference":
        return f"ref-{slug}"
    if category == "mega_cap_equity":
        return f"us-equity-{slug}"
    return f"us-etf-{symbol.lower()}"


def _equity_curve_stats(period_returns: list[float], periods_per_year: float) -> dict[str, float | None]:
    equity = 1.0
    equity_curve = [1.0]
    for r in period_returns:
        equity *= 1 + r
        equity_curve.append(equity)
    total_return = equity - 1.0

    mean_r = statistics.fmean(period_returns) if period_returns else 0.0
    stdev_r = statistics.pstdev(period_returns) if len(period_returns) > 1 else 0.0
    annualized_vol = stdev_r * math.sqrt(periods_per_year)
    sharpe = (mean_r * periods_per_year) / annualized_vol if annualized_vol > 1e-12 else None

    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, (value - peak) / peak)

    return {"total_return": total_return, "annualized_vol": annualized_vol, "sharpe": sharpe, "max_drawdown": max_drawdown}


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols WHERE active = 1 "
        "AND category NOT IN ('macro_series', 'crypto_reference') AND research_scope = 'general'"
    ).fetchall()

    closes_by_symbol: dict[str, list[float]] = {}
    dates_by_symbol: dict[str, list[str]] = {}
    for row in staging_rows:
        security_id = _security_id_for(row["symbol"], row["category"])
        bar_rows = connection.execute(
            "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
            "AND close IS NOT NULL ORDER BY time",
            (dataset_id, security_id),
        ).fetchall()
        if not bar_rows:
            continue
        closes_by_symbol[row["symbol"]] = [r["close"] for r in bar_rows]
        dates_by_symbol[row["symbol"]] = [r["time"] for r in bar_rows]

    symbols = sorted(closes_by_symbol)
    index_by_symbol = {s: {day: i for i, day in enumerate(dates_by_symbol[s])} for s in symbols}
    calendar_symbol = min(symbols, key=lambda s: (-len(dates_by_symbol[s]), s))
    calendar_dates = dates_by_symbol[calendar_symbol]
    if len(calendar_dates) < LOOKBACK_DAYS + REBALANCE_DAYS + 50:
        print(f"Insufficient history: reference calendar has {len(calendar_dates)} bars.")
        return

    rebalance_indices = list(range(LOOKBACK_DAYS, len(calendar_dates) - REBALANCE_DAYS, REBALANCE_DAYS))

    gross_returns: list[float] = []
    turnovers: list[float] = []
    previous_selection: frozenset[str] = frozenset()

    for index in rebalance_indices:
        lookback_date = calendar_dates[index - LOOKBACK_DAYS]
        start_date = calendar_dates[index]
        end_date = calendar_dates[index + REBALANCE_DAYS]
        trailing_returns = {}
        for s in symbols:
            past_index = index_by_symbol[s].get(lookback_date)
            start_index = index_by_symbol[s].get(start_date)
            if past_index is None or start_index is None:
                continue
            past_close = closes_by_symbol[s][past_index]
            now_close = closes_by_symbol[s][start_index]
            if past_close == 0:
                continue
            trailing_returns[s] = (now_close - past_close) / abs(past_close)
        if len(trailing_returns) < TOP_N:
            continue

        # Buy the biggest losers: ascending trailing return, take the bottom N.
        ranked = sorted(trailing_returns, key=lambda s: trailing_returns[s])
        selected = ranked[:TOP_N]
        if any(end_date not in index_by_symbol[s] for s in selected):
            continue
        selected_set = frozenset(selected)

        if previous_selection:
            turnovers.append(len(selected_set - previous_selection) / len(selected_set))
        else:
            turnovers.append(1.0)  # first period: the whole book is a real, real cost, not skipped
        previous_selection = selected_set

        period_returns = [
            (
                closes_by_symbol[s][index_by_symbol[s][end_date]]
                - closes_by_symbol[s][index_by_symbol[s][start_date]]
            )
            / closes_by_symbol[s][index_by_symbol[s][start_date]]
            for s in selected
            if closes_by_symbol[s][index_by_symbol[s][start_date]] != 0
        ]
        if not period_returns:
            continue
        gross_returns.append(statistics.fmean(period_returns))

    periods_per_year = 252.0 / REBALANCE_DAYS
    gross_stats = _equity_curve_stats(gross_returns, periods_per_year)
    mean_turnover = statistics.fmean(turnovers) if turnovers else 0.0

    print(f"Dataset: {dataset_id}")
    print(f"Rebalance periods: {len(gross_returns)}, mean turnover per period: {mean_turnover:.1%}")
    print()
    print("Gross (no costs):")
    print(f"  total_return={gross_stats['total_return']:+.1%}  ann_vol={gross_stats['annualized_vol']:.1%}  "
          f"sharpe={gross_stats['sharpe']:.2f}  max_drawdown={gross_stats['max_drawdown']:.1%}"
          if gross_stats["sharpe"] is not None else "  sharpe not computable")
    print()
    print("Net of real round-trip transaction cost, scaled by actual measured turnover each period:")
    for cost_bps in COST_LEVELS_BPS:
        cost_fraction = cost_bps / 10_000.0
        net_returns = [r - t * cost_fraction for r, t in zip(gross_returns, turnovers)]
        net_stats = _equity_curve_stats(net_returns, periods_per_year)
        print(
            f"  {cost_bps}bps: total_return={net_stats['total_return']:+.1%}  "
            f"sharpe={net_stats['sharpe']:.2f}  max_drawdown={net_stats['max_drawdown']:.1%}"
            if net_stats["sharpe"] is not None else f"  {cost_bps}bps: sharpe not computable"
        )


if __name__ == "__main__":
    main()
