from __future__ import annotations

import bisect
from dataclasses import dataclass

from backend.engine.factors.types import Bar
from backend.engine.regime.types import SeriesObservation
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

# Milestone 4, step 1 (docs/engine-milestones.md): does a macro factor's real
# change actually correlate with a real staging symbol's forward return, or
# is the macro composite treating every sleeve the same by assumption? This
# module answers that per (factor, symbol) pair from real fetched data --
# real FRED observations, real Yahoo closes -- never a fabricated cell.
#
# Not registered in the strategies table as a strategy: this is validation
# research feeding INTO macro_regime_composite/risk_envelope_allocation, not
# a decision-making function itself.

# Forward horizon matches this project's existing "1m" cross-sectional
# momentum convention (engine/factors/momentum.py) for consistency, not a
# new, unrelated choice.
FORWARD_HORIZON_TRADING_DAYS = 21

# A real, if modest, minimum. Fewer paired observations than this and a
# correlation is not trustworthy enough to test at all -- reported as
# 'insufficient_data', never computed anyway with a caveat.
MIN_SAMPLES = 24


@dataclass(frozen=True)
class FactorSymbolResult:
    factor_key: str
    symbol: str
    sample_size: int
    correlation: float | None  # Pearson r; None if not computable
    p_value: float | None  # raw two-sided p-value
    adjusted_p_value: float | None  # Benjamini-Hochberg corrected
    significant: bool  # true only after correction, at the run's alpha
    direction: str  # 'positive' | 'negative' | 'inconclusive'
    status: str  # 'ok' | 'insufficient_data'


@dataclass(frozen=True)
class FactorSignificanceRun:
    method: str
    forward_horizon_days: int
    correction_method: str
    alpha: float
    min_samples: int
    factor_count: int
    symbol_count: int
    test_count: int  # pairs actually tested (status == 'ok')
    significant_count: int
    results: list[FactorSymbolResult]


def _paired_samples(
    factor_observations: list[SeriesObservation],
    symbol_bars: list[Bar],
    forward_horizon_days: int,
) -> tuple[list[float], list[float]]:
    """Real paired samples: each factor observation's real period-over-period
    change, paired with that same symbol's real forward return starting at
    the nearest bar at-or-before the observation date. No interpolation, no
    synthetic fill -- an observation with no usable bar pair is dropped.
    """

    ordered_factor = sorted(factor_observations, key=lambda item: item.observation_date)
    ordered_bars = sorted(symbol_bars, key=lambda bar: bar.time)
    bar_dates = [bar.time for bar in ordered_bars]
    bar_closes = [bar.close for bar in ordered_bars]

    factor_changes: list[float] = []
    forward_returns: list[float] = []

    for index in range(1, len(ordered_factor)):
        previous = ordered_factor[index - 1]
        current = ordered_factor[index]
        if previous.value == 0:
            continue
        factor_change = (current.value - previous.value) / abs(previous.value)

        entry_index = bisect.bisect_right(bar_dates, current.observation_date) - 1
        if entry_index < 0:
            continue
        exit_index = entry_index + forward_horizon_days
        if exit_index >= len(ordered_bars):
            continue
        entry_price = bar_closes[entry_index]
        exit_price = bar_closes[exit_index]
        if entry_price == 0:
            continue

        factor_changes.append(factor_change)
        forward_returns.append((exit_price - entry_price) / entry_price)

    return factor_changes, forward_returns


def compute_factor_symbol_significance(
    factor_observations: dict[str, list[SeriesObservation]],
    symbol_bars: dict[str, list[Bar]],
    *,
    forward_horizon_days: int = FORWARD_HORIZON_TRADING_DAYS,
    min_samples: int = MIN_SAMPLES,
    alpha: float = 0.05,
) -> FactorSignificanceRun:
    """For every (macro factor, staging symbol) pair, test whether the
    factor's real change is significantly correlated with that symbol's real
    forward return. Raw p-values across every computable pair are corrected
    for the resulting multiple-comparisons problem (Benjamini-Hochberg)
    before any single pair is called significant -- testing 8 factors x 21
    symbols is 168 hypothesis tests, and a naive per-test cutoff would
    produce false positives by chance alone.
    """

    raw: list[dict[str, object]] = []
    for factor_key in sorted(factor_observations):
        observations = factor_observations[factor_key]
        for symbol in sorted(symbol_bars):
            bars = symbol_bars[symbol]
            x, y = _paired_samples(observations, bars, forward_horizon_days)
            if len(x) < min_samples:
                raw.append(
                    {"factor_key": factor_key, "symbol": symbol, "sample_size": len(x), "status": "insufficient_data"}
                )
                continue
            correlation, p_value = pearson_significance(x, y)
            raw.append(
                {
                    "factor_key": factor_key,
                    "symbol": symbol,
                    "sample_size": len(x),
                    "correlation": correlation,
                    "p_value": p_value,
                    "status": "ok",
                }
            )

    testable = [item for item in raw if item["status"] == "ok"]
    p_values = [item["p_value"] for item in testable]  # type: ignore[misc]
    adjusted_p_values, significant_flags = benjamini_hochberg(p_values, alpha=alpha)
    for item, adjusted_p_value, is_significant in zip(testable, adjusted_p_values, significant_flags):
        item["adjusted_p_value"] = adjusted_p_value
        item["significant"] = is_significant

    results: list[FactorSymbolResult] = []
    for item in raw:
        if item["status"] == "insufficient_data":
            results.append(
                FactorSymbolResult(
                    factor_key=item["factor_key"],  # type: ignore[arg-type]
                    symbol=item["symbol"],  # type: ignore[arg-type]
                    sample_size=item["sample_size"],  # type: ignore[arg-type]
                    correlation=None,
                    p_value=None,
                    adjusted_p_value=None,
                    significant=False,
                    direction="inconclusive",
                    status="insufficient_data",
                )
            )
            continue
        is_significant = bool(item["significant"])
        correlation = float(item["correlation"])  # type: ignore[arg-type]
        # Direction is only reported for a statistically significant pair --
        # asserting "positive" or "negative" from noise would be a fabricated
        # claim of certainty this project's own rules explicitly forbid.
        direction = ("positive" if correlation > 0 else "negative") if is_significant else "inconclusive"
        results.append(
            FactorSymbolResult(
                factor_key=item["factor_key"],  # type: ignore[arg-type]
                symbol=item["symbol"],  # type: ignore[arg-type]
                sample_size=item["sample_size"],  # type: ignore[arg-type]
                correlation=correlation,
                p_value=float(item["p_value"]),  # type: ignore[arg-type]
                adjusted_p_value=float(item["adjusted_p_value"]),  # type: ignore[arg-type]
                significant=is_significant,
                direction=direction,
                status="ok",
            )
        )

    return FactorSignificanceRun(
        method="pearson_forward_return",
        forward_horizon_days=forward_horizon_days,
        correction_method="benjamini_hochberg",
        alpha=alpha,
        min_samples=min_samples,
        factor_count=len(factor_observations),
        symbol_count=len(symbol_bars),
        test_count=len(testable),
        significant_count=sum(1 for result in results if result.significant),
        results=results,
    )
