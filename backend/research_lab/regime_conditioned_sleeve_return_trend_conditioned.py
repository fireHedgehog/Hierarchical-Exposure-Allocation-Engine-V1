"""Scratch script for
docs/hypotheses/asset-selection-research/regime-conditioned-sleeve-return.md
(H-SECT02), trend-conditioned addendum.

Same H, same real relative-return measure (R_sleeve - R_SPY), but
conditioned on a real, classic CTA-style trend filter -- SPY vs. its
own 50-day moving average -- instead of macro_regime_composite. A
genuinely different, textbook-explainable conditioning variable,
deliberately slow-moving (ignores the 5-10 day chop by construction,
per direct instruction). Extends the sleeve universe to include SMH/IGV
("which narrative is winning" is exactly their use case). Read-only
against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.regime_conditioned_sleeve_return_trend_conditioned
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, FORWARD_WINDOWS, SLEEVES, STRIDE_DAYS, _closes

THEMES = ["SMH", "IGV"]
ALL_SLEEVES = SLEEVES + THEMES
MA_LONG = 50  # classic CTA mid-term trend filter, disclosed, not tuned


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    all_symbols = [BENCHMARK] + ALL_SLEEVES
    closes = {symbol: _closes(connection, dataset_id, symbol) for symbol in all_symbols}
    common_dates = sorted(set.intersection(*(set(c) for c in closes.values())))
    spy_ordered = [closes[BENCHMARK][d] for d in common_dates]
    print(f"Dataset: {dataset_id}")
    print(f"{len(common_dates)} common real trading days, {common_dates[0]} to {common_dates[-1]}\n")

    bull_by_index: dict[int, bool] = {}
    for i in range(MA_LONG - 1, len(common_dates)):
        ma = sum(spy_ordered[i - MA_LONG + 1 : i + 1]) / MA_LONG
        bull_by_index[i] = spy_ordered[i] > ma

    n_bull = sum(1 for v in bull_by_index.values() if v)
    print(f"{len(bull_by_index)} real classifiable days: {n_bull} bullish ({n_bull/len(bull_by_index):.1%}), "
          f"{len(bull_by_index)-n_bull} bearish\n")

    results: list[dict] = []
    for sleeve in ALL_SLEEVES:
        for forward_days in FORWARD_WINDOWS:
            bull_indicator: list[float] = []
            relative_returns: list[float] = []
            bull_returns: list[float] = []
            bear_returns: list[float] = []
            for i in range(MA_LONG - 1, len(common_dates) - forward_days, STRIDE_DAYS):
                is_bull = bull_by_index[i]
                start_date, end_date = common_dates[i], common_dates[i + forward_days]
                sleeve_return = closes[sleeve][end_date] / closes[sleeve][start_date] - 1.0
                benchmark_return = closes[BENCHMARK][end_date] / closes[BENCHMARK][start_date] - 1.0
                rel = sleeve_return - benchmark_return

                bull_indicator.append(1.0 if is_bull else 0.0)
                relative_returns.append(rel)
                (bull_returns if is_bull else bear_returns).append(rel)

            n = len(relative_returns)
            if n < 3:
                continue
            r, p = pearson_significance(bull_indicator, relative_returns)
            results.append({
                "sleeve": sleeve, "forward_days": forward_days, "n": n, "correlation": r, "p_value": p,
                "bull_mean": statistics.fmean(bull_returns) if bull_returns else None,
                "bear_mean": statistics.fmean(bear_returns) if bear_returns else None,
                "bull_n": len(bull_returns), "bear_n": len(bear_returns),
            })

    adjusted, significant = benjamini_hochberg([r["p_value"] for r in results])
    for r, adj_p, sig in zip(results, adjusted, significant):
        r["adjusted_p"] = adj_p
        r["significant"] = sig

    print(f"=== {len(results)} tests (sleeve x window), Benjamini-Hochberg corrected ===\n")
    for r in sorted(results, key=lambda r: r["adjusted_p"]):
        flag = "SIGNIFICANT" if r["significant"] else "not significant"
        print(f"{r['sleeve']:5s} {r['forward_days']:3d}d  n={r['n']:3d}  r={r['correlation']:+.3f}  "
              f"adj_p={r['adjusted_p']:.4f}  ({flag})  |  bull(n={r['bull_n']}) mean={r['bull_mean']:+.2%}  "
              f"bear(n={r['bear_n']}) mean={r['bear_mean']:+.2%}")

    sig_count = sum(1 for r in results if r["significant"])
    print(f"\n{sig_count} of {len(results)} significant after correction "
          f"(chance alone at alpha=0.05 would produce ~{0.05 * len(results):.1f})\n")

    print("=== Strongest narrative in a bull regime (by bull-period mean relative return, significant only) ===")
    bull_ranked = sorted((r for r in results if r["significant"]), key=lambda r: r["bull_mean"], reverse=True)
    for r in bull_ranked:
        print(f"  {r['sleeve']:5s} {r['forward_days']:3d}d: bull mean relative return = {r['bull_mean']:+.2%}")


if __name__ == "__main__":
    main()
