"""Scratch loop for H-MACRO-S2-002. Read-only, no fetch, no DB writes.

Run:
  .venv/Scripts/python.exe -m backend.research_lab.macro_s2_indicator_outcome_matrix
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, timedelta

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg


SPLIT_DATE = "2022-01-01"
STRIDE_DAYS = 21
MIN_DEV = 36
MIN_TEST = 24
PERMUTATION_REPS = 1000
RANDOM_SEED = 20260829

RAW_SERIES = [
    "INDPRO", "CPIAUCSL", "PPIACO", "PCEPILFE", "PAYEMS", "NFCI", "VIXCLS",
    "DGS10", "WALCL", "WTREGEN", "DGS30", "GDPC1", "MTSDS133FMS", "ICSA",
    "T10YIE", "T5YIE", "DFII10", "DFII30", "BAMLH0A0HYM2", "BAMLC0A0CM",
    "SOFR", "IORB", "DTWEXBGS", "DFEDTAR", "DFEDTARU", "DFEDTARL",
]

ASSETS = [
    "SPY", "QQQ", "DIA", "IWM", "TLT", "GLD",
    "XLY", "XLI", "XLF", "XLB", "XLE", "XLP", "XLU", "XLV",
]


@dataclass(frozen=True)
class Indicator:
    key: str
    lane: str
    source_ids: tuple[str, ...]
    state_kind: str


INDICATORS = [
    Indicator("INDPRO", "fundamental", ("INDPRO",), "yoy"),
    Indicator("CPIAUCSL", "fundamental", ("CPIAUCSL",), "yoy"),
    Indicator("PPIACO", "fundamental", ("PPIACO",), "yoy"),
    Indicator("PCEPILFE", "fundamental", ("PCEPILFE",), "yoy"),
    Indicator("PAYEMS", "fundamental", ("PAYEMS",), "yoy"),
    Indicator("GDPC1", "fundamental", ("GDPC1",), "yoy"),
    Indicator("MTSDS133FMS", "fundamental", ("MTSDS133FMS",), "ttm_sum"),
    Indicator("ICSA", "fundamental", ("ICSA",), "smooth_yoy"),
    Indicator("NFCI", "transmission", ("NFCI",), "level"),
    Indicator("VIXCLS", "transmission", ("VIXCLS",), "level"),
    Indicator("BAMLH0A0HYM2", "transmission", ("BAMLH0A0HYM2",), "level"),
    Indicator("BAMLC0A0CM", "transmission", ("BAMLC0A0CM",), "level"),
    Indicator("DTWEXBGS", "transmission", ("DTWEXBGS",), "yoy"),
    Indicator("DGS10", "policy/rates", ("DGS10",), "level"),
    Indicator("DGS30", "policy/rates", ("DGS30",), "level"),
    Indicator("DFII10", "policy/rates", ("DFII10",), "level"),
    Indicator("DFII30", "policy/rates", ("DFII30",), "level"),
    Indicator("T10YIE", "policy/rates", ("T10YIE",), "level"),
    Indicator("T5YIE", "policy/rates", ("T5YIE",), "level"),
    Indicator("SOFR", "policy/rates", ("SOFR",), "level"),
    Indicator("IORB", "policy/rates", ("IORB",), "level"),
    Indicator("FED_TARGET", "policy/rates", ("DFEDTAR", "DFEDTARL", "DFEDTARU"), "level"),
    Indicator("WALCL", "liquidity", ("WALCL",), "yoy"),
    Indicator("WTREGEN", "liquidity", ("WTREGEN", "WALCL"), "tga_share"),
]


@dataclass(frozen=True)
class Target:
    key: str
    family: str
    horizon: int
    own_inputs: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        months = {21: "1M", 63: "3M", 126: "6M"}[self.horizon]
        return f"{self.key} {months}"


TARGETS = [
    *[Target("SPY return", "equity path", h) for h in (21, 63, 126)],
    *[Target("SPY max adverse excursion", "equity path", h) for h in (21, 63, 126)],
    *[Target("SPY realized volatility", "equity path", h) for h in (21, 63, 126)],
    *[Target("QQQ-DIA return spread", "equity leadership", h) for h in (63, 126)],
    *[Target("IWM-SPY return spread", "equity leadership", h) for h in (63, 126)],
    *[Target("cyclical-defensive return spread", "equity leadership", h) for h in (63, 126)],
    *[Target("TLT return", "duration/inflation", h) for h in (63, 126)],
    *[Target("DGS10 change", "duration/inflation", h, ("DGS10",)) for h in (63, 126)],
    *[Target("T10YIE change", "duration/inflation", h, ("T10YIE",)) for h in (63, 126)],
    *[Target("HY OAS change", "credit/USD", h, ("BAMLH0A0HYM2",)) for h in (21, 63)],
    *[Target("broad USD return", "credit/USD", h, ("DTWEXBGS",)) for h in (21, 63)],
    *[Target("Fed target change", "policy/liquidity", h, ("FED_TARGET",)) for h in (63, 126)],
    *[Target("WALCL return", "policy/liquidity", h, ("WALCL",)) for h in (63, 126)],
    *[Target("TGA share change", "policy/liquidity", h, ("WTREGEN",)) for h in (63, 126)],
    *[Target("GLD return", "diversifier", h) for h in (63, 126)],
    *[Target("VIX change", "volatility", h, ("VIXCLS",)) for h in (21, 63)],
]


@dataclass
class Cell:
    indicator: str
    lane: str
    target: str
    family: str
    view: str
    validation: str
    self_series: bool
    dev_n: int
    test_n: int
    dev_ic: float
    test_ic: float
    p_value: float
    q_value: float = 1.0
    verdict: str = "inconclusive"
    test_start: str = ""
    test_end: str = ""


def _latest_dataset(connection) -> str:
    series_marks = ",".join("?" for _ in RAW_SERIES)
    asset_marks = ",".join("?" for _ in ASSETS)
    row = connection.execute(
        f"""
        SELECT dataset.id
        FROM dataset_snapshots AS dataset
        WHERE dataset.immutable = 1
          AND (SELECT COUNT(DISTINCT series_id) FROM fred_observations
               WHERE dataset_snapshot_id = dataset.id AND series_id IN ({series_marks})) = ?
          AND (SELECT COUNT(DISTINCT security.primary_symbol)
               FROM symbol_bars AS bar
               JOIN securities AS security ON security.security_id = bar.security_id
               WHERE bar.dataset_snapshot_id = dataset.id
                 AND security.primary_symbol IN ({asset_marks})) = ?
        ORDER BY dataset.as_of DESC, dataset.rowid DESC
        LIMIT 1
        """,
        (*RAW_SERIES, len(RAW_SERIES), *ASSETS, len(ASSETS)),
    ).fetchone()
    if row is None:
        raise RuntimeError("No sealed dataset contains the full S2-002 input and target set.")
    return row["id"]


def _load_fred(connection, dataset_id: str) -> dict[str, list[tuple[str, float]]]:
    result = {}
    for series_id in RAW_SERIES:
        rows = connection.execute(
            "SELECT observation_date, value FROM fred_observations "
            "WHERE dataset_snapshot_id = ? AND series_id = ? AND value IS NOT NULL "
            "ORDER BY observation_date",
            (dataset_id, series_id),
        ).fetchall()
        result[series_id] = [(row["observation_date"], float(row["value"])) for row in rows]
    return result


def _load_assets(connection, dataset_id: str) -> dict[str, list[tuple[str, float]]]:
    result = {}
    for symbol in ASSETS:
        rows = connection.execute(
            """
            SELECT bar.time, bar.close
            FROM symbol_bars AS bar
            JOIN securities AS security ON security.security_id = bar.security_id
            WHERE bar.dataset_snapshot_id = ? AND security.primary_symbol = ?
              AND bar.close IS NOT NULL ORDER BY bar.time
            """,
            (dataset_id, symbol),
        ).fetchall()
        result[symbol] = [(row["time"], float(row["close"])) for row in rows]
    return result


def _prior(series: list[tuple[str, float]], as_of: str) -> float | None:
    low, high = 0, len(series)
    while low < high:
        middle = (low + high) // 2
        if series[middle][0] <= as_of:
            low = middle + 1
        else:
            high = middle
    return series[low - 1][1] if low else None


def _prior_dated(series: list[tuple[str, float]], as_of: str) -> tuple[str, float] | None:
    low, high = 0, len(series)
    while low < high:
        middle = (low + high) // 2
        if series[middle][0] <= as_of:
            low = middle + 1
        else:
            high = middle
    return series[low - 1] if low else None


def _fed_target(raw: dict[str, list[tuple[str, float]]]) -> list[tuple[str, float]]:
    values = {d: v for d, v in raw["DFEDTAR"]}
    lower = dict(raw["DFEDTARL"])
    upper = dict(raw["DFEDTARU"])
    for observation_date in sorted(set(lower) & set(upper)):
        values[observation_date] = (lower[observation_date] + upper[observation_date]) / 2.0
    return sorted(values.items())


def _economic_state(
    indicator: Indicator, raw: dict[str, list[tuple[str, float]]], fed_target: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if indicator.key == "FED_TARGET":
        return fed_target
    base = raw[indicator.source_ids[0]]
    if indicator.state_kind == "level":
        return base
    if indicator.state_kind == "yoy":
        output = []
        for observation_date, value in base:
            prior = _prior(base, (date.fromisoformat(observation_date) - timedelta(days=365)).isoformat())
            if prior not in (None, 0):
                output.append((observation_date, value / prior - 1.0))
        return output
    if indicator.state_kind == "ttm_sum":
        return [
            (observation_date, sum(value for _, value in base[max(0, index - 11) : index + 1]))
            for index, (observation_date, _) in enumerate(base)
            if index >= 11
        ]
    if indicator.state_kind == "smooth_yoy":
        smooth = [
            (observation_date, sum(value for _, value in base[max(0, index - 12) : index + 1]) / 13.0)
            for index, (observation_date, _) in enumerate(base)
            if index >= 12
        ]
        output = []
        for observation_date, value in smooth:
            prior = _prior(smooth, (date.fromisoformat(observation_date) - timedelta(days=365)).isoformat())
            if prior not in (None, 0):
                output.append((observation_date, value / prior - 1.0))
        return output
    if indicator.state_kind == "tga_share":
        walcl = raw["WALCL"]
        output = []
        for observation_date, value in base:
            denominator = _prior(walcl, observation_date)
            if denominator not in (None, 0):
                output.append((observation_date, value / denominator))
        return output
    raise ValueError(indicator.state_kind)


def _impulse(state: list[tuple[str, float]]) -> list[tuple[str, float]]:
    output = []
    for observation_date, value in state:
        previous = _prior(state, (date.fromisoformat(observation_date) - timedelta(days=91)).isoformat())
        if previous is not None:
            output.append((observation_date, value - previous))
    return output


def _asset_return(series: list[tuple[str, float]], start: str, end: str) -> float | None:
    first = _prior(series, start)
    last = _prior(series, end)
    if first in (None, 0) or last is None:
        return None
    return last / first - 1.0


def _fred_change(series: list[tuple[str, float]], start: str, end: str, percent: bool = False) -> float | None:
    first = _prior(series, start)
    last = _prior(series, end)
    if first is None or last is None or (percent and first == 0):
        return None
    return last / first - 1.0 if percent else last - first


def _target_value(
    target: Target,
    anchor_index: int,
    assets: dict[str, list[tuple[str, float]]],
    raw: dict[str, list[tuple[str, float]]],
    fed_target: list[tuple[str, float]],
) -> float | None:
    spy = assets["SPY"]
    future_index = anchor_index + target.horizon
    if future_index >= len(spy):
        return None
    start_date, start_close = spy[anchor_index]
    end_date = spy[future_index][0]
    if target.key == "SPY return":
        return spy[future_index][1] / start_close - 1.0
    if target.key == "SPY max adverse excursion":
        return min(close / start_close - 1.0 for _, close in spy[anchor_index + 1 : future_index + 1])
    if target.key == "SPY realized volatility":
        prices = [close for _, close in spy[anchor_index : future_index + 1]]
        returns = [prices[i] / prices[i - 1] - 1.0 for i in range(1, len(prices))]
        mean = sum(returns) / len(returns)
        return math.sqrt(sum((value - mean) ** 2 for value in returns) / len(returns)) * math.sqrt(252)
    if target.key == "QQQ-DIA return spread":
        qqq = _asset_return(assets["QQQ"], start_date, end_date)
        dia = _asset_return(assets["DIA"], start_date, end_date)
        return None if qqq is None or dia is None else qqq - dia
    if target.key == "IWM-SPY return spread":
        iwm = _asset_return(assets["IWM"], start_date, end_date)
        spy_return = _asset_return(assets["SPY"], start_date, end_date)
        return None if iwm is None or spy_return is None else iwm - spy_return
    if target.key == "cyclical-defensive return spread":
        cyclical = [_asset_return(assets[s], start_date, end_date) for s in ("XLY", "XLI", "XLF", "XLB", "XLE")]
        defensive = [_asset_return(assets[s], start_date, end_date) for s in ("XLP", "XLU", "XLV")]
        if any(value is None for value in cyclical + defensive):
            return None
        return sum(cyclical) / len(cyclical) - sum(defensive) / len(defensive)  # type: ignore[arg-type]
    if target.key in ("TLT return", "GLD return"):
        return _asset_return(assets[target.key.split()[0]], start_date, end_date)
    if target.key == "DGS10 change":
        return _fred_change(raw["DGS10"], start_date, end_date)
    if target.key == "T10YIE change":
        return _fred_change(raw["T10YIE"], start_date, end_date)
    if target.key == "HY OAS change":
        return _fred_change(raw["BAMLH0A0HYM2"], start_date, end_date)
    if target.key == "broad USD return":
        return _fred_change(raw["DTWEXBGS"], start_date, end_date, percent=True)
    if target.key == "Fed target change":
        return _fred_change(fed_target, start_date, end_date)
    if target.key == "WALCL return":
        return _fred_change(raw["WALCL"], start_date, end_date, percent=True)
    if target.key == "TGA share change":
        start_tga, end_tga = _prior(raw["WTREGEN"], start_date), _prior(raw["WTREGEN"], end_date)
        start_walcl, end_walcl = _prior(raw["WALCL"], start_date), _prior(raw["WALCL"], end_date)
        if None in (start_tga, end_tga, start_walcl, end_walcl) or start_walcl == 0 or end_walcl == 0:
            return None
        return end_tga / end_walcl - start_tga / start_walcl  # type: ignore[operator]
    if target.key == "VIX change":
        return _fred_change(raw["VIXCLS"], start_date, end_date)
    raise ValueError(target.key)


def _ranks(values: list[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[index]]:
            end += 1
        rank = (index + end - 1) / 2.0 + 1.0
        for position in ordered[index:end]:
            result[position] = rank
        index = end
    return result


def _pearson(x: list[float], y: list[float]) -> float:
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return float("nan")
    xm, ym = sum(x) / len(x), sum(y) / len(y)
    numerator = sum((a - xm) * (b - ym) for a, b in zip(x, y))
    denominator = math.sqrt(sum((a - xm) ** 2 for a in x) * sum((b - ym) ** 2 for b in y))
    return numerator / denominator if denominator else float("nan")


def _rank_ic(x: list[float], y: list[float]) -> float:
    return _pearson(_ranks(x), _ranks(y))


def _block_p(x: list[float], y: list[float], block_size: int, seed: int) -> float:
    observed = _rank_ic(x, y)
    if not math.isfinite(observed):
        return 1.0
    x_rank, y_rank = _ranks(x), _ranks(y)
    blocks = [y_rank[index : index + block_size] for index in range(0, len(y_rank), block_size)]
    rng = random.Random(seed)
    extreme = 0
    for _ in range(PERMUTATION_REPS):
        shuffled = blocks[:]
        rng.shuffle(shuffled)
        candidate = _pearson(x_rank, [v for block in shuffled for v in block][: len(y_rank)])
        if math.isfinite(candidate) and abs(candidate) >= abs(observed):
            extreme += 1
    return (extreme + 1) / (PERMUTATION_REPS + 1)


def _samples(
    indicator: Indicator,
    target: Target,
    states: dict[str, list[tuple[str, float]]],
    impulses: dict[str, list[tuple[str, float]]],
    assets: dict[str, list[tuple[str, float]]],
    raw: dict[str, list[tuple[str, float]]],
    fed_target: list[tuple[str, float]],
) -> list[tuple[str, float, float, float]]:
    result = []
    for anchor_index in range(0, len(assets["SPY"]), STRIDE_DAYS):
        anchor = assets["SPY"][anchor_index][0]
        state = _prior(states[indicator.key], anchor)
        impulse = _prior(impulses[indicator.key], anchor)
        outcome = _target_value(target, anchor_index, assets, raw, fed_target)
        if state is not None and impulse is not None and outcome is not None:
            result.append((anchor, state, impulse, outcome))
    return result


def _cell(
    indicator: Indicator,
    target: Target,
    states: dict[str, list[tuple[str, float]]],
    impulses: dict[str, list[tuple[str, float]]],
    assets: dict[str, list[tuple[str, float]]],
    raw: dict[str, list[tuple[str, float]]],
    fed_target: list[tuple[str, float]],
    seed: int,
) -> Cell:
    samples = _samples(indicator, target, states, impulses, assets, raw, fed_target)
    dev = [row for row in samples if row[0] < SPLIT_DATE]
    test = [row for row in samples if row[0] >= SPLIT_DATE]
    validation = "fixed"
    if (len(dev) < MIN_DEV or len(test) < MIN_TEST) and len(samples) >= 24:
        cutoff = max(16, int(len(samples) * 2 / 3))
        if len(samples) - cutoff >= 8:
            dev, test = samples[:cutoff], samples[cutoff:]
            validation = "exploratory"
    state_ic = _rank_ic([r[1] for r in dev], [r[3] for r in dev])
    impulse_ic = _rank_ic([r[2] for r in dev], [r[3] for r in dev])
    if math.isfinite(impulse_ic) and (not math.isfinite(state_ic) or abs(impulse_ic) > abs(state_ic)):
        view, position = "impulse", 2
        dev_ic = impulse_ic
    else:
        view, position = "state", 1
        dev_ic = state_ic
    test_x, test_y = [r[position] for r in test], [r[3] for r in test]
    test_ic = _rank_ic(test_x, test_y)
    if validation == "fixed" and len(dev) >= MIN_DEV and len(test) >= MIN_TEST:
        p_value = _block_p(
            test_x,
            test_y,
            max(1, math.ceil(target.horizon / STRIDE_DAYS)),
            RANDOM_SEED + seed,
        )
    else:
        p_value = 1.0
    return Cell(
        indicator.key,
        indicator.lane,
        target.label,
        target.family,
        view,
        validation,
        indicator.key in target.own_inputs,
        len(dev),
        len(test),
        dev_ic,
        test_ic,
        p_value,
        test_start=test[0][0] if test else "",
        test_end=test[-1][0] if test else "",
    )


def _evaluate(cells: list[Cell]) -> None:
    for target in sorted(set(cell.target for cell in cells)):
        group = [
            cell for cell in cells
            if cell.target == target and cell.validation == "fixed"
            and cell.dev_n >= MIN_DEV and cell.test_n >= MIN_TEST
        ]
        if group:
            adjusted, _ = benjamini_hochberg([cell.p_value for cell in group], alpha=0.10)
            for cell, q_value in zip(group, adjusted):
                cell.q_value = q_value
    for cell in cells:
        if cell.validation == "exploratory":
            cell.verdict = "exploratory"
        elif cell.dev_n < MIN_DEV or cell.test_n < MIN_TEST:
            cell.verdict = "insufficient"
        elif (
            math.isfinite(cell.dev_ic)
            and math.isfinite(cell.test_ic)
            and cell.dev_ic * cell.test_ic > 0
            and abs(cell.test_ic) >= 0.15
            and cell.q_value <= 0.10
        ):
            cell.verdict = "supported"


def _fmt(value: float) -> str:
    return f"{value:+.3f}" if math.isfinite(value) else "NA"


def _print_summary(dataset_id: str, cells: list[Cell]) -> None:
    print(f"Dataset: {dataset_id}")
    print(f"Inputs: {len(INDICATORS)} economic indicators from {len(RAW_SERIES)} stored FRED series")
    print(f"Targets: {len(TARGETS)} target-horizon routes; cells: {len(cells)}")
    print(f"Anchors: {STRIDE_DAYS} trading days; split: {SPLIT_DATE}; permutations: {PERMUTATION_REPS}")
    print()

    print("## Per input: strongest supported cross-series route")
    print("| Input | Lane | Supported routes | Best route | View | Dev/Test N | Dev IC | Test IC | q | Status |")
    print("| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |")
    for indicator in INDICATORS:
        own = [c for c in cells if c.indicator == indicator.key and not c.self_series]
        supported = [c for c in own if c.verdict == "supported"]
        eligible = [c for c in own if c.verdict == "inconclusive" and math.isfinite(c.test_ic)]
        exploratory = [c for c in own if c.verdict == "exploratory" and math.isfinite(c.test_ic)]
        pool = supported or eligible or exploratory
        if pool:
            best = max(pool, key=lambda c: abs(c.test_ic))
            status = "supported" if supported else ("none supported" if eligible else "exploratory only")
            print(
                f"| {indicator.key} | {indicator.lane} | {len(supported)} | {best.target} | {best.view} | "
                f"{best.dev_n}/{best.test_n} | {_fmt(best.dev_ic)} | {_fmt(best.test_ic)} | {best.q_value:.3f} | {status} |"
            )
        else:
            print(f"| {indicator.key} | {indicator.lane} | 0 | — | — | — | — | — | — | insufficient |")
    print()

    print("## Per target: strongest supported cross-series inputs by lane")
    print("| Target | Supported cross/self | Exploratory cells | Best distinct-lane cross inputs |")
    print("| --- | ---: | ---: | --- |")
    for target in TARGETS:
        group = [c for c in cells if c.target == target.label]
        supported_cross = [c for c in group if c.verdict == "supported" and not c.self_series]
        supported_self = [c for c in group if c.verdict == "supported" and c.self_series]
        exploratory = [c for c in group if c.verdict == "exploratory"]
        selected = []
        for cell in sorted(supported_cross, key=lambda c: -abs(c.test_ic)):
            if cell.lane not in {item.lane for item in selected}:
                selected.append(cell)
            if len(selected) == 3:
                break
        leaders = "; ".join(f"{c.indicator} {c.view} ({_fmt(c.test_ic)}, q={c.q_value:.3f})" for c in selected) or "none"
        print(f"| {target.label} | {len(supported_cross)}/{len(supported_self)} | {len(exploratory)} | {leaders} |")
    print()

    print("## Self-series results (kept separate)")
    print("| Input -> target | View | Dev/Test N | Dev IC | Test IC | q | Status |")
    print("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for cell in cells:
        if cell.self_series:
            print(
                f"| {cell.indicator} -> {cell.target} | {cell.view} | {cell.dev_n}/{cell.test_n} | "
                f"{_fmt(cell.dev_ic)} | {_fmt(cell.test_ic)} | {cell.q_value:.3f} | {cell.verdict} |"
            )
    print()

    print("## Coverage")
    counts = {
        name: sum(cell.verdict == name for cell in cells)
        for name in ("supported", "inconclusive", "exploratory", "insufficient")
    }
    print(counts)
    no_confirmatory = sorted({indicator.key for indicator in INDICATORS if not any(
        cell.indicator == indicator.key and cell.validation == "fixed" and cell.verdict != "insufficient"
        for cell in cells
    )})
    print("Inputs with no confirmatory route:", ", ".join(no_confirmatory) or "none")
    print("PIT limitation: current-vintage FRED values are aligned by observation date, not historical release timestamp.")


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_id = _latest_dataset(connection)
    raw = _load_fred(connection, dataset_id)
    assets = _load_assets(connection, dataset_id)
    fed_target = _fed_target(raw)
    states = {indicator.key: _economic_state(indicator, raw, fed_target) for indicator in INDICATORS}
    impulses = {key: _impulse(value) for key, value in states.items()}
    cells = []
    for target_index, target in enumerate(TARGETS):
        for indicator_index, indicator in enumerate(INDICATORS):
            cells.append(
                _cell(
                    indicator,
                    target,
                    states,
                    impulses,
                    assets,
                    raw,
                    fed_target,
                    target_index * len(INDICATORS) + indicator_index,
                )
            )
    _evaluate(cells)
    _print_summary(dataset_id, cells)


if __name__ == "__main__":
    main()
