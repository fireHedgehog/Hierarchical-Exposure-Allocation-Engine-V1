"""Scratch script -- real robustness re-check of this project's two most
consequential macro findings (H-MACRO09, H-MACRO11 corrected) against a
real, documented statistical gap: STRIDE_DAYS=21 sampling against 63/126
day forward windows still leaves real overlap between adjacent samples,
so Pearson/Fisher p-values (which assume independent observations)
likely overstate significance. Real fix here: a moving-BLOCK permutation
test -- shuffle contiguous blocks of the outcome series (not individual
points), which preserves each block's own real autocorrelation
structure while destroying the real x/y relationship, giving an
empirical p-value that doesn't assume independence. Read-only against
the sealed dataset. See docs/hypotheses/README.md's "Known methodology
limitations" section for the full context this addresses.

Run: .venv/bin/python -m backend.research_lab.macro_significance_robustness_check
"""

from __future__ import annotations

import math
import random
import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import pearson_significance
from backend.research_lab.macro_factor_breadth_test import _per_factor_series
from backend.research_lab.macro_factor_breadth_test_drawdown_target import DRAWDOWN_THRESHOLD, FORWARD_DAYS
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, STRIDE_DAYS, _closes, _macro_composite_series
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE

PERMUTATION_REPS = 2000
RANDOM_SEED = 20260828  # disclosed, fixed for reproducibility


def _block_permutation_p_value(x: list[float], y: list[float], block_size: int, reps: int = PERMUTATION_REPS) -> tuple[float, float]:
    """Real observed r, then a real empirical two-sided p-value from
    shuffling BLOCKS of y (not individual points) relative to x --
    preserves each block's own real autocorrelation, destroys the real
    cross-series relationship. block_size = ceil(forward_days /
    stride_days), the real number of adjacent strided samples that share
    at least one day of their forward window."""
    observed_r, _ = pearson_significance(x, y)
    n = len(y)
    blocks = [y[i : i + block_size] for i in range(0, n, block_size)]
    rng = random.Random(RANDOM_SEED)
    ge_count = 0
    valid_reps = 0
    for _ in range(reps):
        shuffled = blocks[:]
        rng.shuffle(shuffled)
        shuffled_y = [v for block in shuffled for v in block][:n]
        if len(shuffled_y) < 3:
            continue
        r, _ = pearson_significance(x[: len(shuffled_y)], shuffled_y)
        valid_reps += 1
        if abs(r) >= abs(observed_r):
            ge_count += 1
    p_value = (ge_count + 1) / (valid_reps + 1) if valid_reps else float("nan")
    return observed_r, p_value


def _forward_drawdown_indicator(spy_dates: list[str], spy_closes: dict[str, float], anchor_date: str, forward_days: int) -> float | None:
    candidates = [d for d in spy_dates if d >= anchor_date]
    if not candidates:
        return None
    start_date = candidates[0]
    start_index = spy_dates.index(start_date)
    if start_index + forward_days >= len(spy_dates):
        return None
    start_close = spy_closes[start_date]
    future_closes = [spy_closes[spy_dates[i]] for i in range(start_index, start_index + forward_days + 1)]
    max_dd = min((c - start_close) / start_close for c in future_closes)
    return 1.0 if max_dd <= DRAWDOWN_THRESHOLD else 0.0


def _recheck_h_macro09(connection, dataset_id: str) -> None:
    print("=" * 70)
    print("H-MACRO09 re-check: composite vs. real forward SPY drawdown indicator")
    print("=" * 70)
    composite_series = _macro_composite_series(connection, dataset_id)
    spy_closes = _closes(connection, dataset_id, BENCHMARK)
    spy_dates = sorted(spy_closes)

    for forward_days in (63, 126):
        block_size = math.ceil(forward_days / STRIDE_DAYS)
        xs: list[float] = []
        ys: list[float] = []
        for i in range(0, len(spy_dates) - forward_days, STRIDE_DAYS):
            anchor_date = spy_dates[i]
            candidates = [(d, s) for d, s in composite_series if d <= anchor_date]
            if not candidates:
                continue
            composite = max(candidates, key=lambda pair: pair[0])[1]
            indicator = _forward_drawdown_indicator(spy_dates, spy_closes, anchor_date, forward_days)
            if indicator is None:
                continue
            xs.append(composite)
            ys.append(indicator)

        original_r, original_p = pearson_significance(xs, ys)
        block_r, block_p = _block_permutation_p_value(xs, ys, block_size)
        print(f"\n{forward_days}d forward window, n={len(xs)}, block_size={block_size} "
              f"({PERMUTATION_REPS} block-permutation reps)")
        print(f"  Naive Pearson:      r={original_r:+.3f}  p={original_p:.4f}  "
              f"({'SIGNIFICANT' if original_p < 0.05 else 'not significant'})")
        print(f"  Block-permutation:  r={block_r:+.3f}  p={block_p:.4f}  "
              f"({'SIGNIFICANT' if block_p < 0.05 else 'not significant'})")


def _recheck_h_macro11(connection, dataset_id: str) -> None:
    print("\n" + "=" * 70)
    print("H-MACRO11 re-check: cluster-equal vs. IC-weighted composite, real drawdown target, OOS only")
    print("=" * 70)
    series, factor_keys = _per_factor_series(connection, dataset_id)
    spy_closes = _closes(connection, dataset_id, BENCHMARK)
    spy_dates = sorted(spy_closes)

    in_sample_series = [s for s in series if s[0] < SPLIT_DATE]
    oos_series = [s for s in series if s[0] >= SPLIT_DATE]

    factor_ic: dict[str, float] = {}
    for key in factor_keys:
        xs, ys = [], []
        for anchor, contributions, _ in in_sample_series:
            if key not in contributions:
                continue
            indicator = _forward_drawdown_indicator(spy_dates, spy_closes, anchor, FORWARD_DAYS)
            if indicator is None:
                continue
            xs.append(contributions[key])
            ys.append(indicator)
        if len(xs) >= 3 and len(set(ys)) > 1:
            r, _ = pearson_significance(xs, ys)
            factor_ic[key] = r

    def _ic_weighted(contributions: dict[str, float]) -> float:
        total_abs_ic = sum(abs(factor_ic.get(k, 0.0)) for k in contributions)
        if total_abs_ic < 1e-9:
            return 0.0
        return sum(abs(factor_ic.get(k, 0.0)) * v for k, v in contributions.items()) / total_abs_ic

    block_size = math.ceil(FORWARD_DAYS / STRIDE_DAYS)
    for name, score_fn in [("cluster-equal", lambda c, cluster: cluster), ("IC-weighted", lambda c, cluster: _ic_weighted(c))]:
        xs, ys = [], []
        for anchor, contributions, cluster_composite in oos_series:
            indicator = _forward_drawdown_indicator(spy_dates, spy_closes, anchor, FORWARD_DAYS)
            if indicator is None:
                continue
            xs.append(score_fn(contributions, cluster_composite))
            ys.append(indicator)
        if len(xs) < 6:
            print(f"\n{name}: insufficient OOS data")
            continue
        original_r, original_p = pearson_significance(xs, ys)
        block_r, block_p = _block_permutation_p_value(xs, ys, block_size)
        print(f"\n{name} (OOS, n={len(xs)}, block_size={block_size}):")
        print(f"  Naive Pearson:      r={original_r:+.3f}  p={original_p:.4f}  "
              f"({'SIGNIFICANT' if original_p < 0.05 else 'not significant'})")
        print(f"  Block-permutation:  r={block_r:+.3f}  p={block_p:.4f}  "
              f"({'SIGNIFICANT' if block_p < 0.05 else 'not significant'})")


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

    _recheck_h_macro09(connection, dataset_id)
    _recheck_h_macro11(connection, dataset_id)


if __name__ == "__main__":
    main()
