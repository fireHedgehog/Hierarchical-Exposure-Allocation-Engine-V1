"""Staging V2 Macro S2/S6 exact-runtime audit.

One read-only loop produces both the outcome matrix (S2) and transformed-
contribution redundancy matrix (S6). It never fetches, writes to SQLite, or
changes the running strategy.

Important limitation: the current FRED dataset is a current-vintage history and
does not contain each historical release timestamp. Historical anchors therefore
use observation dates, not true publication-time availability. Results are
diagnostic and cannot promote an S3 probability calibration by themselves.

Run: .venv/Scripts/python.exe -m backend.research_lab.macro_v2_exact_runtime_audit
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from datetime import date

from backend.database import connect, resolve_database_path
from backend.engine.regime.scoring_v3 import (
    CALM_TERCILE_CUTOFF,
    CLUSTERS,
    STRESSED_TERCILE_CUTOFF,
    compute_regime_v3,
)
from backend.engine.regime.types import InsufficientSeriesDataError, SeriesObservation
from backend.engine.research.significance import benjamini_hochberg
from backend.engine.research.signal_validation import (
    effective_number_of_bets,
    pairwise_correlation_matrix,
    rank_information_coefficient,
    redundancy_pairs,
)

STRIDE_DAYS = 21
SPLIT_DATE = "2022-01-01"
FORWARD_WINDOWS = {"3M": 63, "6M": 126, "12M": 252}
PERMUTATION_REPS = 2000
RANDOM_SEED = 20260828
ADVERSE_MOVE_THRESHOLD = -0.10


@dataclass(frozen=True)
class AnchorState:
    anchor: str
    spy_index: int
    composite: float
    contributions: dict[str, float]


@dataclass
class OutcomeRow:
    target: str
    horizon: str
    expected_sign: int
    dev_n: int
    test_n: int
    dev_ic: float
    test_ic: float
    effect: float
    p_value: float
    q_value: float = 1.0
    ic_rank: int = 0
    q_rank: int = 0
    sign_stable: bool = False
    verdict: str = "inconclusive"


def _series_ids() -> list[str]:
    return [member[2] for members in CLUSTERS.values() for member in members]


def _factor_keys() -> list[str]:
    return [member[0] for members in CLUSTERS.values() for member in members]


def _latest_usable_dataset(connection) -> str:
    series_ids = _series_ids()
    placeholders = ",".join("?" for _ in series_ids)
    row = connection.execute(
        f"""
        SELECT dataset.id
        FROM dataset_snapshots AS dataset
        WHERE dataset.immutable = 1
          AND (
              SELECT COUNT(DISTINCT observation.series_id)
              FROM fred_observations AS observation
              WHERE observation.dataset_snapshot_id = dataset.id
                AND observation.series_id IN ({placeholders})
          ) = ?
          AND EXISTS (
              SELECT 1
              FROM symbol_bars AS bar
              JOIN securities AS security ON security.security_id = bar.security_id
              WHERE bar.dataset_snapshot_id = dataset.id
                AND security.primary_symbol = 'SPY'
          )
        ORDER BY dataset.as_of DESC, dataset.rowid DESC
        LIMIT 1
        """,
        (*series_ids, len(series_ids)),
    ).fetchone()
    if row is None:
        raise RuntimeError("No sealed dataset contains SPY and all 13 runtime macro inputs.")
    return row["id"]


def _load_macro_series(connection, dataset_id: str) -> dict[str, list[SeriesObservation]]:
    result: dict[str, list[SeriesObservation]] = {}
    for series_id in _series_ids():
        rows = connection.execute(
            """
            SELECT observation_date, value, observed_at, available_at
            FROM fred_observations
            WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL
            ORDER BY observation_date
            """,
            (dataset_id, series_id),
        ).fetchall()
        result[series_id] = [
            SeriesObservation(
                observation_date=row["observation_date"],
                value=row["value"],
                observed_at=row["observed_at"],
                available_at=row["available_at"],
            )
            for row in rows
        ]
    return result


def _load_spy(connection, dataset_id: str) -> list[tuple[str, float]]:
    rows = connection.execute(
        """
        SELECT bar.time, bar.close
        FROM symbol_bars AS bar
        JOIN securities AS security ON security.security_id = bar.security_id
        WHERE bar.dataset_snapshot_id = ?
          AND security.primary_symbol = 'SPY'
          AND bar.close IS NOT NULL
        ORDER BY bar.time
        """,
        (dataset_id,),
    ).fetchall()
    return [(row["time"], row["close"]) for row in rows]


def _state_at_index(
    macro_series: dict[str, list[SeriesObservation]], spy: list[tuple[str, float]], spy_index: int
) -> AnchorState | None:
    anchor = spy[spy_index][0]
    truncated = {
        series_id: [item for item in observations if item.observation_date <= anchor]
        for series_id, observations in macro_series.items()
    }
    try:
        result = compute_regime_v3(truncated, date.fromisoformat(anchor))
    except InsufficientSeriesDataError:
        return None
    contributions = {factor.key: factor.contribution for factor in result.factors}
    composite = sum(contributions[key] * weight for key, weight in result.weights.items())
    return AnchorState(anchor, spy_index, composite, contributions)


def _anchor_states(
    macro_series: dict[str, list[SeriesObservation]], spy: list[tuple[str, float]]
) -> list[AnchorState]:
    return [
        state
        for spy_index in range(0, len(spy), STRIDE_DAYS)
        if (state := _state_at_index(macro_series, spy, spy_index)) is not None
    ]


def _targets(spy: list[tuple[str, float]], state: AnchorState, forward_days: int) -> dict[str, float] | None:
    if state.spy_index + forward_days >= len(spy):
        return None
    start = spy[state.spy_index][1]
    future = [close for _, close in spy[state.spy_index + 1 : state.spy_index + forward_days + 1]]
    if not future or start == 0:
        return None
    path = [start, *future]
    daily_returns = [path[index] / path[index - 1] - 1.0 for index in range(1, len(path))]
    return {
        "Forward return": future[-1] / start - 1.0,
        "Return direction": 1.0 if future[-1] > start else 0.0,
        "Realized volatility": statistics.pstdev(daily_returns) * math.sqrt(252),
        "Maximum adverse excursion": min(close / start - 1.0 for close in future),
    }


def _safe_rank_ic(x: list[float], y: list[float]) -> float:
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return float("nan")
    value, _ = rank_information_coefficient(x, y)
    return value


def _block_permutation_p_value(
    x: list[float], y: list[float], *, block_size: int, seed_offset: int
) -> float:
    observed = _safe_rank_ic(x, y)
    if not math.isfinite(observed):
        return 1.0
    blocks = [y[index : index + block_size] for index in range(0, len(y), block_size)]
    rng = random.Random(RANDOM_SEED + seed_offset)
    extreme = 0
    for _ in range(PERMUTATION_REPS):
        shuffled = blocks[:]
        rng.shuffle(shuffled)
        permuted = [value for block in shuffled for value in block][: len(y)]
        candidate = _safe_rank_ic(x, permuted)
        if math.isfinite(candidate) and abs(candidate) >= abs(observed):
            extreme += 1
    return (extreme + 1) / (PERMUTATION_REPS + 1)


def _zone_effect(x: list[float], y: list[float], target: str) -> float:
    ordered = sorted(zip(x, y), key=lambda pair: pair[0])
    tercile = max(1, len(ordered) // 3)
    adverse = [value for _, value in ordered[:tercile]]
    supportive = [value for _, value in ordered[-tercile:]]
    if target == "Realized volatility":
        return statistics.fmean(adverse) - statistics.fmean(supportive)
    return statistics.fmean(supportive) - statistics.fmean(adverse)


def _outcome_matrix(states: list[AnchorState], spy: list[tuple[str, float]]) -> list[OutcomeRow]:
    expected_sign = {
        "Forward return": 1,
        "Return direction": 1,
        "Realized volatility": -1,
        "Maximum adverse excursion": 1,
    }
    rows: list[OutcomeRow] = []
    for horizon_index, (horizon, forward_days) in enumerate(FORWARD_WINDOWS.items()):
        samples = []
        for state in states:
            values = _targets(spy, state, forward_days)
            if values is not None:
                samples.append((state.anchor, state.composite, values))
        for target_index, target in enumerate(expected_sign):
            dev = [(score, values[target]) for anchor, score, values in samples if anchor < SPLIT_DATE]
            test = [(score, values[target]) for anchor, score, values in samples if anchor >= SPLIT_DATE]
            dev_x, dev_y = [item[0] for item in dev], [item[1] for item in dev]
            test_x, test_y = [item[0] for item in test], [item[1] for item in test]
            block_size = max(1, math.ceil(forward_days / STRIDE_DAYS))
            rows.append(
                OutcomeRow(
                    target=target,
                    horizon=horizon,
                    expected_sign=expected_sign[target],
                    dev_n=len(dev),
                    test_n=len(test),
                    dev_ic=_safe_rank_ic(dev_x, dev_y),
                    test_ic=_safe_rank_ic(test_x, test_y),
                    effect=_zone_effect(test_x, test_y, target),
                    p_value=_block_permutation_p_value(
                        test_x,
                        test_y,
                        block_size=block_size,
                        seed_offset=horizon_index * 10 + target_index,
                    ),
                )
            )

    adjusted, _ = benjamini_hochberg([row.p_value for row in rows])
    for row, q_value in zip(rows, adjusted):
        row.q_value = q_value
        row.sign_stable = (
            math.isfinite(row.dev_ic)
            and math.isfinite(row.test_ic)
            and row.dev_ic * row.test_ic > 0
        )
        if row.test_n < 20:
            row.verdict = "underpowered"
        elif not row.sign_stable:
            row.verdict = "unstable"
        elif row.q_value <= 0.05:
            row.verdict = "supported" if row.test_ic * row.expected_sign > 0 else "rejected"
        else:
            row.verdict = "inconclusive"

    for rank, row in enumerate(sorted(rows, key=lambda item: -abs(item.test_ic)), 1):
        row.ic_rank = rank
    for rank, row in enumerate(sorted(rows, key=lambda item: item.q_value), 1):
        row.q_rank = rank
    return sorted(rows, key=lambda item: item.ic_rank)


def _fmt(value: float, digits: int = 3) -> str:
    return "n/a" if not math.isfinite(value) else f"{value:+.{digits}f}"


def _print_outcomes(rows: list[OutcomeRow]) -> None:
    print("## H-MACRO-S2-001 - Exact Runtime Outcome Matrix")
    print(
        "| Target | Horizon | Dev N | Test N | Dev rank IC | Test rank IC | IC rank | "
        "Zone effect | block p | BH q | q rank | Sign stable | Verdict |"
    )
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |")
    for row in rows:
        effect = f"{row.effect:+.1%}"
        print(
            f"| {row.target} | {row.horizon} | {row.dev_n} | {row.test_n} | {_fmt(row.dev_ic)} | "
            f"{_fmt(row.test_ic)} | {row.ic_rank} | {effect} | {row.p_value:.4f} | "
            f"{row.q_value:.4f} | {row.q_rank} | {'Yes' if row.sign_stable else 'No'} | {row.verdict} |"
        )


def _redundancy_summary(
    states: list[AnchorState], keys: list[str], label: str
) -> tuple[dict[str, object], list[tuple[str, str, float]]]:
    eligible = [state for state in states if all(key in state.contributions for key in keys)]
    series = {key: [state.contributions[key] for state in eligible] for key in keys}
    matrix = pairwise_correlation_matrix(series)
    enb = effective_number_of_bets(sorted(keys), matrix)
    flags = redundancy_pairs(matrix, threshold=0.7)
    max_abs = max((abs(value) for value in matrix.values()), default=float("nan"))

    cluster_strength: dict[str, float] = {}
    for cluster_name, members in CLUSTERS.items():
        member_keys = [member[0] for member in members if member[0] in keys]
        values = []
        for index, key_a in enumerate(member_keys):
            for key_b in member_keys[index + 1 :]:
                value = matrix.get((key_a, key_b), matrix.get((key_b, key_a)))
                if value is not None:
                    values.append(abs(value))
        if values:
            cluster_strength[cluster_name] = statistics.fmean(values)
    dominant = max(cluster_strength, key=cluster_strength.get) if cluster_strength else "n/a"

    dev = [state for state in eligible if state.anchor < SPLIT_DATE]
    test = [state for state in eligible if state.anchor >= SPLIT_DATE]
    split_enb = []
    for subset in (dev, test):
        subset_series = {key: [state.contributions[key] for state in subset] for key in keys}
        subset_matrix = pairwise_correlation_matrix(subset_series)
        split_enb.append(effective_number_of_bets(sorted(keys), subset_matrix))
    ratio = (enb / len(keys)) if enb is not None else 0.0
    verdict = "concentrated" if ratio <= 0.5 else "partly redundant" if ratio <= 0.75 else "diverse"
    summary = {
        "label": label,
        "window": f"{eligible[0].anchor} to {eligible[-1].anchor}" if eligible else "n/a",
        "n": len(eligible),
        "max_abs": max_abs,
        "enb": enb,
        "dominant": dominant,
        "stability": f"dev {split_enb[0]:.2f} / test {split_enb[1]:.2f}"
        if all(value is not None for value in split_enb)
        else "insufficient split",
        "verdict": verdict,
    }
    top_pairs = [(flag.key_a, flag.key_b, flag.correlation) for flag in flags[:5]]
    return summary, top_pairs


def _print_redundancy(states: list[AnchorState]) -> None:
    all_keys = _factor_keys()
    core_keys = [key for key in all_keys if key not in {"credit_hy", "credit_ig"}]
    reports = [
        _redundancy_summary(states, core_keys, "Core 11 transformed contributions"),
        _redundancy_summary(states, all_keys, "All 13 transformed contributions"),
    ]
    print("\n## H-MACRO-S6-001 - Runtime Contribution Redundancy")
    print("| Contribution set | Window | N | Max abs correlation | Effective bets | Dominant cluster | Stability | Verdict |")
    print("| --- | --- | ---: | ---: | ---: | --- | --- | --- |")
    for summary, _ in reports:
        enb = summary["enb"]
        print(
            f"| {summary['label']} | {summary['window']} | {summary['n']} | {summary['max_abs']:.3f} | "
            f"{enb:.2f} | {summary['dominant']} | {summary['stability']} | {summary['verdict']} |"
        )
    print("\nTop transformed-contribution redundancy pairs:")
    for summary, pairs in reports:
        formatted = ", ".join(f"{a}/{b} {value:+.3f}" for a, b, value in pairs) or "none"
        print(f"- {summary['label']}: {formatted}")


def _zone(composite: float) -> str:
    if composite <= STRESSED_TERCILE_CUTOFF:
        return "adverse"
    if composite >= CALM_TERCILE_CUTOFF:
        return "supportive"
    return "mixed"


def _adverse_frequency_rows(
    states: list[AnchorState], spy: list[tuple[str, float]], subset: str
) -> dict[str, tuple[int, int, float]]:
    samples: dict[str, list[bool]] = {"adverse": [], "mixed": [], "supportive": []}
    for state in states:
        if subset == "dev" and state.anchor >= SPLIT_DATE:
            continue
        if subset == "test" and state.anchor < SPLIT_DATE:
            continue
        targets = _targets(spy, state, FORWARD_WINDOWS["6M"])
        if targets is None:
            continue
        samples[_zone(state.composite)].append(
            targets["Maximum adverse excursion"] <= ADVERSE_MOVE_THRESHOLD
        )
    return {
        zone: (len(events), sum(events), sum(events) / len(events) if events else float("nan"))
        for zone, events in samples.items()
    }


def _print_numeric_translation(
    states: list[AnchorState], current: AnchorState, spy: list[tuple[str, float]]
) -> None:
    support_percentile = 100.0 * sum(
        state.composite <= current.composite for state in states
    ) / len(states)
    reports = {
        subset: _adverse_frequency_rows(states, spy, subset)
        for subset in ("dev", "test", "full")
    }
    current_zone = _zone(current.composite)

    print("\n## H-MACRO-S3-CV-001 - Numeric Environment Translation")
    print(
        f"Current exact-runtime state: {current.anchor}, composite {current.composite:+.3f}, "
        f"zone {current_zone}, support percentile {support_percentile:.1f}%."
    )
    print(
        "The percentile is a descriptive 0-100 environment position. The frequency is the "
        "historical share of exact-runtime anchors followed by a 10% six-month adverse excursion; "
        "it is current-vintage research, not a release-time-PIT probability."
    )
    print("| Zone | Dev N | Dev frequency | Test N | Test frequency | Full N | Full frequency |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for zone in ("adverse", "mixed", "supportive"):
        dev_n, _, dev_rate = reports["dev"][zone]
        test_n, _, test_rate = reports["test"][zone]
        full_n, _, full_rate = reports["full"][zone]
        print(
            f"| {zone} | {dev_n} | {dev_rate:.1%} | {test_n} | {test_rate:.1%} | "
            f"{full_n} | {full_rate:.1%} |"
        )
    full_current_rate = reports["full"][current_zone][2]
    test_current_rate = reports["test"][current_zone][2]
    print(
        f"Candidate UI pair: environment position {support_percentile:.1f}/100; "
        f"six-month adverse-frequency reference {full_current_rate:.1%} "
        f"(held-out {test_current_rate:.1%}) for the current {current_zone} zone."
    )
    ordered_scores = sorted(state.composite for state in states)
    checkpoint_percentiles = (0, 5, 10, 20, 25, 33, 40, 50, 55, 60, 67, 75, 80, 90, 95, 100)
    checkpoints = []
    for percentile in checkpoint_percentiles:
        rank = round((len(ordered_scores) - 1) * percentile / 100)
        checkpoints.append((ordered_scores[rank], float(percentile)))
    print("Exact-runtime reference checkpoints:")
    print(", ".join(f"({score:+.4f}, {percentile:.0f})" for score, percentile in checkpoints))


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_id = _latest_usable_dataset(connection)
    macro_series = _load_macro_series(connection, dataset_id)
    spy = _load_spy(connection, dataset_id)
    states = _anchor_states(macro_series, spy)
    current = _state_at_index(macro_series, spy, len(spy) - 1)
    if current is None:
        raise RuntimeError("The latest SPY date has no computable exact-runtime macro state.")
    print(f"Dataset: {dataset_id}")
    print(f"SPY: {len(spy)} bars, {spy[0][0]} to {spy[-1][0]}")
    print(f"Runtime anchors: {len(states)}, stride {STRIDE_DAYS} trading days, split {SPLIT_DATE}")
    print("LIMITATION: current-vintage FRED values aligned by observation date; not true historical release-time PIT.\n")
    _print_outcomes(_outcome_matrix(states, spy))
    _print_redundancy(states)
    _print_numeric_translation(states, current, spy)


if __name__ == "__main__":
    main()
