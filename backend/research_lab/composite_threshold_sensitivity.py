"""Scratch script for docs/hypotheses/macro-research/composite-threshold-sensitivity.md.

Robustness check before wiring composite_forward_risk.py's design into
production: is the finding sensitive to the hand-picked -10% drawdown
threshold and tercile split, or does it hold across nearby reasonable
choices? Real, full 2004-2026 pooled data (not split -- this is a
robustness check on the *design*, not a fresh claim). Read-only against the
sealed dataset.

Run: .venv/bin/python -m backend.research_lab.composite_threshold_sensitivity
"""

from __future__ import annotations

import statistics
from datetime import date

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import proportion_significance

CLUSTERS: dict[str, list[tuple[str, float, bool, int]]] = {
    "growth_inflation": [
        ("INDPRO", 1.0, True, 6),
        ("PAYEMS", 1.0, True, 6),
        ("GDPC1", 1.0, True, 4),
        ("CPIAUCSL", -1.0, True, 6),
        ("PCEPILFE", -1.0, True, 6),
        ("PPIACO", -1.0, True, 6),
    ],
    "rate_level": [
        ("DGS10", -1.0, False, 60),
        ("DGS30", -1.0, False, 60),
        ("DFII10", -1.0, False, 60),
    ],
    "market_stress": [
        ("NFCI", -1.0, False, 26),
        ("VIXCLS", -1.0, False, 60),
    ],
}

FORWARD_WINDOWS = (63, 126)
DRAWDOWN_THRESHOLDS = (-0.08, -0.10, -0.12, -0.15)
BUCKET_SPLITS = (3, 4)  # tercile, quartile
STRIDE_DAYS = 21


def _series(connection, dataset_id: str, series_id: str, as_of: str) -> list[tuple[str, float]]:
    rows = connection.execute(
        "SELECT observation_date, value FROM fred_observations "
        "WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL AND observation_date <= ? "
        "ORDER BY observation_date",
        (dataset_id, series_id, as_of),
    ).fetchall()
    return [(row["observation_date"], row["value"]) for row in rows]


def _yoy_values(series: list[tuple[str, float]]) -> list[float]:
    by_date = dict(series)
    dates = sorted(by_date)
    values = []
    for i, d in enumerate(dates):
        target = (date.fromisoformat(d).replace(year=date.fromisoformat(d).year - 1)).isoformat()
        prior_dates = [pd for pd in dates[:i] if pd <= target]
        if not prior_dates:
            continue
        year_ago = by_date[max(prior_dates)]
        if year_ago == 0:
            continue
        values.append((by_date[d] - year_ago) / abs(year_ago))
    return values


def _zscore(series_id: str, sign: float, is_yoy: bool, window: int, connection, dataset_id: str, as_of: str) -> float | None:
    raw = _series(connection, dataset_id, series_id, as_of)
    if not raw:
        return None
    values = _yoy_values(raw) if is_yoy else [v for _, v in raw]
    if len(values) < window + 1:
        return None
    trailing = values[-(window + 1) : -1]
    latest = values[-1]
    mean = statistics.fmean(trailing)
    stdev = statistics.pstdev(trailing)
    if stdev < 1e-9:
        return None
    return sign * (latest - mean) / stdev


def _composite(connection, dataset_id: str, as_of: str) -> float | None:
    cluster_means = []
    for members in CLUSTERS.values():
        zs = [z for sid, sign, is_yoy, w in members if (z := _zscore(sid, sign, is_yoy, w, connection, dataset_id, as_of)) is not None]
        if zs:
            cluster_means.append(statistics.fmean(zs))
    return statistics.fmean(cluster_means) if cluster_means else None


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    spy_rows = connection.execute(
        "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = 'us-etf-spy' "
        "AND close IS NOT NULL ORDER BY time",
        (dataset_id,),
    ).fetchall()
    spy = [(row["time"], row["close"]) for row in spy_rows]
    print(f"Dataset: {dataset_id}")
    print(f"SPY: {len(spy)} real daily bars, {spy[0][0]} to {spy[-1][0]}\n")

    for forward_days in FORWARD_WINDOWS:
        composite_scores: list[float] = []
        forward_dds: list[float] = []
        for i in range(0, len(spy) - forward_days, STRIDE_DAYS):
            spy_date, spy_close = spy[i]
            composite = _composite(connection, dataset_id, spy_date)
            if composite is None or spy_close == 0:
                continue
            future_closes = [c for _, c in spy[i : i + forward_days + 1]]
            max_dd = min((c - spy_close) / spy_close for c in future_closes)
            composite_scores.append(composite)
            forward_dds.append(max_dd)

        n = len(composite_scores)
        print(f"=== Forward window: {forward_days} trading days (n={n}) ===")
        sorted_pairs = sorted(zip(composite_scores, forward_dds))

        for splits in BUCKET_SPLITS:
            bucket_size = n // splits
            stressed = sorted_pairs[:bucket_size]
            calm = sorted_pairs[-bucket_size:]
            label = "tercile" if splits == 3 else "quartile"
            print(f"  -- {label} split (bucket size {bucket_size}) --")
            for threshold in DRAWDOWN_THRESHOLDS:
                stressed_hits = sum(1 for _, dd in stressed if dd <= threshold)
                calm_hits = sum(1 for _, dd in calm if dd <= threshold)
                diff, p_value = proportion_significance(stressed_hits, len(stressed), calm_hits, len(calm))
                print(
                    f"     threshold {threshold:+.0%}: stressed {stressed_hits}/{len(stressed)}="
                    f"{stressed_hits / len(stressed):.1%}, calm {calm_hits}/{len(calm)}={calm_hits / len(calm):.1%}, "
                    f"diff={diff:+.1%}, p={p_value:.4f} ({'SIG' if p_value < 0.05 else 'ns'})"
                )
        print()


if __name__ == "__main__":
    main()
