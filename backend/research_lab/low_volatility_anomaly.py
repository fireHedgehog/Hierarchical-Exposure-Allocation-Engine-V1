"""Scratch script for docs/hypotheses/low-volatility-anomaly.md (H-LOWVOL01).

Real IC test: does an asset's trailing realized volatility (inverted, so
"lower vol = higher signal") predict its own forward return, cross-
sectionally? Read-only against the sealed dataset -- never writes anywhere.

Run: .venv/bin/python -m backend.research_lab.low_volatility_anomaly
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance
from backend.engine.research.signal_validation import rank_information_coefficient

FORWARD_DAYS = 21
VOL_WINDOW_DAYS = 63  # ~3 trading months, a standard realized-vol lookback


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

    x: list[float] = []  # inverted realized vol (higher = calmer)
    y: list[float] = []  # forward return
    for row in staging_rows:
        security_id = _security_id_for(row["symbol"], row["category"])
        bar_rows = connection.execute(
            "SELECT close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
            "AND close IS NOT NULL ORDER BY time",
            (dataset_id, security_id),
        ).fetchall()
        closes = [bar["close"] for bar in bar_rows]
        n = len(closes)
        for i in range(VOL_WINDOW_DAYS, n - FORWARD_DAYS, 5):  # stride=5, same overlap-control as the momentum script
            window = closes[i - VOL_WINDOW_DAYS : i + 1]
            daily_returns = [
                (window[j] - window[j - 1]) / window[j - 1] for j in range(1, len(window)) if window[j - 1] != 0
            ]
            if len(daily_returns) < 2:
                continue
            realized_vol = statistics.pstdev(daily_returns)
            if realized_vol <= 0 or closes[i] == 0:
                continue
            forward_return = (closes[i + FORWARD_DAYS] - closes[i]) / abs(closes[i])
            x.append(-realized_vol)  # inverted: higher x = calmer = the anomaly's predicted-better bucket
            y.append(forward_return)

    if len(x) < 24:
        print(f"Insufficient data: only {len(x)} paired samples.")
        return

    correlation, p_value = pearson_significance(x, y)
    rank_correlation, rank_p_value = rank_information_coefficient(x, y)
    adjusted_p_values, significant_flags = benjamini_hochberg([p_value], alpha=0.05)

    # Simple, human-readable check: split into vol terciles, compare mean forward return.
    paired = sorted(zip(x, y), key=lambda pair: pair[0])  # ascending inverted-vol = descending vol
    n = len(paired)
    high_vol_third = [ret for _, ret in paired[: n // 3]]
    low_vol_third = [ret for _, ret in paired[-(n // 3) :]]

    print(f"Dataset: {dataset_id}")
    print(
        f"Pearson r={correlation:+.4f} (adjusted p={adjusted_p_values[0]:.4f}, "
        f"{'SIGNIFICANT' if significant_flags[0] else 'not significant'}), n={len(x)}"
    )
    print(f"Rank IC={rank_correlation:+.4f} (raw p={rank_p_value:.4f}, not itself corrected)")
    print(
        f"Mean {FORWARD_DAYS}-day forward return, calmest third={statistics.fmean(low_vol_third):+.2%} "
        f"vs. most volatile third={statistics.fmean(high_vol_third):+.2%}"
    )


if __name__ == "__main__":
    main()
