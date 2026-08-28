"""Scratch script for docs/hypotheses/macro-research/factor-breadth-weighting.md
(H-MACRO11), real target-corrected re-test.

H-MACRO11's own required next step: re-run the identical IC-weighted-
vs-cluster-equal comparison against the composite's ACTUAL, real,
out-of-sample-validated target -- P(real SPY drawdown >=10% within 6
months), H-MACRO09's own definition -- not forward SPY return (the
wrong target the first pass used). Same walk-forward discipline: IC
weights learned in-sample only, held fixed, applied unchanged
out-of-sample. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.macro_factor_breadth_test_drawdown_target
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import pearson_significance, proportion_significance
from backend.research_lab.macro_factor_breadth_test import _per_factor_series
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, _closes
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE

FORWARD_DAYS = 126  # matches H-MACRO09's own primary window
DRAWDOWN_THRESHOLD = -0.10  # matches H-MACRO09's own real, disclosed threshold


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    series, factor_keys = _per_factor_series(connection, dataset_id)
    spy_closes = _closes(connection, dataset_id, BENCHMARK)
    spy_dates = sorted(spy_closes)
    print(f"Dataset: {dataset_id}")
    print(f"{len(series)} real point-in-time anchors, {len(factor_keys)} real factors\n")

    def _forward_drawdown(anchor_date: str) -> tuple[float, bool] | None:
        """Real max drawdown and a real >=10% drawdown indicator over the
        126 real trading days following the first real SPY date on/after
        anchor_date -- exact same definition as H-MACRO09."""
        candidates = [d for d in spy_dates if d >= anchor_date]
        if not candidates:
            return None
        start_date = candidates[0]
        start_index = spy_dates.index(start_date)
        if start_index + FORWARD_DAYS >= len(spy_dates):
            return None
        start_close = spy_closes[start_date]
        future_closes = [spy_closes[spy_dates[i]] for i in range(start_index, start_index + FORWARD_DAYS + 1)]
        max_dd = min((c - start_close) / start_close for c in future_closes)
        return max_dd, max_dd <= DRAWDOWN_THRESHOLD

    in_sample_series = [s for s in series if s[0] < SPLIT_DATE]
    oos_series = [s for s in series if s[0] >= SPLIT_DATE]

    factor_ic: dict[str, float] = {}
    print("=== Real per-factor IC (in-sample, contribution vs. real 126d drawdown indicator) ===")
    for key in factor_keys:
        xs, ys = [], []
        for anchor, contributions, _ in in_sample_series:
            if key not in contributions:
                continue
            dd = _forward_drawdown(anchor)
            if dd is None:
                continue
            xs.append(contributions[key])
            ys.append(1.0 if dd[1] else 0.0)
        if len(xs) >= 3 and len(set(ys)) > 1:
            r, _ = pearson_significance(xs, ys)
            factor_ic[key] = r
            print(f"  {key:16s}: IC={r:+.3f} (n={len(xs)})")

    if not factor_ic:
        print("No real factor ICs computable against this target -- stopping.")
        return

    def _ic_weighted_composite(contributions: dict[str, float]) -> float:
        # Weight by |IC| (reliability), not signed IC -- see the matching
        # comment in macro_factor_breadth_test.py for why the signed
        # version is a real bug: `contributions` is already sign-oriented,
        # so a genuinely reliable factor correctly shows a NEGATIVE IC
        # here, and using that signed IC as the weight flips it, corrupting
        # the composite. Caught by this exact script's first run showing an
        # impossible, backwards sign against real drawdown risk.
        total_abs_ic = sum(abs(factor_ic.get(k, 0.0)) for k in contributions)
        if total_abs_ic < 1e-9:
            return 0.0
        return sum(abs(factor_ic.get(k, 0.0)) * v for k, v in contributions.items()) / total_abs_ic

    for label, subset in [("IN-SAMPLE", in_sample_series), ("OUT-OF-SAMPLE", oos_series)]:
        cluster_scores, ic_weighted_scores, dd_flags = [], [], []
        for anchor, contributions, cluster_composite in subset:
            dd = _forward_drawdown(anchor)
            if dd is None:
                continue
            cluster_scores.append(cluster_composite)
            ic_weighted_scores.append(_ic_weighted_composite(contributions))
            dd_flags.append(dd[1])

        n = len(dd_flags)
        if n < 6:
            print(f"{label}: insufficient data")
            continue

        dd_numeric = [1.0 if f else 0.0 for f in dd_flags]
        r_cluster, _ = pearson_significance(cluster_scores, dd_numeric)
        r_icweighted, _ = pearson_significance(ic_weighted_scores, dd_numeric)
        print(f"\n=== {label} (n={n}) -- continuous IC vs. real drawdown indicator ===")
        print(f"cluster-equal IC={r_cluster:+.3f}   IC-weighted IC={r_icweighted:+.3f}   diff={r_icweighted - r_cluster:+.3f}")

        for name, scores in [("cluster-equal", cluster_scores), ("IC-weighted", ic_weighted_scores)]:
            paired = sorted(zip(scores, dd_flags))
            tercile = n // 3
            stressed = paired[:tercile]  # most negative composite = most stressed
            calm = paired[-tercile:]
            stressed_hits = sum(1 for _, dd_flag in stressed if dd_flag)
            calm_hits = sum(1 for _, dd_flag in calm if dd_flag)
            diff, p = proportion_significance(stressed_hits, len(stressed), calm_hits, len(calm))
            print(f"  {name:14s}: P(drawdown|stressed tercile)={stressed_hits}/{len(stressed)}={stressed_hits/len(stressed):.1%}  "
                  f"P(drawdown|calm tercile)={calm_hits}/{len(calm)}={calm_hits/len(calm):.1%}  "
                  f"diff={diff:+.1%}  p={p:.4f} ({'SIG' if p < 0.05 else 'n.s.'})")


if __name__ == "__main__":
    main()
