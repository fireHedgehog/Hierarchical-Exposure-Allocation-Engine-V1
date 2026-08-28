"""Scratch loop for H-TIME-S2-001. Read-only, no fetch, no DB writes.

Run:
  .venv/Scripts/python.exe -m backend.research_lab.timing_dislocation_repair_surface
"""

from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg


SYMBOLS = ("SPY", "QQQ", "DIA", "IWM")
HORIZONS = (5, 10, 20, 63)
PERMUTATION_REPS = 5000
RANDOM_SEED = 20260829
MIN_PANEL_PAIRS = 8


@dataclass(frozen=True)
class Spec:
    family: str
    threshold: float

    @property
    def label(self) -> str:
        if self.family == "abrupt shock":
            return f"z<={-self.threshold:.1f}"
        if self.family == "100DMA break":
            return f"depth>={self.threshold:.1f} vol"
        return f"drawdown>={self.threshold:.0%}"


SPECS = [
    *[Spec("abrupt shock", value) for value in (1.5, 2.0, 2.5)],
    *[Spec("100DMA break", value) for value in (0.0, 0.5, 1.0)],
    *[Spec("drawdown transition", value) for value in (0.05, 0.10, 0.15)],
]


@dataclass(frozen=True)
class Point:
    date: str
    close: float
    prior_vol: float
    annual_vol: float
    sma100: float
    sma200: float
    sma200_slope: float
    high63: float
    drawdown63: float
    one_day_return: float


@dataclass(frozen=True)
class Event:
    symbol: str
    index: int
    date: str
    reference: float
    barrier_fraction: float
    panel: str


@dataclass(frozen=True)
class Pair:
    event: Event
    control_index: int


@dataclass(frozen=True)
class Path:
    repair50: float
    full_repair: float
    terminal_repair: float
    additional_loss: float
    underwater: float


@dataclass
class Result:
    family: str
    threshold: str
    horizon: int
    pairs_dev: int
    pairs_val: int
    pairs_test: int
    unmatched: int
    repair_dev: float
    repair_val: float
    repair_test: float
    repair_event_test: float
    repair_control_test: float
    strict_test: float
    terminal_test: float
    loss_test: float
    underwater_test: float
    breadth_positive: int
    breadth_negative: int
    test_clusters: int
    p_value: float
    q_value: float = 1.0
    verdict: str = "inconclusive"


def _panel(observation_date: str) -> str:
    if observation_date <= "2014-12-31":
        return "dev"
    if observation_date <= "2019-12-31":
        return "val"
    return "test"


def _latest_dataset(connection) -> str:
    marks = ",".join("?" for _ in SYMBOLS)
    row = connection.execute(
        f"""
        SELECT dataset.id
        FROM dataset_snapshots AS dataset
        WHERE dataset.immutable = 1
          AND (SELECT COUNT(DISTINCT security.primary_symbol)
               FROM symbol_bars AS bar
               JOIN securities AS security ON security.security_id = bar.security_id
               WHERE bar.dataset_snapshot_id = dataset.id
                 AND security.primary_symbol IN ({marks})) = ?
        ORDER BY dataset.as_of DESC, dataset.rowid DESC
        LIMIT 1
        """,
        (*SYMBOLS, len(SYMBOLS)),
    ).fetchone()
    if row is None:
        raise RuntimeError("No sealed dataset contains all broad-index timing inputs.")
    return row["id"]


def _load_closes(connection, dataset_id: str) -> dict[str, list[tuple[str, float]]]:
    result = {}
    for symbol in SYMBOLS:
        rows = connection.execute(
            """
            SELECT bar.time, bar.close
            FROM symbol_bars AS bar
            JOIN securities AS security ON security.security_id = bar.security_id
            WHERE bar.dataset_snapshot_id = ? AND security.primary_symbol = ?
              AND bar.close IS NOT NULL
            ORDER BY bar.time
            """,
            (dataset_id, symbol),
        ).fetchall()
        result[symbol] = [(row["time"], float(row["close"])) for row in rows]
    return result


def _stdev(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) >= 2 else float("nan")


def _points(bars: list[tuple[str, float]]) -> list[Point | None]:
    closes = [item[1] for item in bars]
    returns = [float("nan")] + [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    sma200_values: list[float | None] = [None] * len(closes)
    for index in range(199, len(closes)):
        sma200_values[index] = statistics.fmean(closes[index - 199 : index + 1])
    output: list[Point | None] = [None] * len(closes)
    for index in range(219, len(closes)):
        prior_returns = returns[index - 20 : index]
        prior_vol = _stdev(prior_returns)
        sma100 = statistics.fmean(closes[index - 99 : index + 1])
        sma200 = sma200_values[index]
        old_sma200 = sma200_values[index - 20]
        high63 = max(closes[index - 63 : index])
        if (
            not math.isfinite(prior_vol)
            or prior_vol <= 0
            or sma200 is None
            or old_sma200 in (None, 0)
            or high63 <= 0
        ):
            continue
        output[index] = Point(
            date=bars[index][0],
            close=closes[index],
            prior_vol=prior_vol,
            annual_vol=prior_vol * math.sqrt(252),
            sma100=sma100,
            sma200=sma200,
            sma200_slope=sma200 / old_sma200 - 1.0,
            high63=high63,
            drawdown63=closes[index] / high63 - 1.0,
            one_day_return=returns[index],
        )
    return output


def _candidate(point: Point, previous: Point | None, spec: Spec, previous_close: float) -> tuple[bool, float]:
    if spec.family == "abrupt shock":
        triggered = point.one_day_return / point.prior_vol <= -spec.threshold
        return triggered, previous_close
    if spec.family == "100DMA break":
        depth = (point.close / point.sma100 - 1.0) / point.prior_vol
        previous_depth = (
            (previous.close / previous.sma100 - 1.0) / previous.prior_vol
            if previous is not None
            else float("inf")
        )
        triggered = depth <= -spec.threshold and previous_depth > -spec.threshold
        return triggered, point.sma100
    previous_drawdown = previous.drawdown63 if previous is not None else 0.0
    triggered = point.drawdown63 <= -spec.threshold and previous_drawdown > -spec.threshold
    return triggered, point.high63


def _events(
    symbol: str, bars: list[tuple[str, float]], points: list[Point | None], spec: Spec
) -> tuple[list[Event], set[int]]:
    result = []
    raw_candidates: set[int] = set()
    active_index: int | None = None
    active_reference: float | None = None
    for index in range(220, len(bars) - max(HORIZONS)):
        point = points[index]
        previous = points[index - 1]
        if point is None:
            continue
        if active_index is not None and active_reference is not None:
            if point.close >= active_reference or index - active_index >= 63:
                active_index = None
                active_reference = None
        triggered, reference = _candidate(point, previous, spec, bars[index - 1][1])
        if triggered:
            raw_candidates.add(index)
        if not triggered or active_index is not None or reference <= point.close:
            continue
        result.append(
            Event(
                symbol=symbol,
                index=index,
                date=point.date,
                reference=reference,
                barrier_fraction=max(reference - point.close, point.close * point.prior_vol) / point.close,
                panel=_panel(point.date),
            )
        )
        active_index = index
        active_reference = reference
    return result, raw_candidates


def _vol_bucket(value: float) -> int:
    if value < 0.15:
        return 0
    if value < 0.25:
        return 1
    return 2


def _drawdown_bucket(value: float) -> int:
    depth = -value
    if depth < 0.05:
        return 0
    if depth < 0.10:
        return 1
    if depth < 0.15:
        return 2
    return 3


def _match(
    events: list[Event], raw_candidates: set[int], points: list[Point | None], bars: list[tuple[str, float]]
) -> tuple[list[Pair], int]:
    excluded = {
        index
        for event_index in raw_candidates
        for index in range(max(220, event_index - 5), min(len(bars) - 63, event_index + 6))
    }
    buckets: dict[tuple[str, bool, int, int], list[int]] = defaultdict(list)
    for index in range(220, len(bars) - 63):
        point = points[index]
        if point is None or index in excluded:
            continue
        key = (
            _panel(point.date),
            point.close >= point.sma200,
            _vol_bucket(point.annual_vol),
            _drawdown_bucket(point.drawdown63),
        )
        buckets[key].append(index)
    used: set[int] = set()
    pairs = []
    for event in events:
        point = points[event.index]
        if point is None:
            continue
        key = (
            event.panel,
            point.close >= point.sma200,
            _vol_bucket(point.annual_vol),
            _drawdown_bucket(point.drawdown63),
        )
        candidates = [index for index in buckets.get(key, []) if index not in used]
        if not candidates:
            continue
        control_index = min(
            candidates,
            key=lambda index: (
                abs(points[index].annual_vol - point.annual_vol) / 0.10  # type: ignore[union-attr]
                + abs(points[index].drawdown63 - point.drawdown63) / 0.05  # type: ignore[union-attr]
                + abs(points[index].sma200_slope - point.sma200_slope) / 0.02  # type: ignore[union-attr]
            ),
        )
        used.add(control_index)
        pairs.append(Pair(event, control_index))
    return pairs, len(events) - len(pairs)


def _first_pass(path: list[float], upper: float, lower: float) -> float:
    for value in path:
        if value >= upper:
            return 1.0
        if value <= lower:
            return 0.0
    return 0.0


def _path(closes: list[float], index: int, barrier_fraction: float, horizon: int) -> Path:
    start = closes[index]
    damage = start * barrier_fraction
    future = closes[index + 1 : index + horizon + 1]
    reference = start + damage
    return Path(
        repair50=_first_pass(future, start + 0.5 * damage, start - 0.5 * damage),
        full_repair=_first_pass(future, reference, start - damage),
        terminal_repair=(future[-1] - start) / damage,
        additional_loss=(min(future) - start) / damage,
        underwater=sum(value < reference for value in future) / len(future),
    )


def _paired_rows(
    pairs: list[Pair], closes_by_symbol: dict[str, list[float]], horizon: int
) -> list[tuple[Event, Path, Path]]:
    result = []
    for pair in pairs:
        closes = closes_by_symbol[pair.event.symbol]
        event_path = _path(closes, pair.event.index, pair.event.barrier_fraction, horizon)
        control_path = _path(closes, pair.control_index, pair.event.barrier_fraction, horizon)
        result.append((pair.event, event_path, control_path))
    return result


def _mean_delta(rows: list[tuple[Event, Path, Path]], field: str) -> float:
    if not rows:
        return float("nan")
    return statistics.fmean(getattr(event, field) - getattr(control, field) for _, event, control in rows)


def _mean_side(rows: list[tuple[Event, Path, Path]], field: str, side: int) -> float:
    if not rows:
        return float("nan")
    return statistics.fmean(getattr(row[side], field) for row in rows)


def _cluster_p(rows: list[tuple[Event, Path, Path]], seed: int) -> float:
    differences: dict[str, list[float]] = defaultdict(list)
    for event, event_path, control_path in rows:
        differences[event.date].append(event_path.repair50 - control_path.repair50)
    observed_values = [value for values in differences.values() for value in values]
    if len(differences) < MIN_PANEL_PAIRS or not observed_values:
        return 1.0
    observed = abs(statistics.fmean(observed_values))
    rng = random.Random(seed)
    extreme = 0
    clusters = list(differences.values())
    for _ in range(PERMUTATION_REPS):
        permuted = [value * rng.choice((-1.0, 1.0)) for values in clusters for value in values]
        if abs(statistics.fmean(permuted)) >= observed - 1e-12:
            extreme += 1
    return (extreme + 1) / (PERMUTATION_REPS + 1)


def _breadth(rows: list[tuple[Event, Path, Path]]) -> tuple[int, int]:
    positive = 0
    negative = 0
    for symbol in SYMBOLS:
        subset = [row for row in rows if row[0].symbol == symbol]
        delta = _mean_delta(subset, "repair50")
        if math.isfinite(delta) and delta > 0:
            positive += 1
        elif math.isfinite(delta) and delta < 0:
            negative += 1
    return positive, negative


def _run(
    bars_by_symbol: dict[str, list[tuple[str, float]]],
    points_by_symbol: dict[str, list[Point | None]],
) -> tuple[list[Result], dict[tuple[str, str], tuple[int, int, float, float]]]:
    closes = {symbol: [value for _, value in bars] for symbol, bars in bars_by_symbol.items()}
    results = []
    coverage = {}
    for spec_index, spec in enumerate(SPECS):
        all_pairs = []
        matched = unmatched = 0
        vol_gaps = []
        drawdown_gaps = []
        for symbol in SYMBOLS:
            events, raw_candidates = _events(symbol, bars_by_symbol[symbol], points_by_symbol[symbol], spec)
            pairs, missing = _match(events, raw_candidates, points_by_symbol[symbol], bars_by_symbol[symbol])
            all_pairs.extend(pairs)
            for pair in pairs:
                event_point = points_by_symbol[symbol][pair.event.index]
                control_point = points_by_symbol[symbol][pair.control_index]
                if event_point is not None and control_point is not None:
                    vol_gaps.append(abs(event_point.annual_vol - control_point.annual_vol))
                    drawdown_gaps.append(abs(event_point.drawdown63 - control_point.drawdown63))
            matched += len(pairs)
            unmatched += missing
        coverage[(spec.family, spec.label)] = (
            matched,
            unmatched,
            statistics.fmean(vol_gaps) if vol_gaps else float("nan"),
            statistics.fmean(drawdown_gaps) if drawdown_gaps else float("nan"),
        )
        for horizon_index, horizon in enumerate(HORIZONS):
            rows = _paired_rows(all_pairs, closes, horizon)
            dev = [row for row in rows if row[0].panel == "dev"]
            val = [row for row in rows if row[0].panel == "val"]
            test = [row for row in rows if row[0].panel == "test"]
            breadth_positive, breadth_negative = _breadth(test)
            results.append(
                Result(
                    family=spec.family,
                    threshold=spec.label,
                    horizon=horizon,
                    pairs_dev=len(dev),
                    pairs_val=len(val),
                    pairs_test=len(test),
                    unmatched=unmatched,
                    repair_dev=_mean_delta(dev, "repair50"),
                    repair_val=_mean_delta(val, "repair50"),
                    repair_test=_mean_delta(test, "repair50"),
                    repair_event_test=_mean_side(test, "repair50", 1),
                    repair_control_test=_mean_side(test, "repair50", 2),
                    strict_test=_mean_delta(test, "full_repair"),
                    terminal_test=_mean_delta(test, "terminal_repair"),
                    loss_test=_mean_delta(test, "additional_loss"),
                    underwater_test=_mean_delta(test, "underwater"),
                    breadth_positive=breadth_positive,
                    breadth_negative=breadth_negative,
                    test_clusters=len({row[0].date for row in test}),
                    p_value=_cluster_p(test, RANDOM_SEED + spec_index * len(HORIZONS) + horizon_index),
                )
            )
    for family in sorted(set(result.family for result in results)):
        group = [result for result in results if result.family == family]
        adjusted, _ = benjamini_hochberg([result.p_value for result in group], alpha=0.10)
        for result, q_value in zip(group, adjusted):
            result.q_value = q_value
    for result in results:
        enough = min(result.pairs_val, result.pairs_test) >= MIN_PANEL_PAIRS
        if (
            enough
            and result.repair_val > 0
            and result.repair_test > 0
            and result.q_value <= 0.10
            and result.breadth_positive >= 3
        ):
            result.verdict = "stable repair"
        elif (
            enough
            and result.repair_val < 0
            and result.repair_test < 0
            and result.q_value <= 0.10
            and result.breadth_negative >= 3
        ):
            result.verdict = "continuation risk"
        elif not enough:
            result.verdict = "insufficient"
    return results, coverage


def _fmt(value: float) -> str:
    return f"{value:+.1%}" if math.isfinite(value) else "NA"


def _print(dataset_id: str, results: list[Result], coverage: dict[tuple[str, str], tuple[int, int, float, float]]) -> None:
    print(f"Dataset: {dataset_id}")
    print(f"Symbols: {', '.join(SYMBOLS)}; specs: {len(SPECS)}; cells: {len(results)}")
    print(f"Date-cluster sign flips: {PERMUTATION_REPS}; minimum validation/test pairs: {MIN_PANEL_PAIRS}")
    print()
    print("## Event coverage")
    print("| Family | Threshold | Matched | Unmatched | Mean vol gap | Mean drawdown gap |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    for spec in SPECS:
        matched, unmatched, vol_gap, drawdown_gap = coverage[(spec.family, spec.label)]
        print(f"| {spec.family} | {spec.label} | {matched} | {unmatched} | {vol_gap:.1%} | {drawdown_gap:.1%} |")
    print()
    print("## Repair surface")
    print("| Family | Threshold | H | Dev/Val/Test | Test clusters | Repair delta D/V/T | Event/control test | Strict test | Terminal test | Add-loss test | Underwater test | Breadth +/- | q | Verdict |")
    print("| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for result in results:
        print(
            f"| {result.family} | {result.threshold} | {result.horizon} | "
            f"{result.pairs_dev}/{result.pairs_val}/{result.pairs_test} | "
            f"{result.test_clusters} | "
            f"{_fmt(result.repair_dev)} / {_fmt(result.repair_val)} / {_fmt(result.repair_test)} | "
            f"{_fmt(result.repair_event_test)} / {_fmt(result.repair_control_test)} | "
            f"{_fmt(result.strict_test)} | {result.terminal_test:+.2f}D | {result.loss_test:+.2f}D | "
            f"{_fmt(result.underwater_test)} | {result.breadth_positive}/{result.breadth_negative} | "
            f"{result.q_value:.3f} | {result.verdict} |"
        )
    print()
    counts = {name: sum(result.verdict == name for result in results) for name in (
        "stable repair", "continuation risk", "inconclusive", "insufficient"
    )}
    print("Verdicts:", counts)
    print("Positive additional-loss delta means the event suffered less further loss than its matched control.")
    print("Negative underwater delta means the event spent less of the horizon below its frozen reference.")


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_id = _latest_dataset(connection)
    bars = _load_closes(connection, dataset_id)
    points = {symbol: _points(symbol_bars) for symbol, symbol_bars in bars.items()}
    results, coverage = _run(bars, points)
    _print(dataset_id, results, coverage)


if __name__ == "__main__":
    main()
