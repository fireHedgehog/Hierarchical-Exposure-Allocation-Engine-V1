"""Scratch script for docs/hypotheses/dow-theory-trend-structure.md (H-DOW01a).

Real IC test: does an intact Higher-High/Higher-Low swing structure predict
higher forward returns than a just-broken (Lower-High or Lower-Low)
structure? A mechanical, non-discretionary fractal swing detector, applied
point-in-time (a swing point only counts once enough bars have passed to
confirm it -- no look-ahead). Price-only -- volume confirmation is a
separate, later hypothesis (H-DOW01b), not tested here.

Read-only against the sealed dataset -- never writes anywhere.

Run: .venv/bin/python -m backend.research_lab.dow_theory_trend_structure
"""

from __future__ import annotations

import bisect

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

FORWARD_DAYS = 21
SWING_WINDOW = 5  # bars each side -- an 11-bar fractal, ~2 trading weeks total


def _security_id_for(symbol: str, category: str) -> str:
    # Reproduced, not imported -- see backend/research_lab/README.md.
    slug = symbol.lower().replace("-", "")
    if category == "crypto_reference":
        return f"ref-{slug}"
    if category == "mega_cap_equity":
        return f"us-equity-{slug}"
    return f"us-etf-{symbol.lower()}"


def _swing_points(values: list[float], window: int, is_high: bool) -> tuple[list[int], list[float]]:
    """Real fractal swing detector: index j is a swing high (low) if
    values[j] is the max (min) of the symmetric window around it. Returns
    (indices, values) in ascending index order -- naturally sorted, since j
    increases monotonically."""

    n = len(values)
    indices: list[int] = []
    swing_values: list[float] = []
    for j in range(window, n - window):
        segment = values[j - window : j + window + 1]
        if is_high:
            if values[j] == max(segment):
                indices.append(j)
                swing_values.append(values[j])
        else:
            if values[j] == min(segment):
                indices.append(j)
                swing_values.append(values[j])
    return indices, swing_values


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

    x: list[float] = []  # 1.0 = intact Higher-High/Higher-Low structure, 0.0 = broken
    y: list[float] = []  # forward return
    for row in staging_rows:
        security_id = _security_id_for(row["symbol"], row["category"])
        bar_rows = connection.execute(
            "SELECT close, high, low FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
            "AND close IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL ORDER BY time",
            (dataset_id, security_id),
        ).fetchall()
        closes = [bar["close"] for bar in bar_rows]
        highs = [bar["high"] for bar in bar_rows]
        lows = [bar["low"] for bar in bar_rows]
        n = len(closes)
        if n < 2 * SWING_WINDOW + FORWARD_DAYS + 10:
            continue

        swing_high_idx, swing_high_val = _swing_points(highs, SWING_WINDOW, is_high=True)
        swing_low_idx, swing_low_val = _swing_points(lows, SWING_WINDOW, is_high=False)

        for i in range(2 * SWING_WINDOW, n - FORWARD_DAYS, 5):  # stride=5, same overlap control as other scripts
            # A swing centered at j is confirmed by test index i only once
            # SWING_WINDOW bars have passed since j -- no look-ahead.
            confirm_cutoff = i - SWING_WINDOW
            high_count = bisect.bisect_right(swing_high_idx, confirm_cutoff)
            low_count = bisect.bisect_right(swing_low_idx, confirm_cutoff)
            if high_count < 2 or low_count < 2:
                continue
            latest_high, prev_high = swing_high_val[high_count - 1], swing_high_val[high_count - 2]
            latest_low, prev_low = swing_low_val[low_count - 1], swing_low_val[low_count - 2]
            if closes[i] == 0:
                continue
            intact_uptrend = latest_high > prev_high and latest_low > prev_low
            forward_return = (closes[i + FORWARD_DAYS] - closes[i]) / abs(closes[i])
            x.append(1.0 if intact_uptrend else 0.0)
            y.append(forward_return)

    if len(x) < 24 or sum(x) < 3 or (len(x) - sum(x)) < 3:
        print(f"Insufficient data or event days: n={len(x)}, intact days={sum(x)}.")
        return

    correlation, p_value = pearson_significance(x, y)
    adjusted_p_values, significant_flags = benjamini_hochberg([p_value], alpha=0.05)
    intact_returns = [yi for xi, yi in zip(x, y) if xi == 1.0]
    broken_returns = [yi for xi, yi in zip(x, y) if xi == 0.0]

    print(f"Dataset: {dataset_id}")
    print(
        f"Pearson r={correlation:+.4f} (adjusted p={adjusted_p_values[0]:.4f}, "
        f"{'SIGNIFICANT' if significant_flags[0] else 'not significant'}), n={len(x)} "
        f"(intact={int(sum(x))}, broken={len(x) - int(sum(x))})"
    )
    print(
        f"Mean {FORWARD_DAYS}-day forward return, intact HH/HL structure={sum(intact_returns) / len(intact_returns):+.2%} "
        f"vs. broken structure (LH/LL)={sum(broken_returns) / len(broken_returns):+.2%}"
    )


if __name__ == "__main__":
    main()
