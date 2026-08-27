"""Scratch script for
docs/hypotheses/asset-selection-research/beta-adjusted-regime-sensitivity.md.

H-SECT05: does H-SECT02's regime-sleeve correlation survive controlling
for each sleeve's own trailing beta to SPY, or was it substantially
rediscovering "low-beta sleeves cushion a falling market, and the
composite predicts falling markets"? Read-only against the sealed
dataset.

Run: .venv/bin/python -m backend.research_lab.beta_adjusted_regime_sensitivity
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, FORWARD_WINDOWS, SLEEVES, STRIDE_DAYS, _closes, _macro_composite_series

BETA_WINDOW = 252  # ~1 year of daily returns, standard convention, not tuned


def _daily_returns(closes: dict[str, float], dates: list[str]) -> dict[str, float]:
    returns: dict[str, float] = {}
    for i in range(1, len(dates)):
        returns[dates[i]] = closes[dates[i]] / closes[dates[i - 1]] - 1.0
    return returns


def _trailing_beta(sleeve_returns: dict[str, float], spy_returns: dict[str, float], dates: list[str], anchor_index: int) -> float | None:
    if anchor_index < BETA_WINDOW:
        return None
    window_dates = dates[anchor_index - BETA_WINDOW + 1 : anchor_index + 1]
    sleeve_series = [sleeve_returns[d] for d in window_dates]
    spy_series = [spy_returns[d] for d in window_dates]
    spy_mean = statistics.fmean(spy_series)
    spy_var = statistics.fmean([(s - spy_mean) ** 2 for s in spy_series])
    if spy_var < 1e-12:
        return None
    sleeve_mean = statistics.fmean(sleeve_series)
    covariance = statistics.fmean([(sleeve_series[i] - sleeve_mean) * (spy_series[i] - spy_mean) for i in range(len(spy_series))])
    return covariance / spy_var


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

    spy_daily = _daily_returns(closes[BENCHMARK], common_dates)
    sleeve_daily = {sleeve: _daily_returns(closes[sleeve], common_dates) for sleeve in SLEEVES}
    return_dates = common_dates[1:]  # first date has no daily return
    return_date_index = {d: i for i, d in enumerate(return_dates)}

    print(f"Dataset: {dataset_id}")
    print(f"{len(SLEEVES)} sleeves, {len(common_dates)} common real trading days, beta window={BETA_WINDOW}d\n")

    results: list[dict] = []
    for sleeve in SLEEVES:
        for forward_days in FORWARD_WINDOWS:
            composite_scores: list[float] = []
            alpha_returns: list[float] = []
            for i in range(0, len(common_dates) - forward_days, STRIDE_DAYS):
                anchor_date = common_dates[i]
                return_index = return_date_index.get(anchor_date)
                if return_index is None:
                    continue
                beta = _trailing_beta(sleeve_daily[sleeve], spy_daily, return_dates, return_index)
                if beta is None:
                    continue

                candidates = [(d, s) for d, s in composite_series if d <= anchor_date]
                if not candidates:
                    continue
                _, composite = max(candidates, key=lambda pair: pair[0])

                start_date, end_date = common_dates[i], common_dates[i + forward_days]
                sleeve_return = closes[sleeve][end_date] / closes[sleeve][start_date] - 1.0
                benchmark_return = closes[BENCHMARK][end_date] / closes[BENCHMARK][start_date] - 1.0
                composite_scores.append(composite)
                alpha_returns.append(sleeve_return - beta * benchmark_return)

            n = len(composite_scores)
            if n < 3:
                continue
            correlation, p_value = pearson_significance(composite_scores, alpha_returns)
            results.append({"sleeve": sleeve, "forward_days": forward_days, "n": n, "correlation": correlation, "p_value": p_value})

    adjusted, significant = benjamini_hochberg([r["p_value"] for r in results])
    for r, adj_p, sig in zip(results, adjusted, significant):
        r["adjusted_p"] = adj_p
        r["significant"] = sig

    # H-SECT02's original full-sample results, for a direct side-by-side
    original_by_key = {}
    for sleeve in SLEEVES:
        for forward_days in FORWARD_WINDOWS:
            composite_scores2: list[float] = []
            relative_returns2: list[float] = []
            for i in range(0, len(common_dates) - forward_days, STRIDE_DAYS):
                anchor_date = common_dates[i]
                candidates = [(d, s) for d, s in composite_series if d <= anchor_date]
                if not candidates:
                    continue
                _, composite = max(candidates, key=lambda pair: pair[0])
                start_date, end_date = common_dates[i], common_dates[i + forward_days]
                sleeve_return = closes[sleeve][end_date] / closes[sleeve][start_date] - 1.0
                benchmark_return = closes[BENCHMARK][end_date] / closes[BENCHMARK][start_date] - 1.0
                composite_scores2.append(composite)
                relative_returns2.append(sleeve_return - benchmark_return)
            if len(composite_scores2) >= 3:
                r2, p2 = pearson_significance(composite_scores2, relative_returns2)
                original_by_key[(sleeve, forward_days)] = (r2, p2)

    print(f"=== {len(results)} beta-adjusted tests, Benjamini-Hochberg corrected -- vs. H-SECT02's raw results ===\n")
    for r in sorted(results, key=lambda r: r["adjusted_p"]):
        flag = "SIGNIFICANT" if r["significant"] else "not significant"
        orig = original_by_key.get((r["sleeve"], r["forward_days"]))
        orig_str = f"raw r={orig[0]:+.3f}" if orig else "raw n/a"
        print(f"{r['sleeve']:5s} {r['forward_days']:3d}d  n={r['n']:3d}  beta-adj r={r['correlation']:+.3f}  "
              f"adj_p={r['adjusted_p']:.4f}  ({flag})  |  {orig_str}")

    sig_count = sum(1 for r in results if r["significant"])
    print(f"\n{sig_count} of {len(results)} significant after beta adjustment "
          f"(H-SECT02 raw had 11 of 24; chance alone predicts ~{0.05 * len(results):.1f})")


if __name__ == "__main__":
    main()
