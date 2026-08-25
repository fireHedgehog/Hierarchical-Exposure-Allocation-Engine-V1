"""Scratch script for docs/hypotheses/short-term-mean-reversion.md (H-STREV01).

Real IC test: does an asset's own trailing ~1-week return have a real
NEGATIVE relationship with its near-term forward return (Jegadeesh 1990's
short-term reversal), tested at its own proper window -- not reused from the
longer-horizon momentum/vol scripts, to avoid hypothesizing after the
result. Read-only against the sealed dataset -- never writes anywhere.

Run: .venv/bin/python -m backend.research_lab.short_term_mean_reversion
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.engine.research.signal_validation import rank_information_coefficient

TRAILING_WINDOW_DAYS = 5  # ~1 trading week, matching Jegadeesh (1990)'s own horizon
# Tested at two short forward windows -- both shorter than the 21-day horizon
# used elsewhere in this project, deliberately: a reversal effect claimed to
# resolve within a few weeks should show up at a few-week forward window, not
# get diluted by a full month of unrelated subsequent news.
FORWARD_WINDOWS: tuple[tuple[str, int], ...] = (("1w_fwd", 5), ("2w_fwd", 10))


def _security_id_for(symbol: str, category: str) -> str:
    # Reproduced, not imported -- see backend/research_lab/README.md.
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
    for label, forward_days in FORWARD_WINDOWS:
        x: list[float] = []  # trailing weekly return (raw, not sign -- testing magnitude too)
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
            # stride=2 (not 5): the trailing window itself is only 5 days, so
            # a 5-day stride would leave almost no overlap to control for in
            # the first place -- still spaced out, just proportional to the
            # much shorter window being tested here.
            for i in range(TRAILING_WINDOW_DAYS, n - forward_days, 2):
                past_close = closes[i - TRAILING_WINDOW_DAYS]
                now_close = closes[i]
                future_close = closes[i + forward_days]
                if past_close == 0 or now_close == 0:
                    continue
                trailing_return = (now_close - past_close) / abs(past_close)
                forward_return = (future_close - now_close) / abs(now_close)
                x.append(trailing_return)
                y.append(forward_return)
        if len(x) < 24:
            raw.append({"label": label, "status": "insufficient_data", "sample_size": len(x)})
            continue
        correlation, p_value = pearson_significance(x, y)
        rank_correlation, rank_p_value = rank_information_coefficient(x, y)
        raw.append(
            {
                "label": label,
                "status": "ok",
                "sample_size": len(x),
                "correlation": correlation,
                "p_value": p_value,
                "rank_correlation": rank_correlation,
                "rank_p_value": rank_p_value,
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
            print(f"  {item['label']}: insufficient data ({item['sample_size']} samples)")
            continue
        print(
            f"  {item['label']}: r={item['correlation']:+.4f} (adjusted p={item['adjusted_p_value']:.4f}, "
            f"{'SIGNIFICANT' if item['significant'] else 'not significant'}), "
            f"Rank IC={item['rank_correlation']:+.4f}, n={item['sample_size']}"
        )


if __name__ == "__main__":
    main()
