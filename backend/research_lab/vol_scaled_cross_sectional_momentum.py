"""Scratch script for docs/hypotheses/vol-scaled-cross-sectional-momentum.md
(H-VOLSCALE01).

Two parallel real walk-forward equity curves over the identical dataset,
identical ranking function, identical top_n/rebalance_days: baseline
(constant exposure, reproducing the real production backtest) vs.
vol-scaled (exposure reduced when the selected symbols' swing structure is
broken, per H-DOW02's confirmed volatility finding). Imports the real
compute_cross_section_v2 from engine/ (allowed, one-way, per
backend/research_lab/README.md) -- never the production DB, never writes
anywhere.

Run: .venv/bin/python -m backend.research_lab.vol_scaled_cross_sectional_momentum
"""

from __future__ import annotations

import math
import statistics

from backend.database import connect, resolve_database_path
from backend.engine.factors.momentum_v2 import compute_cross_section_v2
from backend.engine.factors.types import Bar, InsufficientPriceDataError

TOP_N = 5
REBALANCE_DAYS = 21
SWING_WINDOW = 5  # identical to dow_theory_trend_structure.py / dow_theory_risk_state.py
BROKEN_EXPOSURE_HAIRCUT = 0.5  # disclosed, hand-picked, naive -- not fit to this universe


def _security_id_for(symbol: str, category: str) -> str:
    # Reproduced, not imported -- see backend/research_lab/README.md.
    slug = symbol.lower().replace("-", "")
    if category == "crypto_reference":
        return f"ref-{slug}"
    if category == "mega_cap_equity":
        return f"us-equity-{slug}"
    return f"us-etf-{symbol.lower()}"


def _swing_points(values: list[float], window: int, is_high: bool) -> tuple[list[int], list[float]]:
    # Identical to dow_theory_trend_structure.py's detector.
    n = len(values)
    indices: list[int] = []
    swing_values: list[float] = []
    for j in range(window, n - window):
        segment = values[j - window : j + window + 1]
        if is_high:
            if values[j] == max(segment):
                indices.append(j)
                swing_values.append(values[j])
        else:
            if values[j] == min(segment):
                indices.append(j)
                swing_values.append(values[j])
    return indices, swing_values


def _is_structure_broken(highs: list[float], lows: list[float], as_of_index: int) -> bool:
    """Real point-in-time structure state, using only bars up to and
    including as_of_index -- no look-ahead, same rule H-DOW02 confirmed."""

    window = SWING_WINDOW
    if as_of_index < 2 * window:
        return False  # not enough history yet to have two confirmed swings; treat as intact (no haircut)
    high_slice = highs[: as_of_index + 1]
    low_slice = lows[: as_of_index + 1]
    swing_high_idx, swing_high_val = _swing_points(high_slice, window, is_high=True)
    swing_low_idx, swing_low_val = _swing_points(low_slice, window, is_high=False)
    if len(swing_high_val) < 2 or len(swing_low_val) < 2:
        return False
    intact = swing_high_val[-1] > swing_high_val[-2] and swing_low_val[-1] > swing_low_val[-2]
    return not intact


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

    return {
        "total_return": total_return,
        "annualized_vol": annualized_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
    }


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

    bars_by_symbol: dict[str, list[Bar]] = {}
    highs_by_symbol: dict[str, list[float]] = {}
    lows_by_symbol: dict[str, list[float]] = {}
    for row in staging_rows:
        security_id = _security_id_for(row["symbol"], row["category"])
        bar_rows = connection.execute(
            "SELECT time, close, high, low FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
            "AND close IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL ORDER BY time",
            (dataset_id, security_id),
        ).fetchall()
        if not bar_rows:
            continue
        bars_by_symbol[row["symbol"]] = [Bar(time=r["time"], close=r["close"]) for r in bar_rows]
        highs_by_symbol[row["symbol"]] = [r["high"] for r in bar_rows]
        lows_by_symbol[row["symbol"]] = [r["low"] for r in bar_rows]

    symbols = sorted(bars_by_symbol)
    dates_by_symbol = {s: [bar.time for bar in bars_by_symbol[s]] for s in symbols}
    index_by_symbol = {s: {day: i for i, day in enumerate(dates_by_symbol[s])} for s in symbols}
    calendar_symbol = min(symbols, key=lambda s: (-len(dates_by_symbol[s]), s))
    calendar_dates = dates_by_symbol[calendar_symbol]
    if len(calendar_dates) < 300:
        print(f"Insufficient history: reference calendar has {len(calendar_dates)} bars, need >= 300.")
        return

    rebalance_indices = list(range(252, len(calendar_dates) - REBALANCE_DAYS, REBALANCE_DAYS))
    if len(rebalance_indices) < 4:
        print(f"Insufficient rebalance points: only {len(rebalance_indices)}.")
        return

    baseline_returns: list[float] = []
    scaled_returns: list[float] = []
    exposures: list[float] = []

    for index in rebalance_indices:
        start_date = calendar_dates[index]
        end_date = calendar_dates[index + REBALANCE_DAYS]
        truncated = {}
        formation_index = {}
        for symbol in symbols:
            symbol_index = index_by_symbol[symbol].get(start_date)
            if symbol_index is None or symbol_index < 252:
                continue
            formation_index[symbol] = symbol_index
            truncated[symbol] = bars_by_symbol[symbol][: symbol_index + 1]
        if len(truncated) < TOP_N:
            continue
        try:
            ranked, _weights = compute_cross_section_v2(truncated)
        except InsufficientPriceDataError:
            continue
        selected = [item.symbol for item in ranked[:TOP_N]]
        if len(selected) < TOP_N or any(end_date not in index_by_symbol[s] for s in selected):
            continue

        selected_returns = [
            (
                bars_by_symbol[s][index_by_symbol[s][end_date]].close
                - bars_by_symbol[s][formation_index[s]].close
            )
            / bars_by_symbol[s][formation_index[s]].close
            for s in selected
            if bars_by_symbol[s][formation_index[s]].close != 0
        ]
        if not selected_returns:
            continue
        period_return = statistics.fmean(selected_returns)
        baseline_returns.append(period_return)

        broken_count = sum(
            1
            for s in selected
            if _is_structure_broken(highs_by_symbol[s], lows_by_symbol[s], formation_index[s])
        )
        broken_fraction = broken_count / len(selected)
        exposure = 1.0 - BROKEN_EXPOSURE_HAIRCUT * broken_fraction
        exposures.append(exposure)
        scaled_returns.append(period_return * exposure)

    periods_per_year = 252.0 / REBALANCE_DAYS
    baseline_stats = _equity_curve_stats(baseline_returns, periods_per_year)
    scaled_stats = _equity_curve_stats(scaled_returns, periods_per_year)
    # Attribution check: is the scaled version's drawdown improvement real
    # (specifically timed to broken-structure periods), or just an artifact
    # of being less invested on average? Compare against a naive CONSTANT
    # exposure at the same mean level, with no timing at all.
    mean_exposure = statistics.fmean(exposures)
    constant_scaled_returns = [r * mean_exposure for r in baseline_returns]
    constant_stats = _equity_curve_stats(constant_scaled_returns, periods_per_year)

    print(f"Dataset: {dataset_id}")
    print(f"Rebalance periods: {len(baseline_returns)}, mean exposure (scaled version): {statistics.fmean(exposures):.2%}")
    print()
    print("Baseline (constant exposure, reproducing the real production backtest):")
    print(f"  total_return={baseline_stats['total_return']:+.1%}  ann_vol={baseline_stats['annualized_vol']:.1%}  "
          f"sharpe={baseline_stats['sharpe']:.2f}  max_drawdown={baseline_stats['max_drawdown']:.1%}"
          if baseline_stats["sharpe"] is not None else "  sharpe not computable")
    print()
    print(f"Vol-scaled (exposure cut up to {BROKEN_EXPOSURE_HAIRCUT:.0%} when selected symbols' structure is broken):")
    print(f"  total_return={scaled_stats['total_return']:+.1%}  ann_vol={scaled_stats['annualized_vol']:.1%}  "
          f"sharpe={scaled_stats['sharpe']:.2f}  max_drawdown={scaled_stats['max_drawdown']:.1%}"
          if scaled_stats["sharpe"] is not None else "  sharpe not computable")
    print()
    print(f"Attribution check -- constant {mean_exposure:.1%} exposure, same average level, no structure timing at all:")
    print(f"  total_return={constant_stats['total_return']:+.1%}  ann_vol={constant_stats['annualized_vol']:.1%}  "
          f"sharpe={constant_stats['sharpe']:.2f}  max_drawdown={constant_stats['max_drawdown']:.1%}"
          if constant_stats["sharpe"] is not None else "  sharpe not computable")


if __name__ == "__main__":
    main()
