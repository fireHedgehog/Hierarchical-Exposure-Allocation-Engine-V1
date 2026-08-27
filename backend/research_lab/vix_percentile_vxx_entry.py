"""Scratch script for
docs/hypotheses/timing-research/vix-percentile-vxx-entry.md.

H-TIME01: does a real, quantified "how suppressed is VIX right now"
state (percentile within its own trailing history, or days since it
was last elevated) predict VXX's forward return better than VXX's own
unconditional (structurally negative) average. Read-only against the
sealed dataset.

Run: .venv/bin/python -m backend.research_lab.vix_percentile_vxx_entry
"""

from __future__ import annotations

import bisect
import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

STATE_WINDOW = 252  # trailing days for VIX percentile, standard 1-year convention
ELEVATED_THRESHOLD = 20.0  # disclosed, standard practitioner "elevated VIX" level, not tuned
FORWARD_WINDOWS = (21, 63)
STRIDE_DAYS = 21


def _percentile_rank(value: float, trailing_values: list[float]) -> float | None:
    if not trailing_values:
        return None
    below = sum(1 for v in trailing_values if v <= value)
    return 100.0 * below / len(trailing_values)


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    vix_rows = connection.execute(
        "SELECT observation_date, value FROM fred_observations "
        "WHERE dataset_snapshot_id = ? AND series_id = 'VIXCLS' AND value IS NOT NULL ORDER BY observation_date",
        (dataset_id,),
    ).fetchall()
    vix_dates = [row["observation_date"] for row in vix_rows]
    vix_values = [row["value"] for row in vix_rows]

    vxx_rows = connection.execute(
        "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = 'us-etf-vxx' "
        "AND close IS NOT NULL ORDER BY time",
        (dataset_id,),
    ).fetchall()
    vxx_dates = [row["time"] for row in vxx_rows]
    vxx_closes = {row["time"]: row["close"] for row in vxx_rows}

    print(f"Dataset: {dataset_id}")
    print(f"VIXCLS: {len(vix_dates)} real observations, {vix_dates[0]} to {vix_dates[-1]}")
    print(f"VXX: {len(vxx_dates)} real bars, {vxx_dates[0]} to {vxx_dates[-1]}\n")

    days_since_elevated_by_date: dict[str, float] = {}
    streak: float | None = None
    for d, v in zip(vix_dates, vix_values):
        if v > ELEVATED_THRESHOLD:
            streak = 0.0
        elif streak is not None:
            streak += 1.0
        days_since_elevated_by_date[d] = streak

    results: list[dict] = []
    for forward_days in FORWARD_WINDOWS:
        percentile_series: list[float] = []
        elevated_series: list[float] = []
        forward_returns: list[float] = []

        for i in range(0, len(vxx_dates) - forward_days, STRIDE_DAYS):
            anchor_date, end_date = vxx_dates[i], vxx_dates[i + forward_days]
            start_close = vxx_closes[anchor_date]
            end_close = vxx_closes[end_date]
            if start_close == 0:
                continue

            pos = bisect.bisect_right(vix_dates, anchor_date) - 1
            if pos < STATE_WINDOW:
                continue
            trailing_vix = vix_values[pos - STATE_WINDOW : pos]
            percentile = _percentile_rank(vix_values[pos], trailing_vix)
            days_elevated = days_since_elevated_by_date.get(vix_dates[pos])
            if percentile is None or days_elevated is None:
                continue

            percentile_series.append(percentile)
            elevated_series.append(days_elevated)
            forward_returns.append(end_close / start_close - 1.0)

        baseline_returns = [
            vxx_closes[vxx_dates[i + forward_days]] / vxx_closes[vxx_dates[i]] - 1.0
            for i in range(len(vxx_dates) - forward_days)
            if vxx_closes[vxx_dates[i]] != 0
        ]
        baseline_mean = statistics.fmean(baseline_returns)

        n = len(forward_returns)
        print(f"=== Forward window {forward_days}d: n={n} monthly-strided obs ===")
        print(f"Unconditional baseline (all {len(baseline_returns)} overlapping days): mean={baseline_mean:+.2%}")
        for name, series in [("vix_percentile", percentile_series), ("days_since_elevated", elevated_series)]:
            if len(series) < 3:
                continue
            r, p = pearson_significance(series, forward_returns)
            results.append({"metric": name, "forward_days": forward_days, "n": len(series), "correlation": r, "p_value": p})

        paired = sorted(zip(percentile_series, forward_returns))
        q = max(1, len(paired) // 4)
        bottom, top = [r for _, r in paired[:q]], [r for _, r in paired[-q:]]
        if bottom and top:
            print(f"  bottom-quartile VIX-percentile (most suppressed): n={len(bottom)}, mean fwd return={statistics.fmean(bottom):+.2%}")
            print(f"  top-quartile VIX-percentile (most elevated):      n={len(top)}, mean fwd return={statistics.fmean(top):+.2%}")
        print()

    adjusted, significant = benjamini_hochberg([r["p_value"] for r in results])
    for r, adj_p, sig in zip(results, adjusted, significant):
        r["adjusted_p"] = adj_p
        r["significant"] = sig

    print(f"=== {len(results)} tests, Benjamini-Hochberg corrected ===\n")
    for r in sorted(results, key=lambda r: r["adjusted_p"]):
        flag = "SIGNIFICANT" if r["significant"] else "not significant"
        print(f"{r['metric']:20s} {r['forward_days']:3d}d  n={r['n']:3d}  r={r['correlation']:+.3f}  "
              f"p={r['p_value']:.4f}  adj_p={r['adjusted_p']:.4f}  ({flag})")


if __name__ == "__main__":
    main()
