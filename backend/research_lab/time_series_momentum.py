"""Scratch script for docs/hypotheses/time-series-momentum.md (H-TSM01).

Real IC test: does an asset's own trailing-return SIGN predict its own
forward return, independent of how it ranks against peers? Read-only
against the sealed dataset (PRAGMA query_only=ON) -- never writes anywhere.

Run: .venv/bin/python -m backend.research_lab.time_series_momentum
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

FORWARD_DAYS = 21
LOOKBACKS: tuple[tuple[str, int], ...] = (("1m", 21), ("3m", 63), ("6m", 126), ("12m", 252))


def _security_id_for(symbol: str, category: str) -> str:
    # Reproduced, not imported -- research_lab never depends on production
    # repository/pipeline internals, only on engine/'s pure utilities. See
    # backend/research_lab/README.md.
    slug = symbol.lower().replace("-", "")
    if category == "crypto_reference":
        return f"ref-{slug}"
    if category == "mega_cap_equity":
        return f"us-equity-{slug}"
    return f"us-etf-{symbol.lower()}"


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols WHERE active = 1 "
        "AND category NOT IN ('macro_series', 'crypto_reference')"
    ).fetchall()

    raw = []
    for horizon, lookback in LOOKBACKS:
        x: list[float] = []
        y: list[float] = []
        for row in staging_rows:
            security_id = _security_id_for(row["symbol"], row["category"])
            bar_rows = connection.execute(
                "SELECT close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
                "AND close IS NOT NULL ORDER BY time",
                (dataset_id, security_id),
            ).fetchall()
            closes = [bar["close"] for bar in bar_rows]
            n = len(closes)
            # stride=5 matches momentum_v2.py's own pooling convention
            # (_pooled_ic_samples) -- consecutive-day windows overlap almost
            # completely (a 252-day window shifted by 1 day shares 251 days
            # with the previous one), which inflates the apparent sample size
            # and understates p-values if not spaced out. This reduces, not
            # removes, that overlap.
            for i in range(lookback, n - FORWARD_DAYS, 5):
                past_close = closes[i - lookback]
                now_close = closes[i]
                future_close = closes[i + FORWARD_DAYS]
                if past_close == 0 or now_close == 0:
                    continue
                trailing_return = (now_close - past_close) / abs(past_close)
                forward_return = (future_close - now_close) / abs(now_close)
                x.append(1.0 if trailing_return > 0 else 0.0)
                y.append(forward_return)
        if len(x) < 24:
            raw.append({"horizon": horizon, "status": "insufficient_data", "sample_size": len(x)})
            continue
        correlation, p_value = pearson_significance(x, y)
        raw.append(
            {
                "horizon": horizon,
                "status": "ok",
                "sample_size": len(x),
                "correlation": correlation,
                "p_value": p_value,
                "mean_forward_return_when_trailing_positive": sum(yi for xi, yi in zip(x, y) if xi == 1.0)
                / sum(1 for xi in x if xi == 1.0),
                "mean_forward_return_when_trailing_negative": sum(yi for xi, yi in zip(x, y) if xi == 0.0)
                / sum(1 for xi in x if xi == 0.0),
            }
        )

    testable = [item for item in raw if item["status"] == "ok"]
    adjusted_p_values, significant_flags = benjamini_hochberg([item["p_value"] for item in testable], alpha=0.05)
    for item, adjusted_p, sig in zip(testable, adjusted_p_values, significant_flags):
        item["adjusted_p_value"] = adjusted_p
        item["significant"] = sig

    print(f"Dataset: {dataset_id}")
    for item in raw:
        if item["status"] == "insufficient_data":
            print(f"  {item['horizon']}: insufficient data ({item['sample_size']} samples)")
            continue
        print(
            f"  {item['horizon']}: r={item['correlation']:+.4f}, adjusted p={item['adjusted_p_value']:.4f}, "
            f"{'SIGNIFICANT' if item['significant'] else 'not significant'}, n={item['sample_size']}, "
            f"mean fwd return trend-up={item['mean_forward_return_when_trailing_positive']:+.2%} "
            f"vs. trend-down={item['mean_forward_return_when_trailing_negative']:+.2%}"
        )


if __name__ == "__main__":
    main()
