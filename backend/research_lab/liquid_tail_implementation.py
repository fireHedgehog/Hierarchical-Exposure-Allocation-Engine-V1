"""H-XSEC-S5-002: next-open implementation check for four liquid tail signals.

Read-only disposable research. Prints compact Markdown and never writes the DB.

Run:
    .venv/Scripts/python.exe -m backend.research_lab.liquid_tail_implementation
"""

from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict
from datetime import date

import numpy as np

from backend.database import connect, resolve_database_path
from backend.research_lab.liquid_leadership_and_reversal import (
    build_pools,
    finite,
    fold_for,
    load_panel,
    pool_scores,
    snapshot,
    weekly_formations,
)


SIGNALS = (
    "momentum_1m",
    "momentum_3m",
    "reversal_5d",
    "sector_relative_reversal_5d",
)
MOMENTUM_SIGNALS = frozenset(("momentum_1m", "momentum_3m"))
MOMENTUM_SLEEVES = 13
COST_BPS = (0, 5, 10, 25, 50)
ADV_PARTICIPATION = 0.01


def equal_weights(symbols):
    return {symbol: 1.0 / len(symbols) for symbol in symbols} if symbols else {}


def combine_sleeves(sleeves):
    combined = defaultdict(float)
    for sleeve in sleeves:
        for symbol, weight in sleeve.items():
            combined[symbol] += weight / len(sleeves)
    total = sum(combined.values())
    return {symbol: weight / total for symbol, weight in combined.items()} if total else {}


def one_way_turnover(current, prior):
    symbols = set(current) | set(prior)
    return 0.5 * sum(abs(current.get(symbol, 0.0) - prior.get(symbol, 0.0)) for symbol in symbols)


def open_to_open_return(weights, arrays, start, end):
    if not weights:
        return None
    returns = []
    for symbol, weight in weights.items():
        opens = arrays[symbol]["open"]
        if not finite(opens[start]) or not finite(opens[end]) or opens[start] <= 0:
            return None
        returns.append(weight * float(opens[end] / opens[start] - 1.0))
    return sum(returns)


def capacity_at_one_percent(weights, panel, formation):
    capacities = []
    for symbol, weight in weights.items():
        if weight <= 0:
            continue
        arrays = panel["arrays"][symbol]
        dollar_volume = (
            arrays["raw_close"][formation - 20 : formation + 1]
            * arrays["volume"][formation - 20 : formation + 1]
        )
        if len(dollar_volume) != 21 or not np.all(np.isfinite(dollar_volume)) or np.any(dollar_volume <= 0):
            return None
        capacities.append(float(np.median(dollar_volume)) * ADV_PARTICIPATION / weight)
    return min(capacities) if capacities else None


def selections(panel, formations):
    records = []
    for position, formation in enumerate(formations):
        snapshots = snapshot(panel, formation)
        top100 = build_pools(snapshots)["top100"]
        scores = pool_scores(top100, snapshots)
        selected = {}
        for signal in SIGNALS:
            usable = [symbol for symbol in top100 if symbol in scores[signal]]
            count = max(1, len(usable) // 10)
            winners = sorted(usable, key=lambda symbol: (-scores[signal][symbol], symbol))[:count]
            selected[signal] = equal_weights(winners)
        records.append(
            {
                "formation": formation,
                "snapshots": snapshots,
                "top100": equal_weights(top100),
                "selected": selected,
            }
        )
        if position % 100 == 0:
            print(f"progress: {position + 1}/{len(formations)} formations", flush=True)
    return records


def run_signal(panel, formations, records, signal):
    rows = []
    prior = {}
    first = MOMENTUM_SLEEVES - 1 if signal in MOMENTUM_SIGNALS else 0
    for position in range(first, len(formations) - 1):
        formation = formations[position]
        next_formation = formations[position + 1]
        start, end = formation + 1, next_formation + 1
        if end >= len(panel["dates"]):
            continue
        if signal in MOMENTUM_SIGNALS:
            sleeves = [
                records[index]["selected"][signal]
                for index in range(position - MOMENTUM_SLEEVES + 1, position + 1)
            ]
            if any(not sleeve for sleeve in sleeves):
                continue
            target = combine_sleeves(sleeves)
        else:
            target = records[position]["selected"][signal]
        benchmark = records[position]["top100"]
        strategy_return = open_to_open_return(target, panel["arrays"], start, end)
        benchmark_return = open_to_open_return(benchmark, panel["arrays"], start, end)
        if not finite(strategy_return) or not finite(benchmark_return):
            continue
        turnover = one_way_turnover(target, prior) if prior else 1.0
        start_date, end_date = panel["dates"][start], panel["dates"][end]
        rows.append(
            {
                "start": start_date,
                "end": end_date,
                "start_fold": fold_for(start_date),
                "end_fold": fold_for(end_date),
                "gross": strategy_return,
                "benchmark": benchmark_return,
                "turnover": turnover,
                "names": len(target),
                "capacity": capacity_at_one_percent(target, panel, formation),
            }
        )
        prior = target
    return rows


def fold_rows(rows, fold):
    if fold == "full":
        return rows
    return [row for row in rows if row["start_fold"] == fold and row["end_fold"] == fold]


def performance(returns, start, end):
    clean = np.asarray(returns, dtype=float)
    if len(clean) == 0:
        return None
    wealth = np.cumprod(1.0 + clean)
    elapsed_days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    annual_return = float(wealth[-1] ** (365.25 / elapsed_days) - 1.0) if elapsed_days > 0 else None
    annual_vol = float(np.std(clean, ddof=1) * math.sqrt(52.1775)) if len(clean) > 1 else None
    sharpe = None if not annual_vol or annual_vol <= 0 else float(np.mean(clean) * 52.1775 / annual_vol)
    peaks = np.maximum.accumulate(np.insert(wealth, 0, 1.0))[1:]
    max_drawdown = float(np.min(wealth / peaks - 1.0))
    return annual_return, annual_vol, sharpe, max_drawdown


def percentile(values, q):
    clean = [float(value) for value in values if finite(value)]
    return None if not clean else float(np.percentile(clean, q))


def summarize(rows, cost_bps=0):
    if not rows:
        return None
    net = [row["gross"] - cost_bps / 10_000.0 * row["turnover"] for row in rows]
    start, end = rows[0]["start"], rows[-1]["end"]
    return {
        "strategy": performance(net, start, end),
        "benchmark": performance([row["benchmark"] for row in rows], start, end),
        "turnover": statistics.fmean(row["turnover"] for row in rows),
        "names": statistics.fmean(row["names"] for row in rows),
        "capacity_p10": percentile([row["capacity"] for row in rows], 10),
        "capacity_median": percentile([row["capacity"] for row in rows], 50),
        "periods": len(rows),
    }


def excess(summary):
    if summary is None or summary["strategy"] is None or summary["benchmark"] is None:
        return None
    return summary["strategy"][0] - summary["benchmark"][0]


def break_even_bps(rows):
    gross = excess(summarize(rows, 0))
    if not finite(gross) or gross <= 0:
        return 0.0
    if excess(summarize(rows, 1_000)) > 0:
        return None
    low, high = 0.0, 1_000.0
    for _ in range(40):
        middle = (low + high) / 2.0
        if excess(summarize(rows, middle)) > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def pct(value, digits=2):
    return "NA" if not finite(value) else f"{100 * float(value):+.{digits}f}%"


def number(value, digits=2):
    return "NA" if not finite(value) else f"{float(value):.{digits}f}"


def money(value):
    return "NA" if not finite(value) else f"${float(value) / 1_000_000:.1f}m"


def bps(value):
    return ">1000" if value is None else f"{float(value):.1f}"


def report(panel, formations, rows_by_signal):
    print("\n## Data and implementation audit")
    print("| Receipts | SPY session spine | Parent formations | Primary pool | Fill | Winner / reversal translation |")
    print("| ---: | ---: | ---: | --- | --- | --- |")
    print(
        f"| {panel['accepted']}/{len(panel['symbols'])} | {len(panel['dates']):,} | {len(formations):,} | "
        "dynamic ADV21 Top-100 | next adjusted open | 13 weekly sleeves / current weekly sleeve |"
    )

    summaries = {}
    print("\n## Frozen gate matrix")
    print("| Signal | Weeks | Dev gross excess | Val gross excess | Recent gross excess | Full gross excess | Full net excess @10bp | Recent net excess @10bp | Turnover/week | Break-even one-way cost | Gate |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for signal in SIGNALS:
        rows = rows_by_signal[signal]
        summaries[signal] = {
            fold: {cost: summarize(fold_rows(rows, fold), cost) for cost in COST_BPS}
            for fold in ("full", "development", "validation", "recent")
        }
        gross_by_fold = {
            fold: excess(summaries[signal][fold][0])
            for fold in ("development", "validation", "recent", "full")
        }
        full_net10 = excess(summaries[signal]["full"][10])
        recent_net10 = excess(summaries[signal]["recent"][10])
        gate = (
            all(finite(gross_by_fold[fold]) and gross_by_fold[fold] > 0 for fold in ("development", "validation", "recent"))
            and finite(full_net10) and full_net10 > 0
            and finite(recent_net10) and recent_net10 > 0
        )
        full = summaries[signal]["full"][0]
        print(
            f"| `{signal}` | {full['periods']} | {pct(gross_by_fold['development'])} | "
            f"{pct(gross_by_fold['validation'])} | {pct(gross_by_fold['recent'])} | "
            f"{pct(gross_by_fold['full'])} | {pct(full_net10)} | {pct(recent_net10)} | "
            f"{pct(full['turnover'], 1)} | {bps(break_even_bps(rows))} bp | {'Pass' if gate else 'Fail'} |"
        )

    print("\n## Explicit assumed-cost surface")
    print("| Signal | Fold | 0 bp | 5 bp | 10 bp | 25 bp | 50 bp |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for signal in SIGNALS:
        for fold in ("full", "recent"):
            values = [pct(excess(summaries[signal][fold][cost])) for cost in COST_BPS]
            print(f"| `{signal}` | {fold} | " + " | ".join(values) + " |")

    print("\n## Full-sample portfolio diagnostics at 10 bp")
    print("| Signal | Net ann. | Top-100 ann. | Sharpe | Max DD / Top-100 Max DD | Avg names | Capacity p10 / median |")
    print("| --- | ---: | ---: | ---: | --- | ---: | --- |")
    for signal in SIGNALS:
        summary = summaries[signal]["full"][10]
        strategy, benchmark = summary["strategy"], summary["benchmark"]
        print(
            f"| `{signal}` | {pct(strategy[0])} | {pct(benchmark[0])} | "
            f"{number(strategy[2])} | {pct(strategy[3])} / {pct(benchmark[3])} | {summary['names']:.1f} | "
            f"{money(summary['capacity_p10'])} / {money(summary['capacity_median'])} |"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=None)
    args = parser.parse_args()
    connection = connect(resolve_database_path(args.database), read_only=True)
    try:
        panel = load_panel(connection)
    finally:
        connection.close()
    formations = weekly_formations(panel["dates"])
    records = selections(panel, formations)
    rows_by_signal = {
        signal: run_signal(panel, formations, records, signal)
        for signal in SIGNALS
    }
    report(panel, formations, rows_by_signal)


if __name__ == "__main__":
    main()
