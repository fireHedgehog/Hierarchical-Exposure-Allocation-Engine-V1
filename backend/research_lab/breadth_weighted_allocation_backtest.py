"""Scratch script for
docs/hypotheses/asset-selection-research/regime-tilted-allocation-backtest.md
(H-SECT04), Fundamental-Law-of-Active-Management addendum.

Direct test of a real, different question than H-SECT04's original:
not "does a binary tilt on a few individually-significant sleeves beat
equal-weight" (already rejected), but "does combining ALL 12 sleeves'
real, IC-weighted signals -- most individually weak, none individually
significant -- via real breadth (Grinold's IR ~= IC x sqrt(BR)) produce
a real portfolio-level edge." Reuses this project's own real,
PCA-based effective-number-of-bets machinery (proven on H-MACRO08).
Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.breadth_weighted_allocation_backtest
"""

from __future__ import annotations

import statistics

from backend.database import connect, resolve_database_path
from backend.engine.research.signal_validation import effective_number_of_bets, pairwise_correlation_matrix
from backend.research_lab.regime_conditioned_sleeve_return import BENCHMARK, FORWARD_WINDOWS, SLEEVES, STRIDE_DAYS, _closes, _macro_composite_series
from backend.research_lab.regime_conditioned_sleeve_return_oos import SPLIT_DATE

IC_WINDOW = 126  # matches H-SECT02's own 126d window, the one with more real signal
PERIODS_PER_YEAR = 252 / STRIDE_DAYS


def _composite_at(composite_series: list[tuple[str, float]], date: str) -> float | None:
    candidates = [(d, s) for d, s in composite_series if d <= date]
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def _real_per_sleeve_ic(dates: list[str], closes: dict[str, dict[str, float]], composite_series: list[tuple[str, float]]) -> dict[str, float]:
    """Same real IC(composite, forward relative return) H-SECT02 computed,
    freshly recomputed here for all 12 sleeves -- including the ones that
    never cleared significance, which the Fundamental Law says still carry
    real, usable information if combined with enough breadth."""
    from backend.engine.research.significance import pearson_significance

    ics: dict[str, float] = {}
    for sleeve in SLEEVES:
        composite_scores: list[float] = []
        relative_returns: list[float] = []
        for i in range(0, len(dates) - IC_WINDOW, STRIDE_DAYS):
            anchor_date = dates[i]
            composite = _composite_at(composite_series, anchor_date)
            if composite is None:
                continue
            start_date, end_date = dates[i], dates[i + IC_WINDOW]
            sleeve_return = closes[sleeve][end_date] / closes[sleeve][start_date] - 1.0
            benchmark_return = closes[BENCHMARK][end_date] / closes[BENCHMARK][start_date] - 1.0
            composite_scores.append(composite)
            relative_returns.append(sleeve_return - benchmark_return)
        if len(composite_scores) >= 3:
            r, _ = pearson_significance(composite_scores, relative_returns)
            ics[sleeve] = r
    return ics


def _real_effective_breadth(dates: list[str], closes: dict[str, dict[str, float]]) -> float | None:
    """Real effective number of independent bets among the 12 sleeves,
    using their own real period returns -- reuses this project's proven
    PCA-based machinery (H-MACRO08), not a naive count of 12."""
    period_returns: dict[str, list[float]] = {sleeve: [] for sleeve in SLEEVES}
    for i in range(0, len(dates) - STRIDE_DAYS, STRIDE_DAYS):
        start_date, end_date = dates[i], dates[i + STRIDE_DAYS]
        for sleeve in SLEEVES:
            period_returns[sleeve].append(closes[sleeve][end_date] / closes[sleeve][start_date] - 1.0)
    correlations = pairwise_correlation_matrix(period_returns)
    return effective_number_of_bets(SLEEVES, correlations)


def _run_backtest(dates: list[str], closes: dict[str, dict[str, float]], composite_series: list[tuple[str, float]], ics: dict[str, float] | None) -> dict:
    base_weight = 1.0 / len(SLEEVES)
    period_returns: list[float] = []
    turnovers: list[float] = []
    previous_weights: dict[str, float] | None = None

    for i in range(0, len(dates) - STRIDE_DAYS, STRIDE_DAYS):
        anchor_date = dates[i]
        if ics is None:
            weights = {s: base_weight for s in SLEEVES}
        else:
            composite = _composite_at(composite_series, anchor_date) or 0.0
            raw_weights = {s: max(0.0, base_weight * (1.0 + ics.get(s, 0.0) * composite)) for s in SLEEVES}
            total = sum(raw_weights.values())
            weights = {s: (w / total) if total > 1e-9 else base_weight for s, w in raw_weights.items()}

        if previous_weights is not None:
            turnovers.append(sum(abs(weights[s] - previous_weights[s]) for s in SLEEVES))
        previous_weights = weights

        start_date, end_date = dates[i], dates[i + STRIDE_DAYS]
        period_return = sum(weights[s] * (closes[s][end_date] / closes[s][start_date] - 1.0) for s in SLEEVES)
        period_returns.append(period_return)

    cumulative = [1.0]
    for r in period_returns:
        cumulative.append(cumulative[-1] * (1.0 + r))
    peak = cumulative[0]
    max_drawdown = 0.0
    for value in cumulative:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, (value - peak) / peak)

    mean_return = statistics.fmean(period_returns)
    stdev_return = statistics.pstdev(period_returns)
    sharpe = (mean_return / stdev_return) * (PERIODS_PER_YEAR ** 0.5) if stdev_return > 1e-9 else float("nan")

    return {
        "periods": len(period_returns), "sharpe": sharpe, "max_drawdown": max_drawdown,
        "total_turnover": sum(turnovers), "cumulative_return": cumulative[-1] - 1.0,
    }


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    all_symbols = [BENCHMARK] + SLEEVES
    closes = {symbol: _closes(connection, dataset_id, symbol) for symbol in all_symbols}
    common_dates = sorted(set.intersection(*(set(c) for c in closes.values())))
    composite_series = _macro_composite_series(connection, dataset_id)
    print(f"Dataset: {dataset_id}\n")

    # Real walk-forward discipline: IC weights learned ONLY from the
    # in-sample half (2004-2018), then held fixed and applied unchanged to
    # both halves -- computing them on the full sample (including the
    # "out-of-sample" window) would silently leak future information into
    # the score, the same mistake the OOS-split convention exists to catch.
    in_sample_dates = [d for d in common_dates if d < SPLIT_DATE]
    ics = _real_per_sleeve_ic(in_sample_dates, closes, composite_series)
    print("=== Real per-sleeve IC (126d, composite vs. forward relative return), IN-SAMPLE ONLY -- ALL 12, not just significant ones ===")
    for sleeve, ic in sorted(ics.items(), key=lambda kv: -abs(kv[1])):
        print(f"  {sleeve:5s}: IC={ic:+.3f}")
    mean_abs_ic = statistics.fmean(abs(v) for v in ics.values())
    print(f"Mean |IC| across all 12 sleeves: {mean_abs_ic:.3f}\n")

    breadth = _real_effective_breadth(common_dates, closes)
    print(f"Real effective breadth (PCA-based, H-MACRO08's own method): {breadth:.2f} "
          f"(vs. a naive count of {len(SLEEVES)})\n")

    if breadth:
        ir_predicted = mean_abs_ic * (breadth ** 0.5)
        print(f"Grinold prediction: IR ~= IC x sqrt(BR) = {mean_abs_ic:.3f} x sqrt({breadth:.2f}) = {ir_predicted:.3f}\n")

    for label, dates in [
        ("FULL SAMPLE (2004-2026)", common_dates),
        ("IN-SAMPLE (2004-2018)", [d for d in common_dates if d < SPLIT_DATE]),
        ("OUT-OF-SAMPLE (2019-2026)", [d for d in common_dates if d >= SPLIT_DATE]),
    ]:
        print(f"=== {label} ===")
        static = _run_backtest(dates, closes, composite_series, None)
        breadth_weighted = _run_backtest(dates, closes, composite_series, ics)
        print(f"Static equal-weight   : Sharpe={static['sharpe']:.3f}, max DD={static['max_drawdown']:.2%}, "
              f"turnover={static['total_turnover']:.2f}, cumulative={static['cumulative_return']:+.1%}")
        print(f"Breadth-weighted (all 12, IC-weighted): Sharpe={breadth_weighted['sharpe']:.3f}, "
              f"max DD={breadth_weighted['max_drawdown']:.2%}, turnover={breadth_weighted['total_turnover']:.2f}, "
              f"cumulative={breadth_weighted['cumulative_return']:+.1%}")
        print(f"Realized IR (Sharpe) difference: {breadth_weighted['sharpe'] - static['sharpe']:+.3f}\n")


if __name__ == "__main__":
    main()
