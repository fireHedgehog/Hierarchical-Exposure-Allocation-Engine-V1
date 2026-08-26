"""Scratch script for docs/hypotheses/large-drop-reversion.md (H-CRASHREV01).

Real recovery-rate test: after a real SPY single-day close-to-close drop of
-3% or worse, does price recover to the pre-drop close within a short
window, at a rate meaningfully higher than the same recovery-rate computed
unconditionally (every day, not just >=3%-drop days)? Read-only against the
sealed dataset. Deliberately NOT reusing H-STREV01's confirmed average
reversal finding as evidence -- this is a different, stronger claim, tested
fresh at its own specification.

Run: .venv/bin/python -m backend.research_lab.large_drop_reversion
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import proportion_significance

SYMBOL = "SPY"
DROP_THRESHOLD = -0.03
WINDOWS = (5, 10, 20)


def _security_id_for(symbol: str) -> str:
    return f"us-etf-{symbol.lower()}"


def _recovery_rate(bars: list[dict], is_drop_day, window: int, use_high: bool) -> tuple[int, int]:
    hits = 0
    total = 0
    n = len(bars)
    for i in range(1, n - window):
        prev_close = bars[i - 1]["close"]
        today_close = bars[i]["close"]
        if prev_close is None or today_close is None or prev_close == 0:
            continue
        if not is_drop_day(today_close, prev_close):
            continue
        total += 1
        if use_high:
            recovered = any(
                bars[j]["high"] is not None and bars[j]["high"] >= prev_close for j in range(i, min(i + window, n))
            )
        else:
            recovered = any(
                bars[j]["close"] is not None and bars[j]["close"] >= prev_close for j in range(i, min(i + window, n))
            )
        if recovered:
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

    security_id = _security_id_for(SYMBOL)
    bar_rows = connection.execute(
        "SELECT high, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
        "AND close IS NOT NULL AND high IS NOT NULL ORDER BY time",
        (dataset_id, security_id),
    ).fetchall()
    bars = [{"high": row["high"], "close": row["close"]} for row in bar_rows]
    print(f"\n{SYMBOL} ({len(bars)} real daily bars):")

    for use_high, check_label in ((False, "close"), (True, "intraday high")):
        for window in WINDOWS:
            drop_hits, drop_total = _recovery_rate(
                bars, lambda c, p: (c - p) / p <= DROP_THRESHOLD, window, use_high
            )
            base_hits, base_total = _recovery_rate(bars, lambda c, p: True, window, use_high)
            if drop_total == 0 or base_total == 0:
                print(f"  check={check_label}, window={window}d: insufficient qualifying days (n_drop={drop_total})")
                continue
            diff, p_value = proportion_significance(drop_hits, drop_total, base_hits, base_total)
            drop_rate = drop_hits / drop_total
            base_rate = base_hits / base_total
            print(
                f"  check={check_label}, window={window}d: conditional recovery rate "
                f"{drop_rate:.1%} (n={drop_total} real >=3% drop days) vs. unconditional baseline "
                f"{base_rate:.1%} (n={base_total}) -- diff={diff:+.1%}, p={p_value:.4f} "
                f"({'SIGNIFICANT' if p_value < 0.05 else 'not significant'})"
            )


if __name__ == "__main__":
    main()
