"""Scratch script for docs/hypotheses/macro-research/equity-outcome-predictors.md.

Layer 1 vs. layer 3's Equity dimension: does each free input signal's level
predict SPY's own forward return? Also the direct test of the user's own
"bad news is good news" intuition: if a real Fed-put mechanism exists,
stress indicators (NFCI/VIX up, breakevens falling) should show a
POSITIVE relationship with forward return (stress precedes intervention
precedes a rally), not the naive negative one. Read-only against the
sealed dataset.

Run: .venv/bin/python -m backend.research_lab.equity_outcome_predictors
"""

from __future__ import annotations

from datetime import date, timedelta

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

MIN_SAMPLES = 24
STRIDE_DAYS = 5
FORWARD_WINDOWS: tuple[tuple[str, int], ...] = (("1m_fwd", 21), ("3m_fwd", 63))

CANDIDATE_SERIES = [
    "INDPRO", "CPIAUCSL", "PPIACO", "PCEPILFE", "PAYEMS", "NFCI", "VIXCLS",
    "DGS10", "DGS30", "GDPC1", "MTSDS133FMS", "ICSA",
    "T10YIE", "T5YIE", "DFII10", "DFII30", "BAMLH0A0HYM2", "BAMLC0A0CM",
    "SOFR", "IORB", "DFEDTAR", "DFEDTARU", "DFEDTARL", "WTREGEN", "WALCL",
]


def _fred_series(connection, dataset_id: str, series_id: str) -> list[tuple[str, float]]:
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
    print(f"SPY: {len(spy)} real daily bars, {spy[0][0]} to {spy[-1][0]}")
    print()

    for window_label, forward_days in FORWARD_WINDOWS:
        print(f"=== Forward window: {window_label} ({forward_days} trading days) ===")
        raw = []
        for series_id in CANDIDATE_SERIES:
            indicator = _fred_series(connection, dataset_id, series_id)
            if not indicator:
                raw.append({"series_id": series_id, "status": "no_data"})
                continue
            indicator_start = indicator[0][0]
            x: list[float] = []
            y: list[float] = []
            for i in range(0, len(spy) - forward_days, STRIDE_DAYS):
                spy_date, spy_close = spy[i]
                if spy_date < indicator_start or spy_close == 0:
                    continue
                future_close = spy[i + forward_days][1]
                indicator_value = _nearest_prior_value(indicator, spy_date)
                if indicator_value is None:
                    continue
                x.append(indicator_value)
                y.append((future_close - spy_close) / spy_close)
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
