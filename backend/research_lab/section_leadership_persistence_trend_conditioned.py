"""Scratch script for
docs/hypotheses/asset-selection-research/section-leadership-persistence.md
(H-SECT01), trend-conditioned addendum.

Same H, same non-overlapping-block method that already found real
quarterly leadership persistence is exactly chance-level pooled (33.3%
vs. 33.3%) -- now split by a real, standard, pre-specified market trend
filter (SPY price vs. its own 5/20-day moving averages), not a macro
regime. Direct test of a real market-participant question: does
trend-following persistence get cleaner specifically within a real
bull trend, or does it stay chance-level even there. Read-only against
the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.section_leadership_persistence_trend_conditioned
"""

from __future__ import annotations

from scipy import stats

from backend.database import connect, resolve_database_path
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, _closes
from backend.research_lab.section_leadership_persistence import LEADERSHIP_SIZE, LOOKBACK_DAYS, SECTORS, _block_leaders

MA_SHORT = 5
MA_LONG = 20


def _trend_regime(closes_ordered: list[float], index: int) -> str | None:
    if index < MA_LONG:
        return None
    ma_short = sum(closes_ordered[index - MA_SHORT + 1 : index + 1]) / MA_SHORT
    ma_long = sum(closes_ordered[index - MA_LONG + 1 : index + 1]) / MA_LONG
    price = closes_ordered[index]
    if price > ma_short > ma_long:
        return "bullish"
    if price < ma_short < ma_long:
        return "bearish"
    return "mixed"


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    all_symbols = [BENCHMARK] + SECTORS
    closes = {symbol: _closes(connection, dataset_id, symbol) for symbol in all_symbols}
    common_dates = sorted(set.intersection(*(set(c) for c in closes.values())))
    spy_ordered = [closes[BENCHMARK][d] for d in common_dates]

    print(f"Dataset: {dataset_id}")
    print(f"{len(common_dates)} common real trading days, {common_dates[0]} to {common_dates[-1]}\n")

    blocks = _block_leaders(common_dates, {s: closes[s] for s in SECTORS}, LOOKBACK_DAYS)
    print(f"{len(blocks)} real non-overlapping {LOOKBACK_DAYS}-day blocks\n")

    # block i's END date, index into common_dates, for real regime classification
    block_end_indices = [min((n + 1) * LOOKBACK_DAYS, len(common_dates) - 1) for n in range(len(blocks))]

    by_regime: dict[str, dict[str, int]] = {
        "bullish": {"persisted": 0, "total": 0},
        "bearish": {"persisted": 0, "total": 0},
        "mixed": {"persisted": 0, "total": 0},
    }
    skipped_no_regime = 0

    for n in range(len(blocks) - 1):
        regime = _trend_regime(spy_ordered, block_end_indices[n])
        if regime is None:
            skipped_no_regime += 1
            continue
        for sector in blocks[n]:
            by_regime[regime]["total"] += 1
            if sector in blocks[n + 1]:
                by_regime[regime]["persisted"] += 1

    chance_rate = LEADERSHIP_SIZE / len(SECTORS)
    print(f"Chance rate (3-of-9): {chance_rate:.1%}. Skipped {skipped_no_regime} early blocks (not enough history for a 20-day MA).\n")
    for regime, counts in by_regime.items():
        total = counts["total"]
        if total == 0:
            print(f"{regime:8s}: no real transitions in this regime")
            continue
        rate = counts["persisted"] / total
        result = stats.binomtest(counts["persisted"], total, p=chance_rate, alternative="two-sided")
        print(f"{regime:8s}: {counts['persisted']}/{total} = {rate:.1%} (vs. chance {chance_rate:.1%}), "
              f"p={result.pvalue:.4f} ({'SIGNIFICANT' if result.pvalue < 0.05 else 'not significant'})")


if __name__ == "__main__":
    main()
