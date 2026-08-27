"""Scratch script for
docs/hypotheses/asset-selection-research/conjunctive-xlu-trigger.md.

H-SECT09: is XLU's real, beta-adjusted regime sensitivity (H-SECT05)
stronger when multiple macro clusters simultaneously read "stressed,"
not just a function of the aggregate composite score already tested?
Deliberately narrow: only XLU, only the 3 production clusters, no
combinatorial sweep. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.conjunctive_xlu_trigger
"""

from __future__ import annotations

import statistics
from datetime import date

from backend.database import connect, resolve_database_path
from backend.engine.regime import InsufficientSeriesDataError, compute_regime_v3
from backend.engine.regime.scoring_v3 import CLUSTERS, STRESSED_TERCILE_CUTOFF
from backend.engine.regime.types import SeriesObservation
from backend.engine.research.significance import pearson_significance
from backend.research_lab.beta_adjusted_regime_sensitivity import BETA_WINDOW, _daily_returns, _trailing_beta
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, FORWARD_WINDOWS, STRIDE_DAYS, _closes

SLEEVE = "XLU"
MACRO_SERIES = [series_id for members in CLUSTERS.values() for (_, _, series_id, *_rest) in members]
KEY_TO_CLUSTER = {key: cluster_name for cluster_name, members in CLUSTERS.items() for (key, *_rest) in members}


def _cluster_composite_series(connection, dataset_id: str) -> list[tuple[str, dict[str, float]]]:
    """Real, point-in-time per-cluster mean contribution at each of
    CPIAUCSL's own observation dates -- same anchor convention as
    regime_conditioned_sleeve_return.py's _macro_composite_series, but
    keeping the 3 cluster means separate instead of collapsing to one
    composite score."""
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
    series: list[tuple[str, dict[str, float]]] = []
    for anchor in anchor_dates:
        truncated = {
            series_id: [obs for obs in obs_list if obs.observation_date <= anchor]
            for series_id, obs_list in factor_observations.items()
        }
        try:
            result = compute_regime_v3(truncated, date.fromisoformat(anchor))
        except InsufficientSeriesDataError:
            continue
        by_cluster: dict[str, list[float]] = {}
        for factor in result.factors:
            cluster_name = KEY_TO_CLUSTER[factor.key]
            by_cluster.setdefault(cluster_name, []).append(factor.contribution)
        cluster_means = {name: statistics.fmean(values) for name, values in by_cluster.items()}
        series.append((anchor, cluster_means))
    return series


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    all_symbols = [BENCHMARK, SLEEVE]
    closes = {symbol: _closes(connection, dataset_id, symbol) for symbol in all_symbols}
    common_dates = sorted(set.intersection(*(set(c) for c in closes.values())))
    daily = {symbol: _daily_returns(closes[symbol], common_dates) for symbol in all_symbols}
    return_dates = common_dates[1:]
    return_date_index = {d: i for i, d in enumerate(return_dates)}

    cluster_series = _cluster_composite_series(connection, dataset_id)
    print(f"Dataset: {dataset_id}")
    print(f"{len(cluster_series)} real point-in-time cluster-composite anchors\n")

    for forward_days in FORWARD_WINDOWS:
        alignment_counts: list[int] = []
        beta_adj_returns: list[float] = []
        by_alignment: dict[int, list[float]] = {0: [], 1: [], 2: [], 3: []}

        for i in range(0, len(common_dates) - forward_days, STRIDE_DAYS):
            anchor_date = common_dates[i]
            return_index = return_date_index.get(anchor_date)
            if return_index is None:
                continue
            beta = _trailing_beta(daily[SLEEVE], daily[BENCHMARK], return_dates, return_index)
            if beta is None:
                continue

            candidates = [(d, means) for d, means in cluster_series if d <= anchor_date]
            if not candidates:
                continue
            _, cluster_means = max(candidates, key=lambda pair: pair[0])
            alignment_count = sum(1 for v in cluster_means.values() if v <= STRESSED_TERCILE_CUTOFF)

            start_date, end_date = common_dates[i], common_dates[i + forward_days]
            sleeve_return = closes[SLEEVE][end_date] / closes[SLEEVE][start_date] - 1.0
            benchmark_return = closes[BENCHMARK][end_date] / closes[BENCHMARK][start_date] - 1.0
            beta_adj_return = sleeve_return - beta * benchmark_return

            alignment_counts.append(alignment_count)
            beta_adj_returns.append(beta_adj_return)
            by_alignment[alignment_count].append(beta_adj_return)

        n = len(alignment_counts)
        if n < 3:
            continue
        r, p = pearson_significance([float(a) for a in alignment_counts], beta_adj_returns)
        print(f"=== {forward_days}d forward window (n={n}) ===")
        print(f"IC(alignment_count, XLU beta-adjusted forward return): r={r:+.3f}, p={p:.4f} "
              f"({'SIGNIFICANT' if p < 0.05 else 'not significant'})")
        for count in (0, 1, 2, 3):
            values = by_alignment[count]
            if values:
                print(f"  alignment_count={count}: n={len(values):3d}  mean beta-adj return={statistics.fmean(values):+.2%}")
            else:
                print(f"  alignment_count={count}: n=0")
        print()


if __name__ == "__main__":
    main()
