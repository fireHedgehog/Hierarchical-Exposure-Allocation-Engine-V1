"""Scratch script for docs/hypotheses/macro-research/balance-sheet-predictors.md.

Balance sheet is a continuous stock/flow, unlike Rate's discrete FOMC steps
-- a naive "did WALCL move this week" event framework would mostly capture
routine operational noise (reserve-management bill purchases, technical
reinvestment), not real QE/QT decisions -- exactly the conflation the
framework README already flags. So this is a real, pooled, continuous IC
test instead: does each layer-1 indicator's level predict WALCL's own
forward 13-week (~1 quarter) percentage change? Read-only against the
sealed dataset.

Run: .venv/bin/python -m backend.research_lab.balance_sheet_predictors
"""

from __future__ import annotations

from datetime import date, timedelta

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

MIN_SAMPLES = 24
FORWARD_DAYS = 91  # ~13 weeks / one quarter
STRIDE_WEEKS = 4  # spaced sampling of WALCL's own weekly series, not every week

CANDIDATE_SERIES = [
    "INDPRO", "CPIAUCSL", "PPIACO", "PCEPILFE", "PAYEMS", "NFCI", "VIXCLS",
    "DGS10", "DGS30", "GDPC1", "MTSDS133FMS", "ICSA",
    "T10YIE", "T5YIE", "DFII10", "DFII30", "BAMLH0A0HYM2", "BAMLC0A0CM",
    "SOFR", "IORB", "DFEDTAR", "DFEDTARU", "DFEDTARL", "WTREGEN",
]


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


def _nearest_value_on_or_after(series: list[tuple[str, float]], target: str) -> float | None:
    for observation_date, value in series:
        if observation_date >= target:
            return value
    return None


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    walcl = _series(connection, dataset_id, "WALCL")
    print(f"Dataset: {dataset_id}")
    print(f"WALCL: {len(walcl)} real weekly observations, {walcl[0][0]} to {walcl[-1][0]}")
    print()

    sample_dates = walcl[:: max(1, STRIDE_WEEKS)]

    raw = []
    for series_id in CANDIDATE_SERIES:
        indicator = _series(connection, dataset_id, series_id)
        if not indicator:
            raw.append({"series_id": series_id, "status": "no_data"})
            continue
        indicator_start = indicator[0][0]
        x: list[float] = []
        y: list[float] = []
        for observation_date, walcl_value in sample_dates:
            if observation_date < indicator_start or walcl_value == 0:
                continue
            future_target = (date.fromisoformat(observation_date) + timedelta(days=FORWARD_DAYS)).isoformat()
            future_value = _nearest_value_on_or_after(walcl, future_target)
            if future_value is None:
                continue
            indicator_value = _nearest_prior_value(indicator, observation_date)
            if indicator_value is None:
                continue
            forward_change = (future_value - walcl_value) / abs(walcl_value)
            x.append(indicator_value)
            y.append(forward_change)
        if len(x) < MIN_SAMPLES:
            raw.append(
                {"series_id": series_id, "status": "insufficient_samples", "n": len(x), "indicator_start": indicator_start}
            )
            continue
        correlation, p_value = pearson_significance(x, y)
        raw.append({"series_id": series_id, "status": "ok", "n": len(x), "correlation": correlation, "p_value": p_value})

    testable = [item for item in raw if item["status"] == "ok"]
    if testable:
        adjusted, significant = benjamini_hochberg([item["p_value"] for item in testable], alpha=0.05)
        for item, adj, sig in zip(testable, adjusted, significant):
            item["adjusted_p_value"] = adj
            item["significant"] = sig

    for item in raw:
        if item["status"] == "no_data":
            print(f"  {item['series_id']}: NOT DONE -- no data fetched for this series")
        elif item["status"] == "insufficient_samples":
            print(
                f"  {item['series_id']}: NOT DONE -- only {item['n']} pooled samples (starts "
                f"{item['indicator_start']}); need >= {MIN_SAMPLES}"
            )
        else:
            print(
                f"  {item['series_id']}: r={item['correlation']:+.4f}, adjusted p={item['adjusted_p_value']:.4f} "
                f"({'SIGNIFICANT' if item['significant'] else 'not significant'}), n={item['n']}"
            )


if __name__ == "__main__":
    main()
