"""Scratch script for
docs/hypotheses/asset-selection-research/section-leadership-persistence.md.

H-SECT01: does sector leadership (top-tercile trailing-3-month return,
9-sector universe) persist longer than a real permutation-null predicts,
and does duration depend on the macro regime active when the episode
begins. Every design decision (universe, window, no stride, permutation
null, regime-bucket source) is disclosed in the paper, not here -- this
is a direct implementation of it. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.section_leadership_persistence
"""

from __future__ import annotations

import random
import statistics
from datetime import date

from scipy import stats

from backend.database import connect, resolve_database_path
from backend.engine.regime import InsufficientSeriesDataError, compute_regime_v3
from backend.engine.regime.scoring_v3 import CALM_TERCILE_CUTOFF, STRESSED_TERCILE_CUTOFF
from backend.engine.regime.types import SeriesObservation

SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
LOOKBACK_DAYS = 63  # ~3 months, trailing total return window
LEADERSHIP_SIZE = 3  # top tercile of 9
PERMUTATION_REPS = 1000
RANDOM_SEED = 20260827  # disclosed, fixed for reproducibility

MACRO_SERIES = [
    "INDPRO", "PAYEMS", "GDPC1", "CPIAUCSL", "PCEPILFE", "PPIACO",
    "DGS10", "DGS30", "DFII10", "NFCI", "VIXCLS", "BAMLH0A0HYM2", "BAMLC0A0CM",
]


def _sector_closes(connection, dataset_id: str, symbol: str) -> list[tuple[str, float]]:
    security_id = f"us-etf-{symbol.lower()}"
    rows = connection.execute(
        "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
        "AND close IS NOT NULL ORDER BY time",
        (dataset_id, security_id),
    ).fetchall()
    return [(row["time"], row["close"]) for row in rows]


def _episode_durations(flags: list[bool]) -> list[int]:
    """Maximal-run durations (real trading days) of consecutive True values.
    The final run, if still open at series end, is right-censored and
    dropped -- a naive, disclosed simplification, not full survival
    analysis."""
    durations: list[int] = []
    run = 0
    for flag in flags:
        if flag:
            run += 1
        else:
            if run > 0:
                durations.append(run)
            run = 0
    return durations


def _macro_composite_series(connection, dataset_id: str) -> list[tuple[str, float]]:
    """Real, point-in-time composite score at each of CPIAUCSL's own
    observation dates -- same anchor convention as research_repository.py's
    _macro_composite_score_series, reimplemented here since research_lab
    may only depend on engine/, never on repository-layer code."""
    factor_observations: dict[str, list[SeriesObservation]] = {}
    for series_id in MACRO_SERIES:
        rows = connection.execute(
            "SELECT observation_date, value FROM fred_observations "
            "WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL ORDER BY observation_date",
            (dataset_id, series_id),
        ).fetchall()
        if rows:
            factor_observations[series_id] = [
                SeriesObservation(
                    observation_date=row["observation_date"], value=row["value"], observed_at="", available_at=""
                )
                for row in rows
            ]

    anchor_dates = sorted({obs.observation_date for obs in factor_observations.get("CPIAUCSL", [])})
    composite_series: list[tuple[str, float]] = []
    for anchor in anchor_dates:
        truncated = {
            series_id: [obs for obs in obs_list if obs.observation_date <= anchor]
            for series_id, obs_list in factor_observations.items()
        }
        try:
            result = compute_regime_v3(truncated, date.fromisoformat(anchor))
        except InsufficientSeriesDataError:
            continue
        composite_score = sum(result.weights[factor.key] * factor.contribution for factor in result.factors)
        composite_series.append((anchor, composite_score))
    return composite_series


def _block_leaders(common_dates: list[str], sector_closes: dict[str, dict[str, float]], block_size: int) -> list[set[str]]:
    """Non-overlapping block leadership -- each block uses a fresh return
    over independent, non-overlapping windows, unlike the daily rolling-
    window analysis above where 62 of 63 days are shared between one day's
    ranking and the next (a real mechanical-autocorrelation confound the
    daily permutation-null test above does NOT rule out). This is the
    cleaner test of genuine persistence."""
    blocks: list[set[str]] = []
    i = 0
    while i + block_size < len(common_dates):
        start_date, end_date = common_dates[i], common_dates[i + block_size]
        returns = {s: sector_closes[s][end_date] / sector_closes[s][start_date] - 1.0 for s in SECTORS}
        ranked = sorted(SECTORS, key=lambda s: returns[s], reverse=True)
        blocks.append(set(ranked[:LEADERSHIP_SIZE]))
        i += block_size
    return blocks


def _regime_bucket(composite: float) -> str:
    if composite <= STRESSED_TERCILE_CUTOFF:
        return "stressed"
    if composite >= CALM_TERCILE_CUTOFF:
        return "calm"
    return "neutral"


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    sector_closes = {symbol: dict(_sector_closes(connection, dataset_id, symbol)) for symbol in SECTORS}
    common_dates = sorted(set.intersection(*(set(closes) for closes in sector_closes.values())))
    print(f"Dataset: {dataset_id}")
    print(f"{len(SECTORS)} sectors, {len(common_dates)} common real trading days, "
          f"{common_dates[0]} to {common_dates[-1]}\n")

    trailing_returns: dict[str, list[float]] = {symbol: [] for symbol in SECTORS}
    for symbol in SECTORS:
        closes = [sector_closes[symbol][d] for d in common_dates]
        for i in range(LOOKBACK_DAYS, len(closes)):
            trailing_returns[symbol].append(closes[i] / closes[i - LOOKBACK_DAYS] - 1.0)

    n_days = len(common_dates) - LOOKBACK_DAYS
    real_flags: dict[str, list[bool]] = {symbol: [False] * n_days for symbol in SECTORS}
    for i in range(n_days):
        ranked = sorted(SECTORS, key=lambda s: trailing_returns[s][i], reverse=True)
        for symbol in ranked[:LEADERSHIP_SIZE]:
            real_flags[symbol][i] = True

    real_episodes: list[dict] = []
    for symbol in SECTORS:
        flags = real_flags[symbol]
        run = 0
        run_start = 0
        for i, flag in enumerate(flags):
            if flag:
                if run == 0:
                    run_start = i
                run += 1
            else:
                if run > 0:
                    real_episodes.append({"symbol": symbol, "start_index": run_start, "duration": run})
                run = 0
        # trailing open run at series end dropped (right-censored)

    real_durations = [e["duration"] for e in real_episodes]
    real_median = statistics.median(real_durations)
    print("=== Real leadership episodes ===")
    print(f"{len(real_durations)} real episodes across {len(SECTORS)} sectors")
    print(f"Real median duration: {real_median:.1f} trading days (mean {statistics.fmean(real_durations):.1f})\n")

    rng = random.Random(RANDOM_SEED)
    null_medians: list[float] = []
    for _ in range(PERMUTATION_REPS):
        null_flags = {symbol: [False] * n_days for symbol in SECTORS}
        for i in range(n_days):
            for symbol in rng.sample(SECTORS, LEADERSHIP_SIZE):
                null_flags[symbol][i] = True
        rep_durations: list[int] = []
        for symbol in SECTORS:
            rep_durations.extend(_episode_durations(null_flags[symbol]))
        if rep_durations:
            null_medians.append(statistics.median(rep_durations))

    ge_count = sum(1 for m in null_medians if m >= real_median)
    p_value = (ge_count + 1) / (len(null_medians) + 1)
    print(f"=== Permutation null ({PERMUTATION_REPS} reps, seed={RANDOM_SEED}) ===")
    print(f"Null median-of-medians: {statistics.median(null_medians):.1f} trading days "
          f"(range {min(null_medians):.1f}-{max(null_medians):.1f})")
    print(f"Real median ({real_median:.1f}) vs. null: empirical p={p_value:.4f} "
          f"({'SIGNIFICANT (real > null)' if p_value < 0.05 else 'not significant'})\n")

    print(f"=== Robustness: non-overlapping {LOOKBACK_DAYS}-day block persistence ===")
    blocks = _block_leaders(common_dates, sector_closes, LOOKBACK_DAYS)
    persisted = 0
    total_slots = 0
    for n in range(len(blocks) - 1):
        for sector in blocks[n]:
            total_slots += 1
            if sector in blocks[n + 1]:
                persisted += 1
    chance_rate = LEADERSHIP_SIZE / len(SECTORS)
    block_result = stats.binomtest(persisted, total_slots, p=chance_rate, alternative="greater")
    print(f"{len(blocks)} independent, non-overlapping blocks")
    print(f"P(leader in block N+1 | leader in block N): {persisted}/{total_slots} = {persisted / total_slots:.1%} "
          f"(chance = {chance_rate:.1%})")
    print(f"Binomial test vs. chance: p={block_result.pvalue:.4f} "
          f"({'SIGNIFICANT' if block_result.pvalue < 0.05 else 'not significant'})\n")

    print("=== Regime interaction ===")
    composite_series = _macro_composite_series(connection, dataset_id)
    if not composite_series:
        print("No real composite series available -- skipping regime interaction test.")
        return

    by_bucket: dict[str, list[int]] = {"stressed": [], "neutral": [], "calm": []}
    for episode in real_episodes:
        entry_date = common_dates[LOOKBACK_DAYS + episode["start_index"]]
        candidates = [(d, score) for d, score in composite_series if d <= entry_date]
        if not candidates:
            continue
        _, composite = max(candidates, key=lambda pair: pair[0])
        by_bucket[_regime_bucket(composite)].append(episode["duration"])

    for bucket, durations in by_bucket.items():
        if durations:
            print(f"{bucket}: n={len(durations)}, median={statistics.median(durations):.1f} trading days")
        else:
            print(f"{bucket}: n=0")

    groups = [durations for durations in by_bucket.values() if len(durations) >= 2]
    if len(groups) >= 2:
        h_stat, kw_p = stats.kruskal(*groups)
        print(f"\nKruskal-Wallis across regime buckets: H={h_stat:.3f}, p={kw_p:.4f} "
              f"({'SIGNIFICANT' if kw_p < 0.05 else 'not significant'})")
    else:
        print("\nToo few non-empty buckets for Kruskal-Wallis.")


if __name__ == "__main__":
    main()
