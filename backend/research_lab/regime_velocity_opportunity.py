"""Scratch script for
docs/hypotheses/asset-selection-research/regime-velocity-opportunity.md.

H-SECT08: does the macro composite's *direction* (velocity,
acceleration, days since a tercile transition) predict cross-sectional
opportunity beyond what its static level already does -- a different
mechanism than H-SECT04's rejected sector tilt, and independent of
H-SECT07's ambiguous result. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.regime_velocity_opportunity
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.engine.regime.scoring_v3 import CALM_TERCILE_CUTOFF, STRESSED_TERCILE_CUTOFF
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, SLEEVES, STRIDE_DAYS, _closes, _macro_composite_series

VELOCITY_WINDOW = 63  # trailing days for velocity/acceleration, matches H-SECT07's state window
FORWARD_WINDOWS = (63, 126)


def _regime_bucket(composite: float) -> str:
    if composite <= STRESSED_TERCILE_CUTOFF:
        return "stressed"
    if composite >= CALM_TERCILE_CUTOFF:
        return "calm"
    return "neutral"


def _daily_composite(common_dates: list[str], composite_series: list[tuple[str, float]]) -> list[float]:
    """Forward-filled real composite value at every real trading day --
    the most recent point-in-time anchor at or before that day, O(n+m)
    via a moving pointer, not a fresh scan per date."""
    sorted_series = sorted(composite_series, key=lambda pair: pair[0])
    daily: list[float] = []
    pointer = -1
    for date in common_dates:
        while pointer + 1 < len(sorted_series) and sorted_series[pointer + 1][0] <= date:
            pointer += 1
        daily.append(sorted_series[pointer][1] if pointer >= 0 else float("nan"))
    return daily


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    all_symbols = [BENCHMARK] + SLEEVES
    closes = {symbol: _closes(connection, dataset_id, symbol) for symbol in all_symbols}
    common_dates = sorted(set.intersection(*(set(c) for c in closes.values())))
    composite_series = _macro_composite_series(connection, dataset_id)
    daily_composite = _daily_composite(common_dates, composite_series)

    bucket = [_regime_bucket(v) if v == v else None for v in daily_composite]  # v==v False only for nan
    days_since_transition: list[int] = []
    streak = 0
    for i in range(len(bucket)):
        if i == 0 or bucket[i] != bucket[i - 1]:
            streak = 0
        else:
            streak += 1
        days_since_transition.append(streak)

    print(f"Dataset: {dataset_id}")
    print(f"{len(SLEEVES)} sleeves, {len(common_dates)} common real trading days, velocity window={VELOCITY_WINDOW}d\n")

    results: list[dict] = []
    for forward_days in FORWARD_WINDOWS:
        velocity_series: list[float] = []
        acceleration_series: list[float] = []
        transition_series: list[float] = []
        forward_spreads: list[float] = []

        start = 2 * VELOCITY_WINDOW
        for i in range(start, len(common_dates) - forward_days, STRIDE_DAYS):
            if daily_composite[i] != daily_composite[i] or daily_composite[i - VELOCITY_WINDOW] != daily_composite[i - VELOCITY_WINDOW] or daily_composite[i - 2 * VELOCITY_WINDOW] != daily_composite[i - 2 * VELOCITY_WINDOW]:
                continue
            velocity = daily_composite[i] - daily_composite[i - VELOCITY_WINDOW]
            prior_velocity = daily_composite[i - VELOCITY_WINDOW] - daily_composite[i - 2 * VELOCITY_WINDOW]
            acceleration = velocity - prior_velocity

            start_date, end_date = common_dates[i], common_dates[i + forward_days]
            forward_returns = {s: closes[s][end_date] / closes[s][start_date] - 1.0 for s in SLEEVES}
            ranked = sorted(SLEEVES, key=lambda s: forward_returns[s], reverse=True)
            forward_spread = (
                statistics.fmean(forward_returns[s] for s in ranked[:3])
                - statistics.fmean(forward_returns[s] for s in ranked[-3:])
            )

            velocity_series.append(velocity)
            acceleration_series.append(acceleration)
            transition_series.append(float(days_since_transition[i]))
            forward_spreads.append(forward_spread)

        n = len(forward_spreads)
        print(f"=== Forward window {forward_days}d: n={n} real monthly-strided observations ===")
        for name, series in [("velocity", velocity_series), ("acceleration", acceleration_series), ("days_since_transition", transition_series)]:
            if len(series) < 3:
                continue
            r, p = pearson_significance(series, forward_spreads)
            results.append({"metric": name, "forward_days": forward_days, "n": len(series), "correlation": r, "p_value": p})

    adjusted, significant = benjamini_hochberg([r["p_value"] for r in results])
    for r, adj_p, sig in zip(results, adjusted, significant):
        r["adjusted_p"] = adj_p
        r["significant"] = sig

    print(f"\n=== {len(results)} tests (velocity-family variable x forward window), Benjamini-Hochberg corrected ===\n")
    for r in sorted(results, key=lambda r: r["adjusted_p"]):
        flag = "SIGNIFICANT" if r["significant"] else "not significant"
        print(f"{r['metric']:22s} {r['forward_days']:3d}d  n={r['n']:3d}  r={r['correlation']:+.3f}  "
              f"p={r['p_value']:.4f}  adj_p={r['adjusted_p']:.4f}  ({flag})")

    sig_count = sum(1 for r in results if r["significant"])
    print(f"\n{sig_count} of {len(results)} significant after correction "
          f"(chance alone at alpha=0.05 would produce ~{0.05 * len(results):.1f})")


if __name__ == "__main__":
    main()
