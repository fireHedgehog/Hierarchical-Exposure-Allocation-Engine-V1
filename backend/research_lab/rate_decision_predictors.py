"""Scratch script for docs/hypotheses/macro-research/rate-decision-predictors.md.

Real ground truth, derived directly from data, no hand-curated FOMC
calendar: every day the Fed funds target level actually changes is a real
hike (+1) or cut (-1) event. DFEDTAR (single target, pre-2008-12-16) +
DFEDTARU/DFEDTARL midpoint (target range, after) give one continuous real
series, 2004-2026. Holds are deliberately NOT classified in this v1 -- that
needs a real FOMC meeting calendar this project doesn't have; see the
hypothesis paper for why that's a disclosed limitation, not an oversight.

For every other layer-1 indicator, real Pearson test: does the indicator's
level (nearest real prior observation) ahead of each real event correlate
with the event's direction? Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.rate_decision_predictors
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

MIN_EVENTS = 10  # a real, small, disclosed floor -- not the 24 used for large pooled continuous tests

# Every layer-1 indicator fetched into production as of 2026-08-27, minus the
# 3 ground-truth rate series themselves.
CANDIDATE_SERIES = [
    "INDPRO", "CPIAUCSL", "PPIACO", "PCEPILFE", "PAYEMS", "NFCI", "VIXCLS", "DGS10",
    "WALCL", "WTREGEN", "DGS30", "GDPC1", "MTSDS133FMS", "ICSA",
    "T10YIE", "T5YIE", "DFII10", "DFII30", "BAMLH0A0HYM2", "BAMLC0A0CM", "SOFR", "IORB",
]


def _series(connection, dataset_id: str, series_id: str) -> list[tuple[str, float]]:
    rows = connection.execute(
        "SELECT observation_date, value FROM fred_observations "
        "WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL ORDER BY observation_date",
        (dataset_id, series_id),
    ).fetchall()
    return [(row["observation_date"], row["value"]) for row in rows]


def _target_rate_midpoint(connection, dataset_id: str) -> list[tuple[str, float]]:
    pre = _series(connection, dataset_id, "DFEDTAR")
    upper = dict(_series(connection, dataset_id, "DFEDTARU"))
    lower = dict(_series(connection, dataset_id, "DFEDTARL"))
    post_dates = sorted(set(upper) & set(lower))
    post = [(d, (upper[d] + lower[d]) / 2) for d in post_dates]
    # DFEDTAR's real history ends 2008-12-15; post-regime dates start
    # 2008-12-16 -- concatenating, not blending, at the real regime switch.
    combined = pre + post
    combined.sort(key=lambda item: item[0])
    return combined


def _real_rate_events(midpoint: list[tuple[str, float]]) -> list[tuple[str, int]]:
    """A real event on every date the level actually changed from the prior
    real observation -- hike (+1) or cut (-1). No hold classification (see
    module docstring)."""

    events: list[tuple[str, int]] = []
    for i in range(1, len(midpoint)):
        prev_date, prev_value = midpoint[i - 1]
        date, value = midpoint[i]
        if value > prev_value:
            events.append((date, 1))
        elif value < prev_value:
            events.append((date, -1))
    return events


def _nearest_prior_value(series: list[tuple[str, float]], as_of: str) -> float | None:
    result = None
    for date, value in series:
        if date > as_of:
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

    midpoint = _target_rate_midpoint(connection, dataset_id)
    events = _real_rate_events(midpoint)
    hikes = sum(1 for _, direction in events if direction == 1)
    cuts = sum(1 for _, direction in events if direction == -1)
    print(f"Dataset: {dataset_id}")
    print(f"Real rate-change events derived: {len(events)} ({hikes} hikes, {cuts} cuts), {midpoint[0][0]} to {midpoint[-1][0]}")
    print()

    raw = []
    for series_id in CANDIDATE_SERIES:
        indicator = _series(connection, dataset_id, series_id)
        if not indicator:
            raw.append({"series_id": series_id, "status": "no_data"})
            continue
        indicator_start = indicator[0][0]
        x: list[float] = []
        y: list[float] = []
        for event_date, direction in events:
            if event_date < indicator_start:
                continue  # event predates this indicator's real coverage
            value = _nearest_prior_value(indicator, event_date)
            if value is None:
                continue
            x.append(value)
            y.append(float(direction))
        if len(x) < MIN_EVENTS:
            raw.append(
                {
                    "series_id": series_id,
                    "status": "insufficient_events",
                    "n": len(x),
                    "indicator_start": indicator_start,
                }
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
        elif item["status"] == "insufficient_events":
            print(
                f"  {item['series_id']}: NOT DONE -- only {item['n']} real rate-change events fall within this "
                f"indicator's real coverage window (starts {item['indicator_start']}); need >= {MIN_EVENTS}"
            )
        else:
            print(
                f"  {item['series_id']}: r={item['correlation']:+.4f}, adjusted p={item['adjusted_p_value']:.4f} "
                f"({'SIGNIFICANT' if item['significant'] else 'not significant'}), n={item['n']}"
            )


if __name__ == "__main__":
    main()
