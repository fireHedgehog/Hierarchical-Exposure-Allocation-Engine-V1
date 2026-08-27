"""Scratch script for
docs/hypotheses/asset-selection-research/regime-conditioned-sleeve-return.md.

H-SECT02 out-of-sample split: same chronological-split convention as
composite_forward_risk_oos.py (H-MACRO09's own OOS follow-up) --
disclosed split at 2019-01-01, no refitting on either half, full
24-test panel re-run independently on each half. Read-only against the
sealed dataset.

Run: .venv/bin/python -m backend.research_lab.regime_conditioned_sleeve_return_oos
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.research_lab.regime_conditioned_sleeve_return import (
    BENCHMARK,
    FORWARD_WINDOWS,
    SLEEVES,
    STRIDE_DAYS,
    _closes,
    _macro_composite_series,
)

SPLIT_DATE = "2019-01-01"  # disclosed, pre-chosen -- same convention as H-MACRO09's OOS split


def _run_panel(common_dates: list[str], closes: dict[str, dict[str, float]], composite_series: list[tuple[str, float]]) -> list[dict]:
    results: list[dict] = []
    for sleeve in SLEEVES:
        for forward_days in FORWARD_WINDOWS:
            composite_scores: list[float] = []
            relative_returns: list[float] = []
            for i in range(0, len(common_dates) - forward_days, STRIDE_DAYS):
                anchor_date = common_dates[i]
                candidates = [(d, s) for d, s in composite_series if d <= anchor_date]
                if not candidates:
                    continue
                _, composite = max(candidates, key=lambda pair: pair[0])

                start_date, end_date = common_dates[i], common_dates[i + forward_days]
                sleeve_return = closes[sleeve][end_date] / closes[sleeve][start_date] - 1.0
                benchmark_return = closes[BENCHMARK][end_date] / closes[BENCHMARK][start_date] - 1.0
                composite_scores.append(composite)
                relative_returns.append(sleeve_return - benchmark_return)

            n = len(composite_scores)
            if n < 3:
                continue
            correlation, p_value = pearson_significance(composite_scores, relative_returns)
            results.append({"sleeve": sleeve, "forward_days": forward_days, "n": n, "correlation": correlation, "p_value": p_value})

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
    composite_series = _macro_composite_series(connection, dataset_id)

    in_sample_dates = [d for d in common_dates if d < SPLIT_DATE]
    out_of_sample_dates = [d for d in common_dates if d >= SPLIT_DATE]
    print(f"Split at {SPLIT_DATE} (disclosed, pre-chosen -- same as H-MACRO09's OOS convention)")
    print(f"In-sample: {in_sample_dates[0]} to {in_sample_dates[-1]} ({len(in_sample_dates)} days)")
    print(f"Out-of-sample: {out_of_sample_dates[0]} to {out_of_sample_dates[-1]} ({len(out_of_sample_dates)} days)\n")

    original = {(r["sleeve"], r["forward_days"]) for r in _run_panel(common_dates, closes, composite_series) if r["significant"]}

    in_sample = _run_panel(in_sample_dates, closes, composite_series)
    out_of_sample = _run_panel(out_of_sample_dates, closes, composite_series)
    in_sample_by_key = {(r["sleeve"], r["forward_days"]): r for r in in_sample}
    oos_by_key = {(r["sleeve"], r["forward_days"]): r for r in out_of_sample}

    in_sig = sum(1 for r in in_sample if r["significant"])
    oos_sig = sum(1 for r in out_of_sample if r["significant"])
    print(f"In-sample half (2004-2018): {in_sig} of {len(in_sample)} significant")
    print(f"Out-of-sample half (2019-2026): {oos_sig} of {len(out_of_sample)} significant\n")

    print(f"=== Replication of the {len(original)} originally full-sample-significant sleeve/windows ===\n")
    for sleeve, forward_days in sorted(original, key=lambda k: (k[0], k[1])):
        is_r = in_sample_by_key.get((sleeve, forward_days))
        oos_r = oos_by_key.get((sleeve, forward_days))
        is_flag = "SIG" if is_r and is_r["significant"] else "n.s."
        oos_flag = "SIG" if oos_r and oos_r["significant"] else "n.s."
        is_str = f"r={is_r['correlation']:+.3f} adj_p={is_r['adjusted_p']:.4f} ({is_flag})" if is_r else "n/a"
        oos_str = f"r={oos_r['correlation']:+.3f} adj_p={oos_r['adjusted_p']:.4f} ({oos_flag})" if oos_r else "n/a"
        print(f"{sleeve:5s} {forward_days:3d}d  |  in-sample: {is_str}  |  out-of-sample: {oos_str}")


if __name__ == "__main__":
    main()
