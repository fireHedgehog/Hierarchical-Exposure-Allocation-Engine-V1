"""Scratch script for docs/hypotheses/macro-research/composite-face-validity-backtest.md.

Face-validity backtest of composite-methodology-v1.md's proposed design:
real z-score (value - trailing_mean) / trailing_stdev per indicator,
point-in-time correct (only data available as-of each test date), averaged
within 3 clusters (policy-operations cluster excluded -- ambiguous sign,
named in the design doc, not guessed here), then averaged across clusters.
Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.composite_face_validity_backtest
"""

from __future__ import annotations

import statistics
from datetime import date

from backend.database import connect, resolve_database_path

# key: (series_id, sign, is_yoy, trailing_window_periods)
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
        ("BAMLH0A0HYM2", -1.0, False, 20),
        ("BAMLC0A0CM", -1.0, False, 20),
    ],
}

TEST_DATES = [
    ("2008-10-15", "2008 Lehman aftermath", "known risk-off"),
    ("2020-03-23", "2020 COVID crash trough", "known risk-off"),
    ("2021-11-15", "2021 late-cycle top", "known risk-on (late-cycle)"),
    ("2022-10-14", "2022 hiking-cycle trough", "known risk-off"),
    ("2026-08-25", "most recent real data", "not pre-judged -- the actual test"),
]


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


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]
    print(f"Dataset: {dataset_id}\n")

    for as_of, label, known in TEST_DATES:
        cluster_scores: dict[str, float | None] = {}
        detail: dict[str, list[str]] = {}
        for cluster_name, members in CLUSTERS.items():
            zs = []
            member_detail = []
            for series_id, sign, is_yoy, window in members:
                z = _zscore(series_id, sign, is_yoy, window, connection, dataset_id, as_of)
                if z is not None:
                    zs.append(z)
                    member_detail.append(f"{series_id}={z:+.2f}")
            cluster_scores[cluster_name] = statistics.fmean(zs) if zs else None
            detail[cluster_name] = member_detail
        valid = [v for v in cluster_scores.values() if v is not None]
        composite = statistics.fmean(valid) if valid else None
        direction = "RISK-ON" if composite and composite > 0.15 else "RISK-OFF" if composite and composite < -0.15 else "NEUTRAL"
        print(f"{as_of} ({label}) -- known: {known}")
        for cluster_name, score in cluster_scores.items():
            score_str = f"{score:+.2f}" if score is not None else "n/a"
            print(f"    {cluster_name}: {score_str}  [{', '.join(detail[cluster_name]) or 'no data'}]")
        composite_str = f"{composite:+.2f}" if composite is not None else "n/a"
        print(f"    COMPOSITE: {composite_str} -> {direction}\n")


if __name__ == "__main__":
    main()
