"""Scratch script for
docs/hypotheses/asset-selection-research/sleeve-dispersion-opportunity.md.

H-SECT07: does real, currently-observable cross-sectional dispersion
among the 12 sleeves predict how much real differentiation exists in
the forward period -- the "is there an opportunity to select at all"
gate, asked before "which sleeve wins" (already rejected at the trend
level, H-SECT01). Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.sleeve_dispersion_opportunity
"""

from __future__ import annotations

import statistics
from itertools import combinations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, SLEEVES, STRIDE_DAYS, _closes

STATE_WINDOW = 63  # trailing window for dispersion/correlation state, matches this folder's forward windows
FORWARD_WINDOWS = (63, 126)


def _daily_returns(closes: dict[str, float], dates: list[str]) -> dict[str, float]:
    return {dates[i]: closes[dates[i]] / closes[dates[i - 1]] - 1.0 for i in range(1, len(dates))}


def _trailing_return(closes: dict[str, float], dates: list[str], end_index: int, window: int) -> float | None:
    start_index = end_index - window
    if start_index < 0:
        return None
    return closes[dates[end_index]] / closes[dates[start_index]] - 1.0


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
    daily = {symbol: _daily_returns(closes[symbol], common_dates) for symbol in all_symbols}
    pairs = list(combinations(SLEEVES, 2))

    print(f"Dataset: {dataset_id}")
    print(f"{len(SLEEVES)} sleeves, {len(common_dates)} common real trading days, state window={STATE_WINDOW}d\n")

    results: list[dict] = []
    for forward_days in FORWARD_WINDOWS:
        state_series: dict[str, list[float]] = {
            "dispersion": [], "mean_pairwise_corr": [], "top3_minus_bottom3": [],
            "leadership_gap": [], "sleeve_breadth": [],
        }
        forward_spreads: list[float] = []

        for i in range(STATE_WINDOW, len(common_dates) - forward_days, STRIDE_DAYS):
            trailing = {s: _trailing_return(closes[s], common_dates, i, STATE_WINDOW) for s in SLEEVES}
            if any(v is None for v in trailing.values()):
                continue
            spy_trailing = _trailing_return(closes[BENCHMARK], common_dates, i, STATE_WINDOW)

            values = list(trailing.values())
            dispersion = statistics.pstdev(values)
            ranked = sorted(SLEEVES, key=lambda s: trailing[s], reverse=True)
            top3_ret = statistics.fmean(trailing[s] for s in ranked[:3])
            bottom3_ret = statistics.fmean(trailing[s] for s in ranked[-3:])
            top1 = ranked[0]
            leadership_gap = trailing[top1] - statistics.fmean(trailing[s] for s in SLEEVES if s != top1)
            breadth = sum(1 for s in SLEEVES if trailing[s] > spy_trailing)

            window_dates = common_dates[i - STATE_WINDOW + 1 : i + 1]
            corr_values: list[float] = []
            for a, b in pairs:
                a_ret = [daily[a][d] for d in window_dates]
                b_ret = [daily[b][d] for d in window_dates]
                r, _ = pearson_significance(a_ret, b_ret)
                corr_values.append(r)
            mean_corr = statistics.fmean(corr_values)

            start_date, end_date = common_dates[i], common_dates[i + forward_days]
            forward_returns = {s: closes[s][end_date] / closes[s][start_date] - 1.0 for s in SLEEVES}
            fwd_ranked = sorted(SLEEVES, key=lambda s: forward_returns[s], reverse=True)
            forward_spread = (
                statistics.fmean(forward_returns[s] for s in fwd_ranked[:3])
                - statistics.fmean(forward_returns[s] for s in fwd_ranked[-3:])
            )

            state_series["dispersion"].append(dispersion)
            state_series["mean_pairwise_corr"].append(mean_corr)
            state_series["top3_minus_bottom3"].append(top3_ret - bottom3_ret)
            state_series["leadership_gap"].append(leadership_gap)
            state_series["sleeve_breadth"].append(float(breadth))
            forward_spreads.append(forward_spread)

        n = len(forward_spreads)
        print(f"=== Forward window {forward_days}d: n={n} real monthly-strided observations ===")
        for name, series in state_series.items():
            if len(series) < 3:
                continue
            r, p = pearson_significance(series, forward_spreads)
            results.append({"metric": name, "forward_days": forward_days, "n": len(series), "correlation": r, "p_value": p})

    adjusted, significant = benjamini_hochberg([r["p_value"] for r in results])
    for r, adj_p, sig in zip(results, adjusted, significant):
        r["adjusted_p"] = adj_p
        r["significant"] = sig

    print(f"\n=== {len(results)} tests (state variable x forward window), Benjamini-Hochberg corrected ===\n")
    for r in sorted(results, key=lambda r: r["adjusted_p"]):
        flag = "SIGNIFICANT" if r["significant"] else "not significant"
        print(f"{r['metric']:20s} {r['forward_days']:3d}d  n={r['n']:3d}  r={r['correlation']:+.3f}  "
              f"p={r['p_value']:.4f}  adj_p={r['adjusted_p']:.4f}  ({flag})")

    sig_count = sum(1 for r in results if r["significant"])
    print(f"\n{sig_count} of {len(results)} significant after correction "
          f"(chance alone at alpha=0.05 would produce ~{0.05 * len(results):.1f})")


if __name__ == "__main__":
    main()
