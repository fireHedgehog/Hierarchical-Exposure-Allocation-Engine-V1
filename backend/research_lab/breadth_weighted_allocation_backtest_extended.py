"""Scratch script for
docs/hypotheses/asset-selection-research/regime-tilted-allocation-backtest.md
(H-SECT04), v3: extended universe (adds SMH, IGV) breadth test.

Same real method as breadth_weighted_allocation_backtest.py (v2) --
walk-forward IC, long-only IC-weighted score, real PCA-based effective
breadth -- run again on a bigger, real universe. BTC-USD deliberately
excluded from the tradable book (this project's own existing rule:
"research reference only, never a position candidate," roadmap.md) but
its own raw IC is reported for information, not included in the
backtest. Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.breadth_weighted_allocation_backtest_extended
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import pearson_significance
from backend.engine.research.signal_validation import effective_number_of_bets, pairwise_correlation_matrix
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, _closes, _macro_composite_series
from backend.research_lab.regime_conditioned_sleeve_return import SLEEVES as CORE_SLEEVES
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE

TRADABLE_SLEEVES = CORE_SLEEVES + ["SMH", "IGV"]
REFERENCE_ONLY = ["BTC-USD"]  # never part of the tradable book, info only
IC_WINDOW = 126
STRIDE_DAYS = 21
PERIODS_PER_YEAR = 252 / STRIDE_DAYS


def _composite_at(composite_series, date):
    candidates = [(d, s) for d, s in composite_series if d <= date]
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def _real_ic(dates, closes, composite_series, symbol):
    composite_scores, relative_returns = [], []
    for i in range(0, len(dates) - IC_WINDOW, STRIDE_DAYS):
        anchor_date = dates[i]
        composite = _composite_at(composite_series, anchor_date)
        if composite is None:
            continue
        start_date, end_date = dates[i], dates[i + IC_WINDOW]
        if start_date not in closes[symbol] or end_date not in closes[symbol]:
            continue
        symbol_return = closes[symbol][end_date] / closes[symbol][start_date] - 1.0
        benchmark_return = closes[BENCHMARK][end_date] / closes[BENCHMARK][start_date] - 1.0
        composite_scores.append(composite)
        relative_returns.append(symbol_return - benchmark_return)
    if len(composite_scores) < 3:
        return None, 0
    r, _ = pearson_significance(composite_scores, relative_returns)
    return r, len(composite_scores)


def _run_backtest(dates, closes, composite_series, ics):
    base_weight = 1.0 / len(TRADABLE_SLEEVES)
    period_returns, turnovers = [], []
    previous_weights = None
    for i in range(0, len(dates) - STRIDE_DAYS, STRIDE_DAYS):
        anchor_date = dates[i]
        if ics is None:
            weights = {s: base_weight for s in TRADABLE_SLEEVES}
        else:
            composite = _composite_at(composite_series, anchor_date) or 0.0
            raw = {s: max(0.0, base_weight * (1.0 + ics.get(s, 0.0) * composite)) for s in TRADABLE_SLEEVES}
            total = sum(raw.values())
            weights = {s: (w / total) if total > 1e-9 else base_weight for s, w in raw.items()}
        if previous_weights is not None:
            turnovers.append(sum(abs(weights[s] - previous_weights[s]) for s in TRADABLE_SLEEVES))
        previous_weights = weights
        start_date, end_date = dates[i], dates[i + STRIDE_DAYS]
        period_returns.append(sum(weights[s] * (closes[s][end_date] / closes[s][start_date] - 1.0) for s in TRADABLE_SLEEVES))

    cumulative = [1.0]
    for r in period_returns:
        cumulative.append(cumulative[-1] * (1.0 + r))
    peak, max_dd = cumulative[0], 0.0
    for v in cumulative:
        peak = max(peak, v)
        max_dd = min(max_dd, (v - peak) / peak)
    mean_r, stdev_r = statistics.fmean(period_returns), statistics.pstdev(period_returns)
    sharpe = (mean_r / stdev_r) * (PERIODS_PER_YEAR ** 0.5) if stdev_r > 1e-9 else float("nan")
    return {"sharpe": sharpe, "max_drawdown": max_dd, "total_turnover": sum(turnovers)}


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    all_symbols = [BENCHMARK] + TRADABLE_SLEEVES + REFERENCE_ONLY
    closes = {}
    for symbol in all_symbols:
        try:
            closes[symbol] = _closes(connection, dataset_id, symbol)
        except Exception:
            closes[symbol] = {}
    common_dates = sorted(set.intersection(*(set(closes[s]) for s in [BENCHMARK] + TRADABLE_SLEEVES)))
    composite_series = _macro_composite_series(connection, dataset_id)
    print(f"Dataset: {dataset_id}")
    print(f"{len(TRADABLE_SLEEVES)} tradable sleeves + {len(REFERENCE_ONLY)} reference-only\n")

    in_sample_dates = [d for d in common_dates if d < SPLIT_DATE]
    ics = {}
    for s in TRADABLE_SLEEVES:
        r, n = _real_ic(in_sample_dates, closes, composite_series, s)
        ics[s] = r if r is not None else 0.0
        print(f"  {s:5s} IC={r:+.3f}" if r is not None else f"  {s:5s} IC=n/a (insufficient data)")

    print("\nReference-only (never a position candidate, info only):")
    for s in REFERENCE_ONLY:
        if s not in closes or not closes[s]:
            print(f"  {s:8s}: no real data in this dataset")
            continue
        btc_dates = sorted(set(in_sample_dates) & set(closes[s]))
        if len(btc_dates) < IC_WINDOW + STRIDE_DAYS:
            print(f"  {s:8s}: insufficient real overlapping history for a meaningful IC")
            continue
        r, n = _real_ic(btc_dates, closes, composite_series, s)
        print(f"  {s:8s} IC={r:+.3f} (n={n})" if r is not None else f"  {s:8s}: insufficient data")

    mean_abs_ic = statistics.fmean(abs(v) for v in ics.values())
    period_returns_by_sleeve = {s: [] for s in TRADABLE_SLEEVES}
    for i in range(0, len(common_dates) - STRIDE_DAYS, STRIDE_DAYS):
        start_date, end_date = common_dates[i], common_dates[i + STRIDE_DAYS]
        for s in TRADABLE_SLEEVES:
            period_returns_by_sleeve[s].append(closes[s][end_date] / closes[s][start_date] - 1.0)
    correlations = pairwise_correlation_matrix(period_returns_by_sleeve)
    breadth = effective_number_of_bets(TRADABLE_SLEEVES, correlations)
    print(f"\nMean |IC| across {len(TRADABLE_SLEEVES)} tradable sleeves: {mean_abs_ic:.3f}")
    print(f"Real effective breadth: {breadth:.2f} (vs. naive count {len(TRADABLE_SLEEVES)})")
    if breadth:
        print(f"Grinold prediction: IR ~= {mean_abs_ic:.3f} x sqrt({breadth:.2f}) = {mean_abs_ic * breadth ** 0.5:.3f}\n")

    for label, dates in [
        ("FULL SAMPLE", common_dates),
        ("IN-SAMPLE (2004-2018)", in_sample_dates),
        ("OUT-OF-SAMPLE (2019-2026)", [d for d in common_dates if d >= SPLIT_DATE]),
    ]:
        static = _run_backtest(dates, closes, composite_series, None)
        weighted = _run_backtest(dates, closes, composite_series, ics)
        print(f"{label:26s} static Sharpe={static['sharpe']:.3f}  breadth-weighted Sharpe={weighted['sharpe']:.3f}  "
              f"diff={weighted['sharpe']-static['sharpe']:+.3f}  static DD={static['max_drawdown']:.1%}  "
              f"weighted DD={weighted['max_drawdown']:.1%}")


if __name__ == "__main__":
    main()
