"""Scratch script for docs/hypotheses/macro-research/volatility-outcome-predictors.md.

Layer 1 vs. layer 3's Volatility dimension: does each free input signal
predict VIXCLS's own forward change? Two windows (1m, 1q) since vol itself
mean-reverts faster than a typical macro cycle -- a single long window could
miss the real, faster dynamic. Continuous-target method, same shape as
H-MACRO02/04. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.volatility_outcome_predictors
"""

from __future__ import annotations

from datetime import date, timedelta

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

MIN_SAMPLES = 24
FORWARD_WINDOWS: tuple[tuple[str, int], ...] = (("1m_fwd", 21), ("1q_fwd", 91))
STRIDE_DAYS = 5

CANDIDATE_SERIES = [
    "INDPRO", "CPIAUCSL", "PPIACO", "PCEPILFE", "PAYEMS", "NFCI",
    "DGS10", "DGS30", "GDPC1", "MTSDS133FMS", "ICSA",
    "T10YIE", "T5YIE", "DFII10", "DFII30", "BAMLH0A0HYM2", "BAMLC0A0CM",
    "SOFR", "IORB", "DFEDTAR", "DFEDTARU", "DFEDTARL", "WTREGEN", "WALCL",
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

    vix = _series(connection, dataset_id, "VIXCLS")
    print(f"Dataset: {dataset_id}")
    print(f"VIXCLS (target): {len(vix)} real observations, {vix[0][0]} to {vix[-1][0]}")
    print()

    sample_points = vix[::STRIDE_DAYS]

    for window_label, forward_days in FORWARD_WINDOWS:
        print(f"=== Forward window: {window_label} ({forward_days} days) ===")
        raw = []
        for series_id in CANDIDATE_SERIES:
            indicator = _series(connection, dataset_id, series_id)
            if not indicator:
                raw.append({"series_id": series_id, "status": "no_data"})
                continue
            indicator_start = indicator[0][0]
            x: list[float] = []
            y: list[float] = []
            for observation_date, target_value in sample_points:
                if observation_date < indicator_start or target_value == 0:
                    continue
                future_target_date = (date.fromisoformat(observation_date) + timedelta(days=forward_days)).isoformat()
                future_value = _nearest_value_on_or_after(vix, future_target_date)
                if future_value is None:
                    continue
                indicator_value = _nearest_prior_value(indicator, observation_date)
                if indicator_value is None:
                    continue
                x.append(indicator_value)
                y.append((future_value - target_value) / abs(target_value))
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
        print()


if __name__ == "__main__":
    main()
