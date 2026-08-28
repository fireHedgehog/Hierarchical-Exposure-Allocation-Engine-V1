"""Disposable Phase A v1.1 screen for H-MACRO-S4-002.

Read-only against the sealed application dataset. It does not fetch, write to
SQLite, or change production code. Delete freely when the research design
changes.

Run:
  .venv/Scripts/python.exe -m backend.research_lab.macro_s4_long_biased_policy
"""

from __future__ import annotations

import bisect
import itertools
import math
import statistics
from dataclasses import dataclass

from backend.database import connect, resolve_database_path
from backend.engine.regime.scoring_v3 import CLUSTERS, _yoy_series
from backend.research_lab.macro_v2_exact_runtime_audit import (
    _latest_usable_dataset,
    _load_macro_series,
)


STRIDE = 21
CORE_KEYS = [
    member[0]
    for members in CLUSTERS.values()
    for member in members
    if member[0] not in {"credit_hy", "credit_ig"}
]
ASSETS = [
    "SPY", "QQQ", "DIA", "XLB", "XLE", "XLF", "XLI",
    "XLK", "XLP", "XLU", "XLV", "XLY",
]
OUTER_FOLDS = [
    ("2015-01-01", "2019-01-01"),
    ("2019-01-01", "2023-01-01"),
    ("2023-01-01", "9999-12-31"),
]
ACTION_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
COST_BPS = 5.0
PREFERENCE_PROFILES = {
    "return-seeking": (0.25, 0.10, 0.0),
    "balanced": (0.75, 0.25, 0.001),
    "capital-preservation": (1.50, 0.50, 0.0025),
}


@dataclass(frozen=True)
class Variant:
    family: str
    window_multiplier: float
    clip: float
    smoothing: int

    @property
    def label(self) -> str:
        return (
            f"{self.family};w={self.window_multiplier:g};"
            f"clip={self.clip:g};smooth={self.smoothing}"
        )


@dataclass(frozen=True)
class Spec:
    variant: Variant | None
    mapping: tuple[float, float, float]

    @property
    def label(self) -> str:
        if self.variant is None:
            return "static-1x"
        return f"{self.variant.label};map={self.mapping}"


@dataclass
class Period:
    start: str
    end: str
    returns: dict[str, list[float]]


@dataclass
class Metrics:
    annualized_return: float
    max_drawdown: float
    downside_volatility: float
    annual_turnover: float
    annual_cost: float
    utility: float
    days: int


@dataclass
class FoldResult:
    start: str
    end: str
    spec: Spec
    thresholds: tuple[float, float] | None
    inner_mean: float
    inner_se: float
    policy: Metrics
    baseline: Metrics
    matched: Metrics
    mean_exposure: float
    allocation_delta: float
    timing_delta: float


def _load_assets(connection, dataset_id: str) -> dict[str, list[tuple[str, float]]]:
    result = {}
    for symbol in ASSETS:
        rows = connection.execute(
            """
            SELECT bar.time, bar.close
            FROM symbol_bars AS bar
            JOIN securities AS security ON security.security_id = bar.security_id
            WHERE bar.dataset_snapshot_id = ?
              AND security.primary_symbol = ?
              AND bar.close IS NOT NULL
            ORDER BY bar.time
            """,
            (dataset_id, symbol),
        ).fetchall()
        result[symbol] = [(row["time"], row["close"]) for row in rows]
    return result


def _factor_points(macro_series) -> dict[str, tuple[list[str], list[float], int, float]]:
    result = {}
    for members in CLUSTERS.values():
        for key, _name, series_id, sign, is_yoy, window in members:
            if key not in CORE_KEYS:
                continue
            observations = macro_series[series_id]
            points = (
                _yoy_series(observations)
                if is_yoy
                else [(item.observation_date, item.value) for item in observations]
            )
            result[key] = (
                [item[0] for item in points],
                [item[1] for item in points],
                window,
                sign,
            )
    return result


def _contribution_at(points, anchor: str, window_multiplier: float, clip: float) -> float | None:
    dates, values, base_window, sign = points
    end = bisect.bisect_right(dates, anchor)
    window = max(2, round(base_window * window_multiplier))
    if end < window + 1:
        return None
    latest = values[end - 1]
    trailing = values[end - window - 1 : end - 1]
    mean = statistics.fmean(trailing)
    stdev = statistics.pstdev(trailing)
    z = 0.0 if stdev < 1e-12 else (latest - mean) / stdev
    return max(-1.0, min(1.0, sign * z / clip))


def _family_score(family: str, values: dict[str, float]) -> float:
    if family == "exact-3-cluster":
        blocks = [
            ["growth", "employment", "gdp", "inflation", "pce", "ppi"],
            ["rates_10y", "rates_30y", "real_yield_10y"],
            ["liquidity", "volatility"],
        ]
    elif family == "four-block":
        blocks = [
            ["growth", "employment", "gdp"],
            ["inflation", "pce", "ppi"],
            ["rates_10y", "rates_30y", "real_yield_10y"],
            ["liquidity", "volatility"],
        ]
    elif family == "vix-only":
        return values["volatility"]
    else:
        raise ValueError(family)
    return statistics.fmean(statistics.fmean(values[key] for key in block) for block in blocks)


def _score_variants(anchor_dates: list[str], points) -> dict[Variant, dict[str, float]]:
    raw = {}
    variants = [
        Variant(family, window_multiplier, clip, smoothing)
        for family in ("exact-3-cluster", "four-block", "vix-only")
        for window_multiplier in (0.5, 1.0, 2.0)
        for clip in (2.0, 2.5, 3.0)
        for smoothing in (1, 3)
    ]
    for variant in variants:
        unsmoothed = []
        for anchor in anchor_dates:
            contributions = {
                key: _contribution_at(value, anchor, variant.window_multiplier, variant.clip)
                for key, value in points.items()
            }
            if any(value is None for value in contributions.values()):
                unsmoothed.append(None)
            else:
                unsmoothed.append(_family_score(variant.family, contributions))
        scores = {}
        for index, value in enumerate(unsmoothed):
            history = unsmoothed[max(0, index - variant.smoothing + 1) : index + 1]
            if value is not None and len(history) == variant.smoothing and all(item is not None for item in history):
                scores[anchor_dates[index]] = statistics.fmean(history)
        raw[variant] = scores
    return raw


def _periods(asset_rows: dict[str, list[tuple[str, float]]]) -> list[Period]:
    spy = asset_rows["SPY"]
    dates = [item[0] for item in spy]
    by_asset = {symbol: dict(rows) for symbol, rows in asset_rows.items()}
    result = []
    for start_index in range(0, len(dates) - STRIDE, STRIDE):
        segment_dates = dates[start_index : start_index + STRIDE + 1]
        returns = {}
        for symbol in ASSETS:
            prices = [by_asset[symbol].get(day) for day in segment_dates]
            if any(price is None for price in prices):
                break
            returns[symbol] = [
                prices[index] / prices[index - 1] - 1.0
                for index in range(1, len(prices))
            ]
        if len(returns) == len(ASSETS):
            result.append(Period(segment_dates[0], segment_dates[-1], returns))
    return result


def _terciles(values: list[float]) -> tuple[float, float]:
    low, high = statistics.quantiles(values, n=3, method="inclusive")
    return low, high


def _exposure(score: float, thresholds: tuple[float, float], mapping) -> float:
    if score <= thresholds[0]:
        return mapping[0]
    if score >= thresholds[1]:
        return mapping[2]
    return mapping[1]


def _metrics(
    periods: list[Period],
    asset: str,
    exposures: list[float],
    profile: tuple[float, float, float],
    cost_bps: float,
) -> Metrics:
    daily_returns = []
    total_turnover = 0.0
    total_cost = 0.0
    previous = 1.0
    for period, multiplier in zip(periods, exposures):
        turnover = abs(multiplier - previous)
        cost = turnover * cost_bps / 10_000
        segment = [multiplier * value for value in period.returns[asset]]
        if segment:
            segment[0] -= cost
        daily_returns.extend(segment)
        total_turnover += turnover
        total_cost += cost
        previous = multiplier
    if not daily_returns:
        return Metrics(*(float("nan"),) * 6, 0)
    equity = [1.0]
    for value in daily_returns:
        equity.append(equity[-1] * (1.0 + value))
    years = len(daily_returns) / 252
    annualized_return = equity[-1] ** (1 / years) - 1.0
    peak = equity[0]
    max_drawdown = 0.0
    for value in equity:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, 1.0 - value / peak)
    downside = math.sqrt(statistics.fmean(min(value, 0.0) ** 2 for value in daily_returns) * 252)
    annual_turnover = total_turnover / years
    annual_cost = total_cost / years
    lambda_dd, lambda_down, lambda_turn = profile
    utility = (
        annualized_return
        - lambda_dd * max_drawdown
        - lambda_down * downside
        - lambda_turn * annual_turnover
    )
    return Metrics(
        annualized_return,
        max_drawdown,
        downside,
        annual_turnover,
        annual_cost,
        utility,
        len(daily_returns),
    )


def _evaluate(
    spec: Spec,
    train: list[Period],
    test: list[Period],
    scores,
    profile,
    *,
    asset: str = "SPY",
    cost_bps: float = COST_BPS,
) -> tuple[Metrics, Metrics, Metrics, tuple[float, float] | None, list[float]]:
    if spec.variant is None:
        thresholds = None
        exposures = [1.0] * len(test)
    else:
        train_values = [scores[spec.variant][period.start] for period in train]
        thresholds = _terciles(train_values)
        exposures = [
            _exposure(scores[spec.variant][period.start], thresholds, spec.mapping)
            for period in test
        ]
    policy = _metrics(test, asset, exposures, profile, cost_bps)
    baseline = _metrics(test, asset, [1.0] * len(test), profile, 0.0)
    matched_exposure = statistics.fmean(exposures)
    matched = _metrics(test, asset, [matched_exposure] * len(test), profile, 0.0)
    return policy, baseline, matched, thresholds, exposures


def _inner_blocks(outer_start: str, periods: list[Period]) -> list[tuple[list[Period], list[Period]]]:
    year = int(outer_start[:4])
    blocks = []
    for start_year in (year - 6, year - 4, year - 2):
        start = f"{start_year:04d}-01-01"
        end = f"{start_year + 2:04d}-01-01"
        train = [period for period in periods if period.start < start]
        validation = [period for period in periods if start <= period.start < end]
        if len(train) >= 24 and len(validation) >= 12:
            blocks.append((train, validation))
    return blocks


def _specs(variants: list[Variant]) -> list[Spec]:
    mappings = [
        mapping
        for mapping in itertools.combinations_with_replacement(ACTION_GRID, 3)
        if mapping[2] == 1.0 and mapping != (1.0, 1.0, 1.0)
    ]
    return [Spec(None, (1.0, 1.0, 1.0))] + [
        Spec(variant, mapping) for variant in variants for mapping in mappings
    ]


def _complexity(spec: Spec) -> tuple:
    if spec.variant is None:
        return (0, 0, 0, 0, 0.0)
    family_rank = {"vix-only": 0, "exact-3-cluster": 1, "four-block": 2}[spec.variant.family]
    return (
        len(set(spec.mapping)),
        family_rank,
        0 if spec.variant.window_multiplier == 1 else 1,
        0 if spec.variant.clip == 2.5 else 1,
        abs(spec.mapping[2] - spec.mapping[0]),
    )


def _select_spec(specs, inner_blocks, scores, profile) -> tuple[Spec, float, float]:
    ranked = []
    for spec in specs:
        values = []
        for train, validation in inner_blocks:
            policy, _, matched, _, _ = _evaluate(spec, train, validation, scores, profile)
            values.append(policy.utility - matched.utility)
        mean = statistics.fmean(values)
        se = statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
        ranked.append((mean, se, spec))
    best_mean, best_se, _ = max(ranked, key=lambda item: item[0])
    eligible = [item for item in ranked if item[0] >= best_mean - best_se]
    mean, se, spec = min(eligible, key=lambda item: (_complexity(item[2]), -item[0]))
    return spec, mean, se


def _outer_results(periods, scores, specs, profile) -> list[FoldResult]:
    results = []
    for start, end in OUTER_FOLDS:
        train = [period for period in periods if period.start < start]
        test = [period for period in periods if start <= period.start < end]
        inner = _inner_blocks(start, periods)
        spec, inner_mean, inner_se = _select_spec(specs, inner, scores, profile)
        policy, baseline, matched, thresholds, exposures = _evaluate(spec, train, test, scores, profile)
        results.append(
            FoldResult(
                start, end, spec, thresholds, inner_mean, inner_se,
                policy, baseline, matched, statistics.fmean(exposures),
                policy.utility - baseline.utility,
                policy.utility - matched.utility,
            )
        )
    return results


def _fold_exposures(result: FoldResult, periods, scores) -> tuple[list[Period], list[float]]:
    test = [period for period in periods if result.start <= period.start < result.end]
    if result.spec.variant is None:
        return test, [1.0] * len(test)
    return test, [
        _exposure(scores[result.spec.variant][period.start], result.thresholds, result.spec.mapping)
        for period in test
    ]


def _fmt_pct(value: float) -> str:
    return "n/a" if not math.isfinite(value) else f"{value:+.2%}"


def _print_fold_details(profile_name: str, results: list[FoldResult]) -> None:
    print(f"\n### {profile_name} fold selections")
    print("| Outer test | Selected specification | Inner timing U | Inner SE | OOS timing U | Allocation U vs 1x | Mean exposure | Policy CAGR | 1x CAGR | Policy max DD | 1x max DD |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in results:
        end = "latest" if item.end == "9999-12-31" else item.end[:4]
        print(
            f"| {item.start[:4]}-{end} | {item.spec.label} | {item.inner_mean:+.4f} | "
            f"{item.inner_se:.4f} | {item.timing_delta:+.4f} | {item.allocation_delta:+.4f} | "
            f"{item.mean_exposure:.2f}x | "
            f"{_fmt_pct(item.policy.annualized_return)} | {_fmt_pct(item.baseline.annualized_return)} | "
            f"{item.policy.max_drawdown:.2%} | {item.baseline.max_drawdown:.2%} |"
        )


def _summary_row(profile_name: str, results: list[FoldResult]) -> dict:
    return {
        "profile": profile_name,
        "selected": " / ".join(item.spec.variant.family if item.spec.variant else "static-1x" for item in results),
        "timing": statistics.fmean(item.timing_delta for item in results),
        "allocation": statistics.fmean(item.allocation_delta for item in results),
        "cagr": statistics.fmean(item.policy.annualized_return for item in results),
        "mdd": max(item.policy.max_drawdown for item in results),
        "down": statistics.fmean(item.policy.downside_volatility for item in results),
        "turn": statistics.fmean(item.policy.annual_turnover for item in results),
        "cost": statistics.fmean(item.policy.annual_cost for item in results),
        "worst": min(item.timing_delta for item in results),
        "positive": sum(item.timing_delta > 0 for item in results),
    }


def _print_summary(summaries) -> None:
    print("\n## Candidate summary")
    print("| Utility profile | Selected family by outer fold | Mean OOS timing U | Allocation U vs 1x | Mean CAGR | Worst max DD | Downside vol | Annual turnover | Annual cost | Worst timing fold | Positive timing folds |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in summaries:
        print(
            f"| {row['profile']} | {row['selected']} | {row['timing']:+.4f} | {row['allocation']:+.4f} | {row['cagr']:.2%} | "
            f"{row['mdd']:.2%} | {row['down']:.2%} | {row['turn']:.2f} | {row['cost']:.3%} | "
            f"{row['worst']:+.4f} | {row['positive']}/3 |"
        )


def _print_family_comparison(periods, scores, specs) -> None:
    print("\n## Balanced family comparison")
    print("| Allowed state family | Mean OOS timing U | Allocation U vs 1x | Worst timing fold | Positive timing folds | Selected specification by fold |")
    print("| --- | ---: | ---: | ---: | ---: | --- |")
    static = [spec for spec in specs if spec.variant is None]
    for family in ("exact-3-cluster", "four-block", "vix-only"):
        family_specs = static + [
            spec for spec in specs
            if spec.variant is not None and spec.variant.family == family
        ]
        results = _outer_results(
            periods, scores, family_specs, PREFERENCE_PROFILES["balanced"]
        )
        row = _summary_row(family, results)
        selected = " / ".join(item.spec.label for item in results)
        print(
            f"| {family} | {row['timing']:+.4f} | {row['allocation']:+.4f} | "
            f"{row['worst']:+.4f} | {row['positive']}/3 | {selected} |"
        )


def _print_robustness(balanced, periods, scores) -> None:
    print("\n## Balanced-policy robustness")
    print("| Asset | Mean timing U | Allocation U vs 1x | Max-DD change | Direction agrees | 1 bp agrees | 10 bp agrees | Verdict |")
    print("| --- | ---: | ---: | ---: | --- | --- | --- | --- |")
    spy_delta = statistics.fmean(item.timing_delta for item in balanced)
    for asset in ASSETS:
        deltas = []
        allocation_deltas = []
        mdd_changes = []
        sensitivity = {1.0: [], 10.0: []}
        for item in balanced:
            train = [period for period in periods if period.start < item.start]
            test = [period for period in periods if item.start <= period.start < item.end]
            for cost in (COST_BPS, 1.0, 10.0):
                policy, baseline, matched, _, _ = _evaluate(
                    item.spec, train, test, scores, PREFERENCE_PROFILES["balanced"],
                    asset=asset, cost_bps=cost,
                )
                delta = policy.utility - matched.utility
                if cost == COST_BPS:
                    deltas.append(delta)
                    allocation_deltas.append(policy.utility - baseline.utility)
                    mdd_changes.append(policy.max_drawdown - baseline.max_drawdown)
                else:
                    sensitivity[cost].append(delta)
        mean_delta = statistics.fmean(deltas)
        mean_allocation = statistics.fmean(allocation_deltas)
        mean_mdd = statistics.fmean(mdd_changes)
        agrees = mean_delta * spy_delta > 0 or (mean_delta == 0 and spy_delta == 0)
        low_agrees = statistics.fmean(sensitivity[1.0]) > 0
        high_agrees = statistics.fmean(sensitivity[10.0]) > 0
        verdict = "supports" if mean_delta > 0 and high_agrees else "mixed" if mean_delta > 0 else "fails"
        print(
            f"| {asset} | {mean_delta:+.4f} | {mean_allocation:+.4f} | {mean_mdd:+.2%} | {'Yes' if agrees else 'No'} | "
            f"{'Yes' if low_agrees else 'No'} | {'Yes' if high_agrees else 'No'} | {verdict} |"
        )


def _print_appetite_bands(balanced, periods, scores, spy_rows) -> None:
    spy_dates = [item[0] for item in spy_rows]
    spy_prices = [item[1] for item in spy_rows]
    samples = {"defensive (<0.5x)": [], "cautious (0.5-0.75x)": [], "baseline (1x)": []}
    for result in balanced:
        test, exposures = _fold_exposures(result, periods, scores)
        for period, exposure in zip(test, exposures):
            index = bisect.bisect_left(spy_dates, period.start)
            if index + 126 >= len(spy_prices):
                continue
            future = spy_prices[index + 1 : index + 127]
            adverse = min(value / spy_prices[index] - 1 for value in future) <= -0.10
            segment_return = math.prod(1 + value for value in period.returns["SPY"]) - 1
            policy_return = exposure * segment_return
            band = (
                "defensive (<0.5x)" if exposure < 0.5
                else "cautious (0.5-0.75x)" if exposure < 1.0
                else "baseline (1x)"
            )
            samples[band].append((exposure, adverse, policy_return >= segment_return))
    print("\n## Balanced-policy risk-appetite bands")
    print("| Exposure band | N | Mean exposure | 6M adverse-event rate | 1M policy win rate | Confidence calibration |")
    print("| --- | ---: | ---: | ---: | ---: | --- |")
    for band, rows in samples.items():
        if not rows:
            print(f"| {band} | 0 | n/a | n/a | n/a | not calibrated |")
            continue
        print(
            f"| {band} | {len(rows)} | {statistics.fmean(row[0] for row in rows):.2f}x | "
            f"{statistics.fmean(row[1] for row in rows):.1%} | "
            f"{statistics.fmean(row[2] for row in rows):.1%} | not calibrated |"
        )


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_id = _latest_usable_dataset(connection)
    macro_series = _load_macro_series(connection, dataset_id)
    assets = _load_assets(connection, dataset_id)
    periods = _periods(assets)
    anchor_dates = [period.start for period in periods]
    scores = _score_variants(anchor_dates, _factor_points(macro_series))
    variants = list(scores)
    common_dates = set.intersection(*(set(values) for values in scores.values()))
    periods = [period for period in periods if period.start in common_dates]
    specs = _specs(variants)

    print("# H-MACRO-S4-002 - Phase A v1.1 engineering screen")
    print(f"Dataset: {dataset_id} (sealed; read-only)")
    print(f"Common policy periods: {len(periods)}, {periods[0].start} to {periods[-1].end}")
    print(f"State variants: {len(variants)}; policy specifications including static 1x: {len(specs)}")
    print("Primary panel: 0x-1x, zero cash return, no leverage, 5 bps one-way turnover cost.")
    print("LIMITATION: current-vintage macro history aligned by observation date, not release-time PIT.\n")

    all_results = {}
    summaries = []
    for profile_name, profile in PREFERENCE_PROFILES.items():
        results = _outer_results(periods, scores, specs, profile)
        all_results[profile_name] = results
        _print_fold_details(profile_name, results)
        summaries.append(_summary_row(profile_name, results))
    _print_summary(summaries)
    _print_family_comparison(periods, scores, specs)
    _print_robustness(all_results["balanced"], periods, scores)
    _print_appetite_bands(all_results["balanced"], periods, scores, assets["SPY"])


if __name__ == "__main__":
    main()
