"""Scratch script for docs/hypotheses/dow-theory-risk-state.md (H-DOW02).

Real test: does a broken swing structure predict higher forward realized
VOLATILITY, independent of whether it predicts higher or lower forward
RETURN (dow-theory-trend-structure.md, H-DOW01a, already tested the return
question and rejected it -- this is a genuinely different claim, not a
revival). Same mechanical fractal swing detector as H-DOW01a's script.

Read-only against the sealed dataset -- never writes anywhere.

Run: .venv/bin/python -m backend.research_lab.dow_theory_risk_state
"""

from __future__ import annotations

import bisect
import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

FORWARD_DAYS = 21
SWING_WINDOW = 5  # bars each side -- identical to dow_theory_trend_structure.py


def _security_id_for(symbol: str, category: str) -> str:
    # Reproduced, not imported -- see backend/research_lab/README.md.
    slug = symbol.lower().replace("-", "")
    if category == "crypto_reference":
        return f"ref-{slug}"
    if category == "mega_cap_equity":
        return f"us-equity-{slug}"
    return f"us-etf-{symbol.lower()}"


def _swing_points(values: list[float], window: int, is_high: bool) -> tuple[list[int], list[float]]:
    # Identical to dow_theory_trend_structure.py's detector -- reproduced,
    # not imported, since research_lab scripts don't depend on each other
    # (each stays independently runnable and disposable).
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

    x: list[float] = []  # 1.0 = intact structure, 0.0 = broken
    y: list[float] = []  # forward realized volatility (stdev of daily returns over the forward window)
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
            confirm_cutoff = i - SWING_WINDOW
            high_count = bisect.bisect_right(swing_high_idx, confirm_cutoff)
            low_count = bisect.bisect_right(swing_low_idx, confirm_cutoff)
            if high_count < 2 or low_count < 2:
                continue
            latest_high, prev_high = swing_high_val[high_count - 1], swing_high_val[high_count - 2]
            latest_low, prev_low = swing_low_val[low_count - 1], swing_low_val[low_count - 2]

            forward_window = closes[i : i + FORWARD_DAYS + 1]
            forward_daily_returns = [
                (forward_window[k] - forward_window[k - 1]) / forward_window[k - 1]
                for k in range(1, len(forward_window))
                if forward_window[k - 1] != 0
            ]
            if len(forward_daily_returns) < 2:
                continue
            forward_vol = statistics.pstdev(forward_daily_returns)

            intact_uptrend = latest_high > prev_high and latest_low > prev_low
            x.append(1.0 if intact_uptrend else 0.0)
            y.append(forward_vol)

    if len(x) < 24 or sum(x) < 3 or (len(x) - sum(x)) < 3:
        print(f"Insufficient data or event days: n={len(x)}, intact days={sum(x)}.")
        return

    correlation, p_value = pearson_significance(x, y)
    adjusted_p_values, significant_flags = benjamini_hochberg([p_value], alpha=0.05)
    intact_vol = [yi for xi, yi in zip(x, y) if xi == 1.0]
    broken_vol = [yi for xi, yi in zip(x, y) if xi == 0.0]

    print(f"Dataset: {dataset_id}")
    print(
        f"Pearson r={correlation:+.4f} (adjusted p={adjusted_p_values[0]:.4f}, "
        f"{'SIGNIFICANT' if significant_flags[0] else 'not significant'}), n={len(x)} "
        f"(intact={int(sum(x))}, broken={len(x) - int(sum(x))})"
    )
    print(
        f"Mean forward {FORWARD_DAYS}-day realized volatility (daily stdev), intact structure="
        f"{statistics.fmean(intact_vol):.4%} vs. broken structure={statistics.fmean(broken_vol):.4%}"
    )


if __name__ == "__main__":
    main()
