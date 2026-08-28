"""Scratch script for
docs/hypotheses/timing-research/broad-index-exposure-policy.md (H-TIME02).

Real checkpoint: does a slow, disclosed, price-only exposure policy
(trend state x volatility state -> exposure level) beat static
buy-and-hold on the real FULL PATH -- max drawdown, time underwater,
crisis-window behavior -- at an acceptable real CAGR cost, for SPY and
QQQ separately, stable across nearby moving-average lengths, and
holding out-of-sample. A deliberately different evaluation frame from
every other trend test in this project: full-path portfolio
statistics, not point-forecast IC. Read-only against the sealed
dataset.

Run: .venv/bin/python -m backend.research_lab.broad_index_exposure_policy_backtest
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.research_lab.regime_conditioned_sleeve_return import _closes
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE

SYMBOLS = ["SPY", "QQQ"]
MA_LENGTHS = [150, 180, 200, 220]
VOL_WINDOW = 21          # trailing realized-vol window, real trading days
VOL_HISTORY = 252        # trailing window over which the vol percentile is measured
VOL_ELEVATED_PCT = 0.75  # top quartile of the series' own trailing vol distribution

# Real, disclosed, hand-picked exposure table -- not fit to any result.
EXPOSURE_TABLE = {
    ("above", "calm"): 1.0,
    ("above", "elevated"): 0.7,
    ("below", "calm"): 0.5,
    ("below", "elevated"): 0.3,
}

CRISIS_WINDOWS = [
    ("2008 crisis", "2007-10-01", "2009-03-31"),
    ("2020 COVID crash", "2020-02-01", "2020-04-30"),
    ("2022 hiking bear", "2022-01-01", "2022-10-31"),
]


def _daily_returns(closes_ordered: list[float]) -> list[float]:
    return [closes_ordered[i] / closes_ordered[i - 1] - 1.0 for i in range(1, len(closes_ordered))]


def _trailing_vol_series(returns: list[float]) -> list[float | None]:
    """Annualized realized vol over the trailing VOL_WINDOW days, indexed the
    same as `returns` (None until enough history exists)."""
    out: list[float | None] = []
    for i in range(len(returns)):
        if i + 1 < VOL_WINDOW:
            out.append(None)
            continue
        window = returns[i + 1 - VOL_WINDOW : i + 1]
        out.append(statistics.pstdev(window) * (252 ** 0.5))
    return out


def _exposure_series(dates: list[str], closes_ordered: list[float], ma_length: int) -> list[float | None]:
    """Exposure decided using only information available AT THE CLOSE of each
    date -- applied to the FOLLOWING day's return by the caller, no lookahead."""
    returns = _daily_returns(closes_ordered)
    vol_series = _trailing_vol_series(returns)

    exposures: list[float | None] = [None]  # no return exists before index 0
    for i in range(len(returns)):
        price_idx = i + 1  # returns[i] is the return ending at closes_ordered[i+1]
        if price_idx < ma_length or vol_series[i] is None:
            exposures.append(None)
            continue

        ma = sum(closes_ordered[price_idx - ma_length + 1 : price_idx + 1]) / ma_length
        trend = "above" if closes_ordered[price_idx] > ma else "below"

        history_start = max(0, i - VOL_HISTORY + 1)
        history = [v for v in vol_series[history_start : i + 1] if v is not None]
        if len(history) < VOL_WINDOW:
            exposures.append(None)
            continue
        sorted_history = sorted(history)
        rank = sum(1 for v in sorted_history if v <= vol_series[i]) / len(sorted_history)
        vol_state = "elevated" if rank >= VOL_ELEVATED_PCT else "calm"

        exposures.append(EXPOSURE_TABLE[(trend, vol_state)])
    return exposures


def _path_stats(dates: list[str], closes_ordered: list[float], exposures: list[float | None], date_filter=None) -> dict:
    """Real full-path statistics. Exposure decided at close of day i-1 is
    applied to day i's return (no lookahead). `date_filter(date) -> bool`
    restricts which days' RETURNS count, for in-sample/OOS/crisis slicing --
    the exposure decision itself always uses the full real history up to
    that point."""
    period_returns: list[float] = []
    bh_returns: list[float] = []
    exposure_path: list[float] = []
    whipsaws = 0
    turnover = 0.0
    previous_exposure: float | None = None

    for i in range(1, len(closes_ordered)):
        exposure = exposures[i - 1]  # decided at yesterday's close
        raw_return = closes_ordered[i] / closes_ordered[i - 1] - 1.0
        if exposure is None:
            previous_exposure = None
            continue
        if previous_exposure is not None:
            turnover += abs(exposure - previous_exposure)
            if exposure != previous_exposure:
                whipsaws += 1
        previous_exposure = exposure

        if date_filter is not None and not date_filter(dates[i]):
            continue
        period_returns.append(exposure * raw_return)
        bh_returns.append(raw_return)
        exposure_path.append(exposure)

    if not period_returns:
        return {"days": 0}

    def _curve_stats(returns: list[float]) -> dict:
        cumulative = [1.0]
        for r in returns:
            cumulative.append(cumulative[-1] * (1.0 + r))
        peak = cumulative[0]
        max_dd = 0.0
        underwater = 0
        max_underwater = 0
        for value in cumulative:
            if value >= peak:
                peak = value
                underwater = 0
            else:
                underwater += 1
                max_underwater = max(max_underwater, underwater)
            max_dd = min(max_dd, (value - peak) / peak)
        mean_r = statistics.fmean(returns)
        stdev_r = statistics.pstdev(returns)
        sharpe = (mean_r / stdev_r) * (252 ** 0.5) if stdev_r > 1e-9 else float("nan")
        years = len(returns) / 252
        cagr = (cumulative[-1] ** (1 / years)) - 1.0 if years > 0 and cumulative[-1] > 0 else float("nan")
        return {
            "cagr": cagr, "sharpe": sharpe, "max_drawdown": max_dd,
            "time_underwater_days": max_underwater, "cumulative_return": cumulative[-1] - 1.0,
        }

    policy = _curve_stats(period_returns)
    bh = _curve_stats(bh_returns)
    return {
        "days": len(period_returns),
        "policy": policy, "buy_and_hold": bh,
        "turnover": turnover, "whipsaws": whipsaws,
        "mean_exposure": statistics.fmean(exposure_path),
    }


def _print_stats(label: str, stats_dict: dict) -> None:
    if stats_dict["days"] == 0:
        print(f"  {label:26s}: no real days in this window")
        return
    p, b = stats_dict["policy"], stats_dict["buy_and_hold"]
    print(f"  {label:26s}: {stats_dict['days']:5d}d  "
          f"policy CAGR={p['cagr']:+.2%} Sharpe={p['sharpe']:.2f} maxDD={p['max_drawdown']:.2%} underwater={p['time_underwater_days']}d  |  "
          f"B&H CAGR={b['cagr']:+.2%} Sharpe={b['sharpe']:.2f} maxDD={b['max_drawdown']:.2%} underwater={b['time_underwater_days']}d")


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]
    print(f"Dataset: {dataset_id}\n")

    for symbol in SYMBOLS:
        closes = _closes(connection, dataset_id, symbol)
        dates = sorted(closes)
        closes_ordered = [closes[d] for d in dates]
        print(f"=== {symbol}: {len(dates)} real daily bars, {dates[0]} to {dates[-1]} ===\n")

        for ma_length in MA_LENGTHS:
            print(f"-- MA length {ma_length} --")
            exposures = _exposure_series(dates, closes_ordered, ma_length)

            full = _path_stats(dates, closes_ordered, exposures)
            in_sample = _path_stats(dates, closes_ordered, exposures, date_filter=lambda d: d < SPLIT_DATE)
            oos = _path_stats(dates, closes_ordered, exposures, date_filter=lambda d: d >= SPLIT_DATE)
            _print_stats("FULL SAMPLE", full)
            _print_stats("IN-SAMPLE (pre-2019)", in_sample)
            _print_stats("OUT-OF-SAMPLE (2019+)", oos)
            if full["days"]:
                print(f"  {'turnover / whipsaws / mean exposure':26s}: {full['turnover']:.1f} / {full['whipsaws']} / {full['mean_exposure']:.2f}")

                # Real check against the H-SECT04 trap: a CONSTANT multiplier at
                # the same mean exposure only scales return and vol together and
                # cannot change Sharpe -- so if Sharpe still improves here, that's
                # real evidence of state-dependent timing value, not an artifact
                # of simply being less invested on average.
                static_exposures: list[float | None] = [full["mean_exposure"] if e is not None else None for e in exposures]
                static_full = _path_stats(dates, closes_ordered, static_exposures)
                sp = static_full["policy"]
                label = f"vs. static {full['mean_exposure']:.2f}x (same avg exposure, no timing)"
                print(f"  {label:26s}: Sharpe={sp['sharpe']:.2f} maxDD={sp['max_drawdown']:.2%}  "
                      f"(state-dependent policy: Sharpe={full['policy']['sharpe']:.2f} maxDD={full['policy']['max_drawdown']:.2%})")
            print()

        print(f"  -- {symbol} crisis windows (MA=200 only, the mid-parameter choice) --")
        exposures_200 = _exposure_series(dates, closes_ordered, 200)
        for label, start, end in CRISIS_WINDOWS:
            window_stats = _path_stats(dates, closes_ordered, exposures_200, date_filter=lambda d, s=start, e=end: s <= d <= e)
            if window_stats["days"] == 0:
                print(f"  {label:20s}: no real overlap with this symbol's history")
                continue
            p, b = window_stats["policy"], window_stats["buy_and_hold"]
            print(f"  {label:20s}: policy cumulative={p['cumulative_return']:+.1%} maxDD={p['max_drawdown']:.1%}  |  "
                  f"B&H cumulative={b['cumulative_return']:+.1%} maxDD={b['max_drawdown']:.1%}")
        print()


if __name__ == "__main__":
    main()
