"""Scratch script for docs/hypotheses/short-term-mean-reversion.md (H-STREV01),
"Regime-conditioned" addendum section.

Same hypothesis, same universe, same method as short_term_mean_reversion.py
-- only addition: does the confirmed reversal IC strengthen or weaken across
macro_regime_composite's real, point-in-time state (stressed/neutral/calm)?
Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.short_term_mean_reversion_regime_conditioned
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.regime.scoring_v3 import CALM_TERCILE_CUTOFF, STRESSED_TERCILE_CUTOFF
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.research_lab.regime_conditioned_sleeve_return import _macro_composite_series

TRAILING_WINDOW_DAYS = 5  # same as short_term_mean_reversion.py -- not re-tuned
FORWARD_WINDOWS: tuple[tuple[str, int], ...] = (("1w_fwd", 5), ("2w_fwd", 10))


def _security_id_for(symbol: str, category: str) -> str:
    slug = symbol.lower().replace("-", "")
    if category == "crypto_reference":
        return f"ref-{slug}"
    if category == "mega_cap_equity":
        return f"us-equity-{slug}"
    return f"us-etf-{symbol.lower()}"


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

    composite_series = sorted(_macro_composite_series(connection, dataset_id), key=lambda pair: pair[0])

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols WHERE active = 1 "
        "AND category NOT IN ('macro_series', 'crypto_reference')"
    ).fetchall()

    results: list[dict] = []
    for label, forward_days in FORWARD_WINDOWS:
        by_bucket: dict[str, tuple[list[float], list[float]]] = {"stressed": ([], []), "neutral": ([], []), "calm": ([], [])}
        for row in staging_rows:
            security_id = _security_id_for(row["symbol"], row["category"])
            bar_rows = connection.execute(
                "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
                "AND close IS NOT NULL ORDER BY time",
                (dataset_id, security_id),
            ).fetchall()
            dates = [bar["time"] for bar in bar_rows]
            closes = [bar["close"] for bar in bar_rows]
            n = len(closes)

            pointer = -1
            for i in range(TRAILING_WINDOW_DAYS, n - forward_days, 2):
                past_close = closes[i - TRAILING_WINDOW_DAYS]
                now_close = closes[i]
                future_close = closes[i + forward_days]
                if past_close == 0 or now_close == 0:
                    continue
                now_date = dates[i]
                while pointer + 1 < len(composite_series) and composite_series[pointer + 1][0] <= now_date:
                    pointer += 1
                if pointer < 0:
                    continue
                bucket = _regime_bucket(composite_series[pointer][1])
                trailing_return = (now_close - past_close) / abs(past_close)
                forward_return = (future_close - now_close) / abs(now_close)
                by_bucket[bucket][0].append(trailing_return)
                by_bucket[bucket][1].append(forward_return)

        for bucket, (x, y) in by_bucket.items():
            if len(x) < 24:
                results.append({"label": label, "bucket": bucket, "status": "insufficient_data", "n": len(x)})
                continue
            r, p = pearson_significance(x, y)
            results.append({"label": label, "bucket": bucket, "status": "ok", "n": len(x), "correlation": r, "p_value": p})

    testable = [item for item in results if item["status"] == "ok"]
    adjusted, significant = benjamini_hochberg([item["p_value"] for item in testable])
    for item, adj_p, sig in zip(testable, adjusted, significant):
        item["adjusted_p"] = adj_p
        item["significant"] = sig

    print(f"Dataset: {dataset_id}\n")
    for item in results:
        if item["status"] == "insufficient_data":
            print(f"{item['label']:8s} {item['bucket']:9s} insufficient data (n={item['n']})")
            continue
        flag = "SIGNIFICANT" if item["significant"] else "not significant"
        print(f"{item['label']:8s} {item['bucket']:9s} n={item['n']:6d}  r={item['correlation']:+.4f}  "
              f"p={item['p_value']:.4f}  adj_p={item['adjusted_p']:.4f}  ({flag})")


if __name__ == "__main__":
    main()
