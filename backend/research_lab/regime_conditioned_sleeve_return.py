"""Scratch script for
docs/hypotheses/asset-selection-research/regime-conditioned-sleeve-return.md.

H-SECT02: does macro_regime_composite's score real-correlate with a
sleeve's forward relative return (vs. SPY), across the 13-asset real
sleeve universe (GLD, SPY, QQQ, DIA, 9 sector ETFs)? A different
mechanism than H-SECT01 (rejected) -- that tested a sleeve's own trend
predicting its own future; this tests macro state predicting relative
return, independent of trend. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.regime_conditioned_sleeve_return
"""

from __future__ import annotations

import statistics
from datetime import date

from backend.database import connect, resolve_database_path
from backend.engine.regime import InsufficientSeriesDataError, compute_regime_v3
from backend.engine.regime.scoring_v3 import CALM_TERCILE_CUTOFF, STRESSED_TERCILE_CUTOFF
from backend.engine.regime.types import SeriesObservation
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

BENCHMARK = "SPY"
SLEEVES = ["GLD", "QQQ", "DIA", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
FORWARD_WINDOWS = (63, 126)  # ~3mo, ~6mo trading days
STRIDE_DAYS = 21  # ~monthly sampling, controls overlap -- an IC test, unlike H-SECT01's episode extraction

MACRO_SERIES = [
    "INDPRO", "PAYEMS", "GDPC1", "CPIAUCSL", "PCEPILFE", "PPIACO",
    "DGS10", "DGS30", "DFII10", "NFCI", "VIXCLS", "BAMLH0A0HYM2", "BAMLC0A0CM",
]


def _closes(connection, dataset_id: str, symbol: str) -> dict[str, float]:
    security_id = f"us-etf-{symbol.lower()}"
    rows = connection.execute(
        "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
        "AND close IS NOT NULL ORDER BY time",
        (dataset_id, security_id),
    ).fetchall()
    return {row["time"]: row["close"] for row in rows}


def _macro_composite_series(connection, dataset_id: str) -> list[tuple[str, float]]:
    """Same real, point-in-time composite series as
    section_leadership_persistence.py -- duplicated, not imported, since
    research_lab scripts don't share code across files (see that folder's
    README: duplication here is normal and expected)."""
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

    all_symbols = [BENCHMARK] + SLEEVES
    closes = {symbol: _closes(connection, dataset_id, symbol) for symbol in all_symbols}
    common_dates = sorted(set.intersection(*(set(c) for c in closes.values())))
    print(f"Dataset: {dataset_id}")
    print(f"{len(SLEEVES)} sleeves + {BENCHMARK} benchmark, {len(common_dates)} common real trading days, "
          f"{common_dates[0]} to {common_dates[-1]}")

    composite_series = _macro_composite_series(connection, dataset_id)
    print(f"{len(composite_series)} real point-in-time composite anchors\n")

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

            by_bucket: dict[str, list[float]] = {"stressed": [], "neutral": [], "calm": []}
            for score, rel_ret in zip(composite_scores, relative_returns):
                by_bucket[_regime_bucket(score)].append(rel_ret)

            results.append({
                "sleeve": sleeve, "forward_days": forward_days, "n": n,
                "correlation": correlation, "p_value": p_value, "by_bucket": by_bucket,
            })

    adjusted, significant = benjamini_hochberg([r["p_value"] for r in results])
    for r, adj_p, sig in zip(results, adjusted, significant):
        r["adjusted_p"] = adj_p
        r["significant"] = sig

    print(f"=== {len(results)} tests (sleeves x windows), Benjamini-Hochberg corrected ===\n")
    for r in sorted(results, key=lambda r: r["adjusted_p"]):
        flag = "SIGNIFICANT" if r["significant"] else "not significant"
        print(f"{r['sleeve']:5s} {r['forward_days']:3d}d  n={r['n']:3d}  r={r['correlation']:+.3f}  "
              f"p={r['p_value']:.4f}  adj_p={r['adjusted_p']:.4f}  ({flag})")

    sig_count = sum(1 for r in results if r["significant"])
    print(f"\n{sig_count} of {len(results)} significant after correction "
          f"(chance alone at alpha=0.05 would produce ~{0.05 * len(results):.1f})\n")

    for r in results:
        if r["significant"]:
            print(f"--- {r['sleeve']} {r['forward_days']}d, by regime tercile ---")
            for bucket in ("stressed", "neutral", "calm"):
                values = r["by_bucket"][bucket]
                if values:
                    print(f"  {bucket}: n={len(values)}, mean relative return={statistics.fmean(values):+.2%}")
                else:
                    print(f"  {bucket}: n=0")


if __name__ == "__main__":
    main()
