"""Scratch script for
docs/hypotheses/asset-selection-research/sleeve-driver-decomposition.md.

H-SECT03: which single real macro driver (real yield, credit stress,
volatility, inflation expectations) actually drives each of H-SECT02's
6 confirmed sleeves, vs. the composite mixing all 13. Read-only against
the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.sleeve_driver_decomposition
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, FORWARD_WINDOWS, STRIDE_DAYS, _closes

SLEEVES = ["XLU", "XLP", "QQQ", "XLY", "DIA", "GLD"]  # H-SECT02's 6 confirmed sleeves only

DRIVERS: dict[str, int] = {
    "DFII10": 60,          # real yield -- duration sensitivity
    "BAMLH0A0HYM2": 60,    # HY credit spread -- risk-off liquidity
    "VIXCLS": 60,           # volatility -- general stress
    "T10YIE": 60,           # 10Y breakeven inflation
}


def _driver_zscore_series(connection, dataset_id: str, series_id: str, window: int) -> list[tuple[str, float]]:
    rows = connection.execute(
        "SELECT observation_date, value FROM fred_observations "
        "WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL ORDER BY observation_date",
        (dataset_id, series_id),
    ).fetchall()
    dates = [row["observation_date"] for row in rows]
    values = [row["value"] for row in rows]
    scores: list[tuple[str, float]] = []
    for i in range(window, len(values)):
        trailing = values[i - window : i]
        mean = statistics.fmean(trailing)
        stdev = statistics.pstdev(trailing)
        if stdev < 1e-9:
            continue
        scores.append((dates[i], (values[i] - mean) / stdev))
    return scores


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
    print(f"Dataset: {dataset_id}")
    print(f"{len(SLEEVES)} sleeves, {len(common_dates)} common real trading days\n")

    driver_series = {series_id: _driver_zscore_series(connection, dataset_id, series_id, window) for series_id, window in DRIVERS.items()}
    for series_id, series in driver_series.items():
        print(f"{series_id}: {len(series)} real z-score observations")
    print()

    results: list[dict] = []
    for sleeve in SLEEVES:
        for series_id, series in driver_series.items():
            for forward_days in FORWARD_WINDOWS:
                driver_scores: list[float] = []
                relative_returns: list[float] = []
                for i in range(0, len(common_dates) - forward_days, STRIDE_DAYS):
                    anchor_date = common_dates[i]
                    candidates = [(d, s) for d, s in series if d <= anchor_date]
                    if not candidates:
                        continue
                    _, driver_z = max(candidates, key=lambda pair: pair[0])

                    start_date, end_date = common_dates[i], common_dates[i + forward_days]
                    sleeve_return = closes[sleeve][end_date] / closes[sleeve][start_date] - 1.0
                    benchmark_return = closes[BENCHMARK][end_date] / closes[BENCHMARK][start_date] - 1.0
                    driver_scores.append(driver_z)
                    relative_returns.append(sleeve_return - benchmark_return)

                n = len(driver_scores)
                if n < 3:
                    continue
                correlation, p_value = pearson_significance(driver_scores, relative_returns)
                results.append({
                    "sleeve": sleeve, "driver": series_id, "forward_days": forward_days,
                    "n": n, "correlation": correlation, "p_value": p_value,
                })

    adjusted, significant = benjamini_hochberg([r["p_value"] for r in results])
    for r, adj_p, sig in zip(results, adjusted, significant):
        r["adjusted_p"] = adj_p
        r["significant"] = sig

    print(f"=== {len(results)} tests (sleeves x drivers x windows), Benjamini-Hochberg corrected ===\n")
    for r in sorted(results, key=lambda r: r["adjusted_p"]):
        flag = "SIGNIFICANT" if r["significant"] else "not significant"
        print(f"{r['sleeve']:5s} {r['driver']:14s} {r['forward_days']:3d}d  n={r['n']:3d}  "
              f"r={r['correlation']:+.3f}  adj_p={r['adjusted_p']:.4f}  ({flag})")

    sig_count = sum(1 for r in results if r["significant"])
    print(f"\n{sig_count} of {len(results)} significant after correction "
          f"(chance alone at alpha=0.05 would produce ~{0.05 * len(results):.1f})\n")

    print("=== Strongest driver per sleeve (by |r| among significant results) ===")
    for sleeve in SLEEVES:
        sleeve_hits = [r for r in results if r["sleeve"] == sleeve and r["significant"]]
        if not sleeve_hits:
            print(f"{sleeve}: no driver survived correction")
            continue
        best = max(sleeve_hits, key=lambda r: abs(r["correlation"]))
        print(f"{sleeve}: {best['driver']} ({best['forward_days']}d, r={best['correlation']:+.3f}, adj_p={best['adjusted_p']:.4f})")


if __name__ == "__main__":
    main()
