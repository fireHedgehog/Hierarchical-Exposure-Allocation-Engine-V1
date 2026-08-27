"""Scratch script for docs/hypotheses/macro-research/indicator-redundancy.md.

The prerequisite the user asked for before any composite: are the 26
layer-1 indicators actually ~26 independent signals, or a much smaller
number of latent factors wearing different names? Real pairwise
correlation + effective-number-of-bets (signal_validation.py, already
proven on the original 8 macro factors and on momentum horizons) applied
to this indicator set for the first time.

Two honest passes, not one forced window: a deep-history pass (indicators
with ~full 2004-2026 coverage) and a recent pass (all 26, bounded to the
shortest real history in the set, 2023-08-28+) -- pooling them into one
window would either truncate 20 years of real history or silently drop the
newest series. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.macro_indicator_redundancy
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.signal_validation import (
    effective_number_of_bets,
    pairwise_correlation_matrix,
    redundancy_pairs,
)

DEEP_HISTORY_SERIES = [
    "INDPRO", "CPIAUCSL", "PPIACO", "PCEPILFE", "PAYEMS", "NFCI", "VIXCLS",
    "DGS10", "DGS30", "GDPC1", "MTSDS133FMS", "ICSA",
    "T10YIE", "T5YIE", "DFII10", "WTREGEN", "WALCL",
]
ALL_SERIES = DEEP_HISTORY_SERIES + [
    "DFII30", "BAMLH0A0HYM2", "BAMLC0A0CM", "SOFR", "IORB", "DTWEXBGS",
]
RECENT_WINDOW_START = "2023-08-28"  # the shortest real history in ALL_SERIES (credit spreads)
STRIDE = 4  # weekly-equivalent sampling of a daily/weekly grid


def _series(connection, dataset_id: str, series_id: str) -> list[tuple[str, float]]:
    rows = connection.execute(
        "SELECT observation_date, value FROM fred_observations "
        "WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL ORDER BY observation_date",
        (dataset_id, series_id),
    ).fetchall()
    return [(row["observation_date"], row["value"]) for row in rows]


def _nearest_prior_value(series: list[tuple[str, float]], as_of: str) -> float | None:
    result = None
    for observation_date, value in series:
        if observation_date > as_of:
            break
        result = value
    return result


def _aligned_series_by_key(
    connection, dataset_id: str, series_ids: list[str], grid_dates: list[str]
) -> dict[str, list[float]]:
    by_key: dict[str, list[float]] = {}
    fetched = {sid: _series(connection, dataset_id, sid) for sid in series_ids}
    valid_dates = []
    for grid_date in grid_dates:
        values = {sid: _nearest_prior_value(fetched[sid], grid_date) for sid in series_ids}
        if all(v is not None for v in values.values()):
            valid_dates.append(grid_date)
    for sid in series_ids:
        by_key[sid] = [_nearest_prior_value(fetched[sid], d) for d in valid_dates]
    return by_key, len(valid_dates)


def _report(title: str, series_by_key: dict[str, list[float]], n: int) -> None:
    print(f"=== {title} (n={n} aligned dates, {len(series_by_key)} indicators) ===")
    matrix = pairwise_correlation_matrix(series_by_key)
    keys = sorted(series_by_key)
    enb = effective_number_of_bets(keys, matrix)
    print(f"Effective number of bets: {enb:.2f} of {len(keys)} raw indicators" if enb is not None else "ENB: not computable")
    flags = redundancy_pairs(matrix, threshold=0.7)
    print(f"Redundant pairs (|r| >= 0.7): {len(flags)}")
    for flag in flags:
        print(f"  {flag.key_a} <-> {flag.key_b}: r={flag.correlation:+.3f}")
    print()


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

    walcl = _series(connection, dataset_id, "WALCL")
    deep_grid = [d for d, _ in walcl[::STRIDE]]
    deep_by_key, deep_n = _aligned_series_by_key(connection, dataset_id, DEEP_HISTORY_SERIES, deep_grid)
    _report("Deep-history pass (17 indicators, 2004-2026)", deep_by_key, deep_n)

    recent_grid = [d for d in deep_grid if d >= RECENT_WINDOW_START]
    recent_by_key, recent_n = _aligned_series_by_key(connection, dataset_id, ALL_SERIES, recent_grid)
    _report("Recent pass (all 23 indicators, 2023-2025)", recent_by_key, recent_n)


if __name__ == "__main__":
    main()
