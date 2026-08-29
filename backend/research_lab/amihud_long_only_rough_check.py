"""H-XSEC-S5-001: rough long-only check of the Amihud discovery candidate.

Read-only disposable research. Prints compact Markdown and never writes the DB.

Run:
    .venv/Scripts/python.exe -m backend.research_lab.amihud_long_only_rough_check
"""

from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict
from datetime import date

import numpy as np

from backend.database import connect, resolve_database_path
from backend.research_lab.price_volume_factor_screen import (
    LIBRARY_DATASET_ID,
    MIN_PRICE,
    aligned_returns,
    finite,
    load_panel,
)


ADV_FLOORS = (1_000_000.0, 5_000_000.0, 10_000_000.0)
SLEEVE_MONTHS = (2, 3)
COST_BPS = (0, 5, 10, 25, 50)
TOP_FRACTION = 0.20
ADV_PARTICIPATION = 0.01
HOLDOUT_START = date(2023, 7, 1)
MIN_SECTOR_NAMES = 5


def month_ends(dates):
    last_by_month = {}
    for index, day in enumerate(dates):
        parsed = date.fromisoformat(day)
        last_by_month[(parsed.year, parsed.month)] = index
    return [index for index in last_by_month.values() if index >= 252]


def amihud_snapshot(price, index):
    close = price["close"]
    raw_close = price["raw_close"]
    volume = price["volume"]
    if not finite(close[index]) or not finite(raw_close[index]) or raw_close[index] < MIN_PRICE:
        return None

    dollar_volume = raw_close[index - 20 : index + 1] * volume[index - 20 : index + 1]
    usable_volume = dollar_volume[np.isfinite(dollar_volume) & (dollar_volume > 0)]
    if len(usable_volume) < 15:
        return None
    median_adv = float(np.median(usable_volume))

    stock_returns = aligned_returns(close, index - 21, index)[-20:]
    aligned_volume = raw_close[index - 19 : index + 1] * volume[index - 19 : index + 1]
    mask = np.isfinite(stock_returns) & np.isfinite(aligned_volume) & (aligned_volume > 0)
    if int(np.sum(mask)) < 15:
        return None
    amihud = float(np.mean(np.abs(stock_returns[mask]) / aligned_volume[mask]))
    return amihud, median_adv


def sector_weights(records, select_top=False):
    by_sector = defaultdict(list)
    for symbol, sector, amihud, adv in records:
        by_sector[sector].append((symbol, amihud, adv))
    by_sector = {sector: rows for sector, rows in by_sector.items() if len(rows) >= MIN_SECTOR_NAMES}
    if not by_sector:
        return {}, {}

    weights = {}
    adv_by_symbol = {}
    sector_weight = 1.0 / len(by_sector)
    for rows in by_sector.values():
        chosen = rows
        if select_top:
            count = max(1, math.ceil(TOP_FRACTION * len(rows)))
            chosen = sorted(rows, key=lambda row: row[1], reverse=True)[:count]
        name_weight = sector_weight / len(chosen)
        for symbol, _, adv in chosen:
            weights[symbol] = name_weight
            adv_by_symbol[symbol] = adv
    return weights, adv_by_symbol


def combine_sleeves(sleeves):
    combined = defaultdict(float)
    for sleeve in sleeves:
        for symbol, weight in sleeve.items():
            combined[symbol] += weight / len(sleeves)
    total = sum(combined.values())
    return {symbol: weight / total for symbol, weight in combined.items()} if total else {}


def portfolio_return(weights, arrays, start, end):
    usable = []
    for symbol, weight in weights.items():
        values = arrays[symbol]["close"]
        if finite(values[start]) and finite(values[end]) and values[start] > 0:
            usable.append((weight, float(values[end] / values[start] - 1.0)))
    total = sum(weight for weight, _ in usable)
    return None if total <= 0 else sum(weight * value for weight, value in usable) / total


def one_way_turnover(current, prior):
    symbols = set(current) | set(prior)
    return 0.5 * sum(abs(current.get(symbol, 0.0) - prior.get(symbol, 0.0)) for symbol in symbols)


def capacity_at_one_percent(weights, arrays, index):
    capacities = []
    for symbol, weight in weights.items():
        if weight <= 0:
            continue
        price = arrays[symbol]
        dollar_volume = price["raw_close"][index - 20 : index + 1] * price["volume"][index - 20 : index + 1]
        usable = dollar_volume[np.isfinite(dollar_volume) & (dollar_volume > 0)]
        if len(usable) >= 15:
            capacities.append(float(np.median(usable)) * ADV_PARTICIPATION / weight)
    return min(capacities) if capacities else None


def performance(values):
    clean = np.asarray([value for value in values if finite(value)], dtype=float)
    if len(clean) == 0:
        return None
    wealth = np.cumprod(1.0 + clean)
    annual_return = float(wealth[-1] ** (12.0 / len(clean)) - 1.0)
    annual_vol = float(np.std(clean, ddof=1) * math.sqrt(12)) if len(clean) > 1 else None
    sharpe = None if not annual_vol or annual_vol <= 0 else float(np.mean(clean) * 12 / annual_vol)
    peak = np.maximum.accumulate(np.insert(wealth, 0, 1.0))[1:]
    max_drawdown = float(np.min(wealth / peak - 1.0))
    return annual_return, annual_vol, sharpe, max_drawdown


def percentile(values, q):
    clean = [value for value in values if finite(value)]
    return None if not clean else float(np.percentile(clean, q))


def pct(value, digits=2):
    return "NA" if not finite(value) else f"{100 * float(value):+.{digits}f}%"


def number(value, digits=2):
    return "NA" if not finite(value) else f"{float(value):.{digits}f}"


def money(value):
    return "NA" if not finite(value) else f"${float(value) / 1_000_000:.1f}m"


def build_snapshots(panel, formations):
    snapshots = []
    for position, index in enumerate(formations):
        raw = []
        for symbol in panel["sector_by_symbol"]:
            result = amihud_snapshot(panel["arrays"][symbol], index)
            if result is not None:
                raw.append((symbol, panel["sector_by_symbol"][symbol], *result))
        floors = {}
        for floor in ADV_FLOORS:
            eligible = [row for row in raw if row[3] >= floor]
            selected, _ = sector_weights(eligible, select_top=True)
            benchmark, _ = sector_weights(eligible, select_top=False)
            floors[floor] = (selected, benchmark, len(eligible))
        snapshots.append(floors)
        if position % 24 == 0:
            print(f"progress: {position + 1}/{len(formations)} formations", flush=True)
    return snapshots


def run_configuration(panel, formations, snapshots, floor, sleeve_months):
    rows = []
    prior = {}
    for position in range(sleeve_months - 1, len(formations) - 1):
        sleeves = [snapshots[i][floor][0] for i in range(position - sleeve_months + 1, position + 1)]
        if any(not sleeve for sleeve in sleeves):
            continue
        target = combine_sleeves(sleeves)
        benchmark = snapshots[position][floor][1]
        # The month-end close is an input to the signal. Enter and rebalance at
        # the following session's adjusted close so the signal never receives
        # an impossible same-close fill.
        start, end = formations[position] + 1, formations[position + 1] + 1
        if end >= len(panel["dates"]):
            continue
        gross = portfolio_return(target, panel["arrays"], start, end)
        sector_equal = portfolio_return(benchmark, panel["arrays"], start, end)
        spy = float(panel["spy"][end] / panel["spy"][start] - 1.0)
        if not all(finite(value) for value in (gross, sector_equal, spy)):
            continue
        turnover = one_way_turnover(target, prior) if prior else 1.0
        rows.append(
            {
                "end": date.fromisoformat(panel["dates"][end]),
                "gross": gross,
                "sector_equal": sector_equal,
                "spy": spy,
                "turnover": turnover,
                "capacity": capacity_at_one_percent(target, panel["arrays"], start),
                "names": len(target),
                "eligible": snapshots[position][floor][2],
            }
        )
        prior = target
    return rows


def summarize(rows, cost_bps=0):
    net = [row["gross"] - cost_bps / 10_000 * row["turnover"] for row in rows]
    return {
        "portfolio": performance(net),
        "sector": performance([row["sector_equal"] for row in rows]),
        "spy": performance([row["spy"] for row in rows]),
        "turnover": statistics.fmean(row["turnover"] for row in rows),
        "capacity_p10": percentile([row["capacity"] for row in rows], 10),
        "capacity_median": percentile([row["capacity"] for row in rows], 50),
        "names": statistics.fmean(row["names"] for row in rows),
        "eligible": statistics.fmean(row["eligible"] for row in rows),
        "periods": len(rows),
    }


def fold(rows, name):
    if name == "full":
        return rows
    return [row for row in rows if row["end"] >= HOLDOUT_START]


def report(panel, formations, configurations):
    print("\n## Data audit")
    print("| Dataset | Receipts | Price dates | Formations | Range |")
    print("| --- | ---: | ---: | ---: | --- |")
    print(
        f"| `{LIBRARY_DATASET_ID}` | {panel['accepted']} | {len(panel['dates']):,} | "
        f"{len(formations)} | {panel['dates'][formations[0]]} to {panel['dates'][formations[-1]]} |"
    )

    print("\n## Gross implementation matrix")
    print("| ADV floor | Sleeves | Fold | Periods | Names | Gross ann. | Sector-EW ann. | Excess | SPY ann. | Excess | Sharpe | Max DD | One-way turnover | 1% ADV capacity p10 / median |")
    print("| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for (floor_value, sleeves), rows in configurations.items():
        for fold_name in ("full", "holdout"):
            summary = summarize(fold(rows, fold_name))
            portfolio, sector, spy = summary["portfolio"], summary["sector"], summary["spy"]
            print(
                f"| ${floor_value / 1_000_000:.0f}m | {sleeves} | {fold_name} | {summary['periods']} | "
                f"{summary['names']:.1f} | {pct(portfolio[0])} | {pct(sector[0])} | "
                f"{pct(portfolio[0] - sector[0])} | {pct(spy[0])} | {pct(portfolio[0] - spy[0])} | "
                f"{number(portfolio[2])} | {pct(portfolio[3])} | {pct(summary['turnover'])} | "
                f"{money(summary['capacity_p10'])} / {money(summary['capacity_median'])} |"
            )

    print("\n## Explicit cost scenarios: primary $1m ADV floor")
    print("| Sleeves | Fold | Cost | Net ann. | Net excess vs gross Sector-EW | Status |")
    print("| ---: | --- | ---: | ---: | ---: | --- |")
    for sleeves in SLEEVE_MONTHS:
        rows = configurations[(ADV_FLOORS[0], sleeves)]
        for fold_name in ("full", "holdout"):
            selected = fold(rows, fold_name)
            for cost in COST_BPS:
                summary = summarize(selected, cost)
                excess = summary["portfolio"][0] - summary["sector"][0]
                status = "Pass" if excess > 0 else "Fail"
                print(
                    f"| {sleeves} | {fold_name} | {cost} bps | {pct(summary['portfolio'][0])} | "
                    f"{pct(excess)} | {status} |"
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
    formations = month_ends(panel["dates"])
    snapshots = build_snapshots(panel, formations)
    configurations = {
        (floor, sleeves): run_configuration(panel, formations, snapshots, floor, sleeves)
        for floor in ADV_FLOORS
        for sleeves in SLEEVE_MONTHS
    }
    report(panel, formations, configurations)


if __name__ == "__main__":
    main()
