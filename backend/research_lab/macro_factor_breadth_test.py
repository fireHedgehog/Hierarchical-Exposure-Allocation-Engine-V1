"""Scratch script for docs/hypotheses/macro-research/README.md's
restart-here gap: "Compare cluster-equal-weighting against IC-weighted
alternatives" -- picked up directly, not re-derived from scratch.

Real Fundamental-Law-style test at the macro-composite level: does the
production composite's cluster-equal weighting (naive-v3) leave real
IR on the table versus a real, walk-forward IC-weighted combination of
the same 13 factors? Reuses this project's own proven PCA breadth
machinery (H-MACRO08's tool). Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.macro_factor_breadth_test
"""

from __future__ import annotations

import statistics
from datetime import date

from backend.database import connect, resolve_database_path
from backend.engine.regime import InsufficientSeriesDataError, compute_regime_v3
from backend.engine.regime.types import SeriesObservation
from backend.engine.research.significance import pearson_significance
from backend.engine.research.signal_validation import effective_number_of_bets, pairwise_correlation_matrix
from backend.research_lab.conjunctive_xlu_trigger import MACRO_SERIES
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, _closes
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE

FORWARD_DAYS = 126  # matches H-MACRO09's own primary window


def _per_factor_series(connection, dataset_id: str) -> tuple[list[tuple[str, dict[str, float], float]], list[str]]:
    """Real, point-in-time (date, {factor_key: contribution}, cluster_composite)
    at each of CPIAUCSL's own observation dates -- same anchor convention
    used throughout this session."""
    factor_observations: dict[str, list[SeriesObservation]] = {}
    for series_id in MACRO_SERIES:
        rows = connection.execute(
            "SELECT observation_date, value FROM fred_observations "
            "WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL ORDER BY observation_date",
            (dataset_id, series_id),
        ).fetchall()
        if rows:
            factor_observations[series_id] = [
                SeriesObservation(observation_date=row["observation_date"], value=row["value"], observed_at="", available_at="")
                for row in rows
            ]

    anchor_dates = sorted({obs.observation_date for obs in factor_observations.get("CPIAUCSL", [])})
    series: list[tuple[str, dict[str, float], float]] = []
    all_keys: set[str] = set()
    for anchor in anchor_dates:
        truncated = {
            series_id: [obs for obs in obs_list if obs.observation_date <= anchor]
            for series_id, obs_list in factor_observations.items()
        }
        try:
            result = compute_regime_v3(truncated, date.fromisoformat(anchor))
        except InsufficientSeriesDataError:
            continue
        contributions = {factor.key: factor.contribution for factor in result.factors}
        cluster_composite = sum(result.weights[factor.key] * factor.contribution for factor in result.factors)
        all_keys.update(contributions)
        series.append((anchor, contributions, cluster_composite))
    return series, sorted(all_keys)


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
    print(f"Dataset: {dataset_id}")
    print(f"{len(series)} real point-in-time anchors, {len(factor_keys)} real factors\n")

    spy_closes = _closes(connection, dataset_id, BENCHMARK)
    spy_dates = sorted(spy_closes)

    def _forward_spy_return(anchor_date: str) -> float | None:
        candidates = [d for d in spy_dates if d >= anchor_date]
        if not candidates:
            return None
        start_date = candidates[0]
        future_candidates = [d for d in spy_dates if d >= start_date]
        idx = future_candidates.index(start_date) if start_date in future_candidates else None
        start_index = spy_dates.index(start_date)
        if start_index + FORWARD_DAYS >= len(spy_dates):
            return None
        end_date = spy_dates[start_index + FORWARD_DAYS]
        return spy_closes[end_date] / spy_closes[start_date] - 1.0

    in_sample_series = [s for s in series if s[0] < SPLIT_DATE]
    oos_series = [s for s in series if s[0] >= SPLIT_DATE]

    # Real, walk-forward IC per factor, learned in-sample only
    factor_ic: dict[str, float] = {}
    print("=== Real per-factor IC (in-sample, contribution vs. forward 126d SPY return) ===")
    for key in factor_keys:
        xs, ys = [], []
        for anchor, contributions, _ in in_sample_series:
            if key not in contributions:
                continue
            fwd = _forward_spy_return(anchor)
            if fwd is None:
                continue
            xs.append(contributions[key])
            ys.append(fwd)
        if len(xs) >= 3:
            r, _ = pearson_significance(xs, ys)
            factor_ic[key] = r
            print(f"  {key:16s}: IC={r:+.3f} (n={len(xs)})")

    mean_abs_ic = statistics.fmean(abs(v) for v in factor_ic.values())
    contribution_series = {key: [c.get(key, 0.0) for _, c, _ in series] for key in factor_keys}
    correlations = pairwise_correlation_matrix(contribution_series)
    breadth = effective_number_of_bets(factor_keys, correlations)
    print(f"\nMean |IC| across {len(factor_keys)} real factors: {mean_abs_ic:.3f}")
    print(f"Real effective breadth: {breadth:.2f} (vs. naive count {len(factor_keys)}; H-MACRO08 found ~4 real clusters)")
    if breadth:
        print(f"Grinold prediction: IR ~= {mean_abs_ic:.3f} x sqrt({breadth:.2f}) = {mean_abs_ic * breadth ** 0.5:.3f}\n")

    def _ic_weighted_composite(contributions: dict[str, float]) -> float:
        total_abs_ic = sum(abs(factor_ic.get(k, 0.0)) for k in contributions)
        if total_abs_ic < 1e-9:
            return 0.0
        return sum(factor_ic.get(k, 0.0) * v for k, v in contributions.items()) / total_abs_ic

    for label, subset in [("IN-SAMPLE", in_sample_series), ("OUT-OF-SAMPLE", oos_series)]:
        cluster_scores, ic_weighted_scores, forwards = [], [], []
        for anchor, contributions, cluster_composite in subset:
            fwd = _forward_spy_return(anchor)
            if fwd is None:
                continue
            cluster_scores.append(cluster_composite)
            ic_weighted_scores.append(_ic_weighted_composite(contributions))
            forwards.append(fwd)
        if len(forwards) < 3:
            print(f"{label}: insufficient data")
            continue
        r_cluster, _ = pearson_significance(cluster_scores, forwards)
        r_icweighted, _ = pearson_significance(ic_weighted_scores, forwards)
        print(f"{label} (n={len(forwards)}): cluster-equal-weight IC={r_cluster:+.3f}  "
              f"IC-weighted-alternative IC={r_icweighted:+.3f}  diff={r_icweighted - r_cluster:+.3f}")


if __name__ == "__main__":
    main()
