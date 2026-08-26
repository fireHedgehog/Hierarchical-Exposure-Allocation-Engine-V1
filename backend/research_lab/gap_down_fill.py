"""Scratch script for docs/hypotheses/gap-down-fill.md (H-GAPFILL01).

Real fill-rate test: after SPY/QQQ opens with a real gap down, does price
trade back up to the pre-gap close within a short window, at a rate
meaningfully higher than the same fill-rate computed unconditionally (every
day, not just gap-down days)? Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.gap_down_fill
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import proportion_significance

SYMBOLS = ("SPY", "QQQ")
GAP_THRESHOLDS = (("any", 0.0), ("meaningful (>=0.3%)", 0.003))
WINDOWS = (5, 10)


def _security_id_for(symbol: str) -> str:
    return f"us-etf-{symbol.lower()}"


def _fill_rate(bars: list[dict], is_gap_day, window: int) -> tuple[int, int]:
    """Count of (qualifying, filled-within-window) over every eligible day i
    (needs a prior close at i-1 and window bars ahead)."""

    hits = 0
    total = 0
    n = len(bars)
    for i in range(1, n - window):
        prev_close = bars[i - 1]["close"]
        today_open = bars[i]["open"]
        if prev_close is None or today_open is None or prev_close == 0:
            continue
        if not is_gap_day(today_open, prev_close):
            continue
        total += 1
        filled = any(
            bars[j]["high"] is not None and bars[j]["high"] >= prev_close for j in range(i, min(i + window, n))
        )
        if filled:
            hits += 1
    return hits, total


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]
    print(f"Dataset: {dataset_id}")

    for symbol in SYMBOLS:
        security_id = _security_id_for(symbol)
        bar_rows = connection.execute(
            "SELECT open, high, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
            "AND close IS NOT NULL AND open IS NOT NULL AND high IS NOT NULL ORDER BY time",
            (dataset_id, security_id),
        ).fetchall()
        bars = [{"open": row["open"], "high": row["high"], "close": row["close"]} for row in bar_rows]
        print(f"\n{symbol} ({len(bars)} real daily bars):")

        for gap_label, threshold in GAP_THRESHOLDS:
            for window in WINDOWS:
                gap_hits, gap_total = _fill_rate(
                    bars, lambda o, c, t=threshold: o < c * (1 - t), window
                )
                base_hits, base_total = _fill_rate(bars, lambda o, c: True, window)
                if gap_total == 0 or base_total == 0:
                    print(f"  gap={gap_label}, window={window}d: insufficient qualifying days")
                    continue
                diff, p_value = proportion_significance(gap_hits, gap_total, base_hits, base_total)
                gap_rate = gap_hits / gap_total
                base_rate = base_hits / base_total
                print(
                    f"  gap={gap_label}, window={window}d: conditional fill rate "
                    f"{gap_rate:.1%} (n={gap_total}) vs. unconditional baseline {base_rate:.1%} "
                    f"(n={base_total}) -- diff={diff:+.1%}, p={p_value:.4f} "
                    f"({'SIGNIFICANT' if p_value < 0.05 else 'not significant'})"
                )


if __name__ == "__main__":
    main()
