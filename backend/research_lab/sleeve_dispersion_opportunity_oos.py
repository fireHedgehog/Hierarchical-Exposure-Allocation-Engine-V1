"""Scratch script for
docs/hypotheses/asset-selection-research/sleeve-dispersion-opportunity.md.

H-SECT07 out-of-sample split: same 2019-01-01 convention as every other
OOS check in this folder, full panel re-run independently on each half,
no refitting. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.sleeve_dispersion_opportunity_oos
"""

from __future__ import annotations

import statistics
from itertools import combinations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, SLEEVES, STRIDE_DAYS, _closes
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE
from backend.research_lab.sleeve_dispersion_opportunity import FORWARD_WINDOWS, STATE_WINDOW, _daily_returns, _trailing_return


def _run_panel(dates: list[str], closes: dict[str, dict[str, float]], daily: dict[str, dict[str, float]], pairs: list[tuple[str, str]]) -> list[dict]:
    results: list[dict] = []
    for forward_days in FORWARD_WINDOWS:
        state_series: dict[str, list[float]] = {
            "dispersion": [], "mean_pairwise_corr": [], "top3_minus_bottom3": [],
            "leadership_gap": [], "sleeve_breadth": [],
        }
        forward_spreads: list[float] = []
        for i in range(STATE_WINDOW, len(dates) - forward_days, STRIDE_DAYS):
            trailing = {s: _trailing_return(closes[s], dates, i, STATE_WINDOW) for s in SLEEVES}
            if any(v is None for v in trailing.values()):
                continue
            spy_trailing = _trailing_return(closes[BENCHMARK], dates, i, STATE_WINDOW)

            values = list(trailing.values())
            dispersion = statistics.pstdev(values)
            ranked = sorted(SLEEVES, key=lambda s: trailing[s], reverse=True)
            top3_ret = statistics.fmean(trailing[s] for s in ranked[:3])
            bottom3_ret = statistics.fmean(trailing[s] for s in ranked[-3:])
            top1 = ranked[0]
            leadership_gap = trailing[top1] - statistics.fmean(trailing[s] for s in SLEEVES if s != top1)
            breadth = sum(1 for s in SLEEVES if trailing[s] > spy_trailing)

            window_dates = dates[i - STATE_WINDOW + 1 : i + 1]
            corr_values = []
            for a, b in pairs:
                r, _ = pearson_significance([daily[a][d] for d in window_dates], [daily[b][d] for d in window_dates])
                corr_values.append(r)
            mean_corr = statistics.fmean(corr_values)

            start_date, end_date = dates[i], dates[i + forward_days]
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

        for name, series in state_series.items():
            if len(series) < 3:
                continue
            r, p = pearson_significance(series, forward_spreads)
            results.append({"metric": name, "forward_days": forward_days, "n": len(series), "correlation": r, "p_value": p})

    adjusted, significant = benjamini_hochberg([r["p_value"] for r in results])
    for r, adj_p, sig in zip(results, adjusted, significant):
        r["adjusted_p"] = adj_p
        r["significant"] = sig
    return results


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

    in_sample_dates = [d for d in common_dates if d < SPLIT_DATE]
    out_of_sample_dates = [d for d in common_dates if d >= SPLIT_DATE]
    print(f"Split at {SPLIT_DATE}")
    print(f"In-sample: {len(in_sample_dates)} days, out-of-sample: {len(out_of_sample_dates)} days\n")

    in_sample = _run_panel(in_sample_dates, closes, daily, pairs)
    out_of_sample = _run_panel(out_of_sample_dates, closes, daily, pairs)
    oos_by_key = {(r["metric"], r["forward_days"]): r for r in out_of_sample}

    for r in sorted(in_sample, key=lambda r: (r["metric"], r["forward_days"])):
        oos_r = oos_by_key.get((r["metric"], r["forward_days"]))
        is_flag = "SIG" if r["significant"] else "n.s."
        oos_flag = "SIG" if oos_r and oos_r["significant"] else "n.s."
        oos_str = f"r={oos_r['correlation']:+.3f} adj_p={oos_r['adjusted_p']:.4f} ({oos_flag})" if oos_r else "n/a"
        print(f"{r['metric']:20s} {r['forward_days']:3d}d  |  in-sample: r={r['correlation']:+.3f} "
              f"adj_p={r['adjusted_p']:.4f} ({is_flag})  |  out-of-sample: {oos_str}")

    print(f"\nIn-sample: {sum(1 for r in in_sample if r['significant'])} of {len(in_sample)} significant")
    print(f"Out-of-sample: {sum(1 for r in out_of_sample if r['significant'])} of {len(out_of_sample)} significant")


if __name__ == "__main__":
    main()
