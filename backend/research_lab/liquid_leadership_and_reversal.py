"""H-XSEC-S2-004: liquid-stock leadership continuation and weekly reversal.

One read-only Stage 2 loop, two deliberately separate tail relationships.
It never writes the database and has no production authority.

Run:
    .venv/Scripts/python.exe -m backend.research_lab.liquid_leadership_and_reversal
"""

from __future__ import annotations

import argparse
import math
import statistics
import zlib
from collections import defaultdict
from datetime import date

import numpy as np
from scipy import stats

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg
from backend.research_lab.price_volume_factor_screen import ANCHOR_DATASET_ID
from backend.universe.library_fetch import (
    DUAL_BASIS_CONTRACT_REVISION,
    LIBRARY_CONTRACT_THROUGH,
    LIBRARY_DATASET_ID,
    LIBRARY_UNIVERSE_STAGE,
)


SPY = "SPY"
SECTORS = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")
MAG7 = frozenset(("AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"))
MOMENTUM_SIGNALS = (
    "momentum_1m",
    "momentum_3m",
    "momentum_6m",
    "momentum_12m",
    "classic_12_1",
    "multi_1_3_6_12",
)
REVERSAL_SIGNALS = ("reversal_5d", "sector_relative_reversal_5d")
SIGNALS = MOMENTUM_SIGNALS + REVERSAL_SIGNALS
MOMENTUM_HORIZONS = (5, 21, 63, 126)
REVERSAL_HORIZONS = (5, 10, 21)
PRIMARY_HORIZON = {**{signal: 63 for signal in MOMENTUM_SIGNALS}, **{signal: 5 for signal in REVERSAL_SIGNALS}}
MIN_PRICE = 5.0
MIN_HISTORY = 252
MIN_POOL = 30
BOOTSTRAP_DRAWS = 2_000


def finite(value) -> bool:
    return value is not None and math.isfinite(float(value))


def pct(value, digits=2):
    return "NA" if not finite(value) else f"{100 * float(value):+.{digits}f}%"


def number(value, digits=3):
    return "NA" if not finite(value) else f"{float(value):+.{digits}f}"


def pnumber(value):
    if not finite(value):
        return "NA"
    return "<.0001" if float(value) < 0.0001 else f"{float(value):.4f}"


def fold_for(day_string: str) -> str:
    day = date.fromisoformat(day_string)
    if day <= date(2018, 12, 31):
        return "development"
    if day <= date(2023, 6, 30):
        return "validation"
    return "recent"


def weekly_formations(dates: list[str]) -> list[int]:
    last_by_week: dict[tuple[int, int], int] = {}
    for index, value in enumerate(dates):
        parsed = date.fromisoformat(value)
        iso = parsed.isocalendar()
        last_by_week[(iso.year, iso.week)] = index
    return [
        index
        for index in last_by_week.values()
        if index >= MIN_HISTORY and index + max(MOMENTUM_HORIZONS) < len(dates)
    ]


def trailing_return(values: np.ndarray, start: int, end: int):
    first, last = values[start], values[end]
    if not finite(first) or not finite(last) or first <= 0:
        return None
    return float(last / first - 1.0)


def load_panel(connection):
    coverage = connection.execute(
        """
        WITH cohort AS (
            SELECT DISTINCT m.symbol
            FROM staging_universe_membership AS m
            JOIN staging_symbols AS s ON s.symbol = m.symbol
            WHERE m.stage = ? AND s.research_scope = 'general'
        ), mapped AS (
            SELECT primary_symbol, MIN(security_id) AS security_id, COUNT(*) AS n
            FROM securities GROUP BY primary_symbol
        ), bars AS (
            SELECT security_id, COUNT(*) AS n, MIN(time) AS first_bar, MAX(time) AS last_bar
            FROM symbol_bars WHERE dataset_snapshot_id = ? GROUP BY security_id
        )
        SELECT COUNT(*) AS eligible,
               SUM(CASE WHEN r.coverage_status = 'accepted'
                         AND r.contract_revision = ? AND r.requested_to >= ?
                         AND r.security_id = mapped.security_id
                         AND bars.n = r.returned_bar_count
                         AND bars.first_bar = r.returned_from
                         AND bars.last_bar = r.returned_to
                        THEN 1 ELSE 0 END) AS accepted
        FROM cohort
        LEFT JOIN mapped ON mapped.primary_symbol = cohort.symbol AND mapped.n = 1
        LEFT JOIN staging_price_fetch_status AS r
          ON r.dataset_snapshot_id = ? AND r.symbol = cohort.symbol AND r.source_key = 'yahoo'
        LEFT JOIN bars ON bars.security_id = mapped.security_id
        """,
        (
            LIBRARY_UNIVERSE_STAGE,
            LIBRARY_DATASET_ID,
            DUAL_BASIS_CONTRACT_REVISION,
            LIBRARY_CONTRACT_THROUGH,
            LIBRARY_DATASET_ID,
        ),
    ).fetchone()
    if coverage is None or coverage["accepted"] != coverage["eligible"]:
        raise RuntimeError(
            f"price gate closed: {0 if coverage is None else coverage['accepted']}/"
            f"{0 if coverage is None else coverage['eligible']} accepted receipts"
        )

    symbols = [
        row["symbol"]
        for row in connection.execute(
            """SELECT DISTINCT m.symbol
               FROM staging_universe_membership AS m
               JOIN staging_symbols AS s ON s.symbol = m.symbol
               WHERE m.stage = ? AND s.research_scope = 'general'
               ORDER BY m.symbol""",
            (LIBRARY_UNIVERSE_STAGE,),
        )
    ]
    sector_by_symbol: dict[str, str] = {}
    placeholders = ",".join("?" for _ in SECTORS)
    for row in connection.execute(
        f"""SELECT DISTINCT symbol, anchor
             FROM staging_universe_membership
             WHERE stage = ? AND anchor IN ({placeholders})
             ORDER BY symbol""",
        (LIBRARY_UNIVERSE_STAGE, *SECTORS),
    ):
        if row["symbol"] in sector_by_symbol:
            raise RuntimeError(f"primary-sector membership is not unique: {row['symbol']}")
        sector_by_symbol[row["symbol"]] = row["anchor"]

    spy_security = connection.execute(
        "SELECT security_id FROM securities WHERE primary_symbol = ? ORDER BY security_id LIMIT 1",
        (SPY,),
    ).fetchone()
    if spy_security is None:
        raise RuntimeError("SPY security identity is missing")
    spy_rows = connection.execute(
        """SELECT time FROM symbol_bars
           WHERE dataset_snapshot_id = ? AND security_id = ?
             AND COALESCE(adjusted_close, close) IS NOT NULL
           ORDER BY time""",
        (ANCHOR_DATASET_ID, spy_security["security_id"]),
    ).fetchall()
    dates = [row["time"] for row in spy_rows]
    date_index = {day: index for index, day in enumerate(dates)}
    arrays = {
        symbol: {
            "close": np.full(len(dates), np.nan),
            "open": np.full(len(dates), np.nan),
            "raw_close": np.full(len(dates), np.nan),
            "volume": np.full(len(dates), np.nan),
        }
        for symbol in symbols
    }

    for row in connection.execute(
        """SELECT s.primary_symbol AS symbol, b.time, b.adjusted_close,
                  b.adjusted_open, b.raw_close, b.volume
           FROM symbol_bars AS b
           JOIN securities AS s ON s.security_id = b.security_id
           WHERE b.dataset_snapshot_id = ?
           ORDER BY s.primary_symbol, b.time""",
        (LIBRARY_DATASET_ID,),
    ):
        target = arrays.get(row["symbol"])
        index = date_index.get(row["time"])
        if target is None or index is None:
            continue
        target["close"][index] = row["adjusted_close"]
        target["open"][index] = row["adjusted_open"]
        target["raw_close"][index] = row["raw_close"]
        target["volume"][index] = row["volume"]

    return {
        "dates": dates,
        "symbols": symbols,
        "sector_by_symbol": sector_by_symbol,
        "arrays": arrays,
        "accepted": int(coverage["accepted"]),
    }


def snapshot(panel, formation: int):
    rows = {}
    for symbol in panel["symbols"]:
        values = panel["arrays"][symbol]
        close = values["close"]
        raw_close = values["raw_close"]
        volume = values["volume"]
        signal_points = (formation, formation - 5, formation - 21, formation - 63, formation - 126, formation - 252)
        if not all(finite(close[index]) and close[index] > 0 for index in signal_points):
            continue
        if not finite(values["open"][formation + 1]) or values["open"][formation + 1] <= 0:
            continue
        if not finite(raw_close[formation]) or raw_close[formation] < MIN_PRICE:
            continue
        dollar_volume = raw_close[formation - 20 : formation + 1] * volume[formation - 20 : formation + 1]
        if len(dollar_volume) != 21 or not np.all(np.isfinite(dollar_volume)) or np.any(dollar_volume <= 0):
            continue
        momentum = {
            "momentum_1m": trailing_return(close, formation - 21, formation),
            "momentum_3m": trailing_return(close, formation - 63, formation),
            "momentum_6m": trailing_return(close, formation - 126, formation),
            "momentum_12m": trailing_return(close, formation - 252, formation),
            "classic_12_1": trailing_return(close, formation - 252, formation - 21),
        }
        if not all(finite(value) for value in momentum.values()):
            continue
        rows[symbol] = {
            "adv21": float(np.median(dollar_volume)),
            "sector": panel["sector_by_symbol"].get(symbol),
            "return_5d": trailing_return(close, formation - 5, formation),
            **momentum,
        }
    return rows


def percentile_scores(values: list[float]) -> np.ndarray:
    if len(values) == 1:
        return np.array([0.5])
    return (stats.rankdata(values, method="average") - 1.0) / (len(values) - 1.0)


def pool_scores(symbols: list[str], snapshots: dict[str, dict[str, object]]):
    result = {signal: {} for signal in SIGNALS}
    for signal in MOMENTUM_SIGNALS[:-1]:
        result[signal] = {symbol: float(snapshots[symbol][signal]) for symbol in symbols}
    component_ranks = []
    for signal in ("momentum_1m", "momentum_3m", "momentum_6m", "momentum_12m"):
        component_ranks.append(percentile_scores([float(snapshots[symbol][signal]) for symbol in symbols]))
    composite = np.mean(np.vstack(component_ranks), axis=0)
    result["multi_1_3_6_12"] = {symbol: float(value) for symbol, value in zip(symbols, composite)}
    result["reversal_5d"] = {symbol: -float(snapshots[symbol]["return_5d"]) for symbol in symbols}

    sector_returns: dict[str, list[float]] = defaultdict(list)
    for symbol in symbols:
        sector = snapshots[symbol]["sector"]
        if sector:
            sector_returns[str(sector)].append(float(snapshots[symbol]["return_5d"]))
    sector_means = {sector: statistics.fmean(values) for sector, values in sector_returns.items() if len(values) >= 3}
    result["sector_relative_reversal_5d"] = {
        symbol: -(float(snapshots[symbol]["return_5d"]) - sector_means[str(snapshots[symbol]["sector"])])
        for symbol in symbols
        if snapshots[symbol]["sector"] and str(snapshots[symbol]["sector"]) in sector_means
    }
    return result


def forward_returns(panel, symbols: list[str], formation: int, horizon: int):
    result = {}
    for symbol in symbols:
        entry = panel["arrays"][symbol]["open"][formation + 1]
        exit_price = panel["arrays"][symbol]["close"][formation + horizon]
        if finite(entry) and finite(exit_price) and entry > 0:
            result[symbol] = float(exit_price / entry - 1.0)
    return result


def evaluate_cell(
    symbols: list[str],
    scores: dict[str, float],
    outcomes: dict[str, float],
    sector_by_symbol: dict[str, str],
):
    usable = [symbol for symbol in symbols if symbol in scores and symbol in outcomes]
    if len(usable) < MIN_POOL:
        return None
    x = np.array([scores[symbol] for symbol in usable], dtype=float)
    y = np.array([outcomes[symbol] for symbol in usable], dtype=float)
    order = np.argsort(x)
    tail_size = max(1, len(order) // 10)
    selected = [usable[index] for index in order[-tail_size:]]
    pool_return = float(np.mean(y))
    tail_return = statistics.fmean(outcomes[symbol] for symbol in selected)
    ic_result = stats.spearmanr(x, y)

    sector_outcomes: dict[str, list[float]] = defaultdict(list)
    for symbol in usable:
        sector = sector_by_symbol.get(symbol)
        if sector:
            sector_outcomes[sector].append(outcomes[symbol])
    sector_excesses = []
    for symbol in selected:
        sector = sector_by_symbol.get(symbol)
        peers = sector_outcomes.get(sector or "", [])
        if len(peers) >= 3:
            sector_excesses.append(outcomes[symbol] - statistics.fmean(peers))

    deciles = []
    for bucket in np.array_split(order, 10):
        deciles.append(float(np.mean(y[bucket]) - pool_return) if len(bucket) else None)
    return {
        "tail_excess": tail_return - pool_return,
        "sector_excess": statistics.fmean(sector_excesses) if sector_excesses else None,
        "ic": float(ic_result.statistic) if finite(ic_result.statistic) else None,
        "selected": frozenset(selected),
        "deciles": deciles,
        "names": len(usable),
    }


def build_pools(snapshots):
    ordered = sorted(snapshots, key=lambda symbol: (-float(snapshots[symbol]["adv21"]), symbol))
    sector_leaders = []
    by_sector: dict[str, list[str]] = defaultdict(list)
    for symbol in ordered:
        sector = snapshots[symbol]["sector"]
        if sector:
            by_sector[str(sector)].append(symbol)
    for sector in sorted(by_sector):
        sector_leaders.extend(by_sector[sector][:2])
    return {
        "top100": ordered[:100],
        "top200": ordered[:200],
        "control201plus": ordered[200:],
        "mag7": [symbol for symbol in ordered if symbol in MAG7],
        "sector_leaders": sector_leaders,
    }


def run(panel):
    rows = defaultdict(list)
    previous_selection: dict[tuple[str, str], frozenset[str]] = {}
    coverage = []
    formations = weekly_formations(panel["dates"])
    for formation in formations:
        snapshots = snapshot(panel, formation)
        pools = build_pools(snapshots)
        coverage.append((len(snapshots), len(pools["top100"]), len(pools["control201plus"])))
        for pool_name, pool_symbols in pools.items():
            if len(pool_symbols) < MIN_POOL and pool_name not in ("mag7", "sector_leaders"):
                continue
            if len(pool_symbols) < 3:
                continue
            scores_by_signal = pool_scores(pool_symbols, snapshots)
            for signal in SIGNALS:
                horizons = MOMENTUM_HORIZONS if signal in MOMENTUM_SIGNALS else REVERSAL_HORIZONS
                current_scores = scores_by_signal[signal]
                turnover_for_signal = None
                for horizon in horizons:
                    outcomes = forward_returns(panel, pool_symbols, formation, horizon)
                    minimum = 3 if pool_name in ("mag7", "sector_leaders") else MIN_POOL
                    usable_symbols = [symbol for symbol in pool_symbols if symbol in current_scores and symbol in outcomes]
                    if len(usable_symbols) < minimum:
                        continue
                    cell = evaluate_cell(
                        usable_symbols,
                        current_scores,
                        outcomes,
                        panel["sector_by_symbol"],
                    ) if len(usable_symbols) >= MIN_POOL else None
                    if cell is None and pool_name in ("mag7", "sector_leaders"):
                        x = np.array([current_scores[symbol] for symbol in usable_symbols])
                        y = np.array([outcomes[symbol] for symbol in usable_symbols])
                        order = np.argsort(x)
                        tail_size = max(1, len(order) // 3)
                        selected = [usable_symbols[index] for index in order[-tail_size:]]
                        pool_return = float(np.mean(y))
                        ic = None if np.ptp(x) <= 1e-12 or np.ptp(y) <= 1e-12 else stats.spearmanr(x, y).statistic
                        cell = {
                            "tail_excess": statistics.fmean(outcomes[symbol] for symbol in selected) - pool_return,
                            "sector_excess": None,
                            "ic": float(ic) if finite(ic) else None,
                            "selected": frozenset(selected),
                            "deciles": [],
                            "names": len(usable_symbols),
                        }
                    if cell is None:
                        continue
                    selection_key = (pool_name, signal)
                    if horizon == min(horizons):
                        prior = previous_selection.get(selection_key)
                        if prior:
                            turnover_for_signal = len(cell["selected"] - prior) / len(cell["selected"])
                        previous_selection[selection_key] = cell["selected"]
                    rows[(pool_name, signal, horizon)].append(
                        {
                            "date": panel["dates"][formation],
                            "exit_date": panel["dates"][formation + horizon],
                            "fold": fold_for(panel["dates"][formation]),
                            "exit_fold": fold_for(panel["dates"][formation + horizon]),
                            "turnover": turnover_for_signal,
                            **cell,
                        }
                    )
    return rows, coverage, formations


def mean_or_none(values):
    clean = [float(value) for value in values if finite(value)]
    return statistics.fmean(clean) if clean else None


def summarize(cell_rows, fold=None):
    selected = [
        row
        for row in cell_rows
        if fold is None or (row["fold"] == fold and row["exit_fold"] == fold)
    ]
    return {
        "formations": len(selected),
        "tail_excess": mean_or_none(row["tail_excess"] for row in selected),
        "sector_excess": mean_or_none(row["sector_excess"] for row in selected),
        "ic": mean_or_none(row["ic"] for row in selected),
        "hit": mean_or_none(row["tail_excess"] > 0 for row in selected),
        "turnover": mean_or_none(row["turnover"] for row in selected),
        "names": mean_or_none(row["names"] for row in selected),
    }


def quarter_block_inference(cell_rows, draws: int, seed: int):
    post = [
        row
        for row in cell_rows
        if row["fold"] in ("validation", "recent") and row["fold"] == row["exit_fold"]
    ]
    if len(post) < 20:
        return None, None, None
    grouped: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in post:
        parsed = date.fromisoformat(row["date"])
        grouped[(parsed.year, (parsed.month - 1) // 3 + 1)].append(float(row["tail_excess"]))
    blocks = [np.asarray(values, dtype=float) for _, values in sorted(grouped.items())]
    if len(blocks) < 8:
        return None, None, None
    observed = statistics.fmean(row["tail_excess"] for row in post)
    centered = [block - observed for block in blocks]
    rng = np.random.default_rng(seed)
    boot, null = [], []
    for _ in range(draws):
        chosen = rng.integers(0, len(blocks), len(blocks))
        boot.append(float(np.mean(np.concatenate([blocks[index] for index in chosen]))))
        null.append(float(np.mean(np.concatenate([centered[index] for index in chosen]))))
    p_value = (1 + sum(value >= observed for value in null)) / (draws + 1)
    low, high = np.quantile(boot, (0.025, 0.975))
    return p_value, float(low), float(high)


def summarize_results(rows, draws):
    primary = []
    for signal in SIGNALS:
        horizon = PRIMARY_HORIZON[signal]
        cell_rows = rows[("top100", signal, horizon)]
        item = {
            "signal": signal,
            "horizon": horizon,
            "full": summarize(cell_rows),
            "development": summarize(cell_rows, "development"),
            "validation": summarize(cell_rows, "validation"),
            "recent": summarize(cell_rows, "recent"),
        }
        seed = zlib.crc32(f"{signal}:{horizon}".encode("utf-8"))
        item["p"], item["ci_low"], item["ci_high"] = quarter_block_inference(cell_rows, draws, seed)
        primary.append(item)
    valid = [index for index, item in enumerate(primary) if finite(item["p"])]
    adjusted, _ = benjamini_hochberg([primary[index]["p"] for index in valid])
    q_by_index = dict(zip(valid, adjusted))
    for index, item in enumerate(primary):
        q_value = q_by_index.get(index)
        item["q"] = q_value
        item["candidate"] = (
            finite(q_value)
            and q_value < 0.10
            and all(
                finite(item[fold]["tail_excess"]) and item[fold]["tail_excess"] > 0
                for fold in ("development", "validation", "recent")
            )
        )
    return primary


def print_results(panel, rows, coverage, formations, primary, draws):
    eligible = [item[0] for item in coverage]
    controls = [item[2] for item in coverage]
    print("## Data and clock audit")
    print("| Receipts | Price dates (ET sessions) | Weekly formations | Eligible mean/min/max | Control mean | Entry |")
    print("| ---: | --- | ---: | --- | ---: | --- |")
    print(
        f"| {panel['accepted']}/{len(panel['symbols'])} | {panel['dates'][0]} to {panel['dates'][-1]} | "
        f"{len(formations)} | {statistics.fmean(eligible):.0f}/{min(eligible)}/{max(eligible)} | "
        f"{statistics.fmean(controls):.0f} | next-session adjusted open |"
    )

    print("\n## Eight-cell primary decision table")
    print(f"Post-2019 p uses {draws:,} quarter-block resamples; q corrects these eight rows together.")
    print("| Family | Signal | H | N | Full tail excess [95% post-2019 CI] | Dev | Val | Recent | p / q | IC | Hit | Turnover | Verdict |")
    print("| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |")
    for item in primary:
        full = item["full"]
        family = "M" if item["signal"] in MOMENTUM_SIGNALS else "R"
        interval = f"{pct(full['tail_excess'])} [{pct(item['ci_low'])}, {pct(item['ci_high'])}]"
        print(
            f"| {family} | `{item['signal']}` | {item['horizon']} | {full['formations']} | {interval} | "
            f"{pct(item['development']['tail_excess'])} | {pct(item['validation']['tail_excess'])} | "
            f"{pct(item['recent']['tail_excess'])} | {pnumber(item['p'])} / {pnumber(item['q'])} | "
            f"{number(full['ic'])} | {pct(full['hit'], 1)} | {pct(full['turnover'], 1)} | "
            f"{'diagnostic candidate' if item['candidate'] else 'not a candidate'} |"
        )

    print("\n## Tail-excess path (Top 100)")
    print("| Signal | 5d | 10d | 21d | 63d | 126d |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for signal in SIGNALS:
        cells = []
        for horizon in (5, 10, 21, 63, 126):
            if ("top100", signal, horizon) not in rows:
                cells.append("NA")
            else:
                cells.append(pct(summarize(rows[("top100", signal, horizon)])["tail_excess"]))
        print(f"| `{signal}` | " + " | ".join(cells) + " |")

    print("\n## Pool and sector decomposition at each primary horizon")
    print("| Signal | Top 100 | Top 200 | Rank 201+ control | Top-100 sector-peer excess |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for signal in SIGNALS:
        horizon = PRIMARY_HORIZON[signal]
        summaries = {
            pool: summarize(rows[(pool, signal, horizon)])
            for pool in ("top100", "top200", "control201plus")
        }
        print(
            f"| `{signal}` | {pct(summaries['top100']['tail_excess'])} | "
            f"{pct(summaries['top200']['tail_excess'])} | {pct(summaries['control201plus']['tail_excess'])} | "
            f"{pct(summaries['top100']['sector_excess'])} |"
        )

    print("\n## Top-100 decile shape at each primary horizon")
    print("D1 is lowest signal score; D10 is the selected tail. Cells are excess versus the same-date Top-100 mean.")
    print("| Signal | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for signal in SIGNALS:
        horizon = PRIMARY_HORIZON[signal]
        cell_rows = rows[("top100", signal, horizon)]
        deciles = [mean_or_none(row["deciles"][index] for row in cell_rows) for index in range(10)]
        print(f"| `{signal}` | " + " | ".join(pct(value) for value in deciles) + " |")

    print("\n## Familiar-name sanity panels (not gates)")
    print("| Signal | H | MAG7 top-third excess / IC | Dynamic two-per-sector top-third excess / IC |")
    print("| --- | ---: | --- | --- |")
    for signal in ("classic_12_1", "multi_1_3_6_12", "reversal_5d", "sector_relative_reversal_5d"):
        horizon = PRIMARY_HORIZON[signal]
        mag = summarize(rows[("mag7", signal, horizon)])
        sector = summarize(rows[("sector_leaders", signal, horizon)])
        print(
            f"| `{signal}` | {horizon} | {pct(mag['tail_excess'])} / {number(mag['ic'])} | "
            f"{pct(sector['tail_excess'])} / {number(sector['ic'])} |"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database")
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    args = parser.parse_args()
    connection = connect(resolve_database_path(args.database), read_only=True)
    try:
        panel = load_panel(connection)
    finally:
        connection.close()
    rows, coverage, formations = run(panel)
    primary = summarize_results(rows, args.bootstrap_draws)
    print_results(panel, rows, coverage, formations, primary, args.bootstrap_draws)


if __name__ == "__main__":
    main()
