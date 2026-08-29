"""H-XSEC-S2-002: one monthly cross-sectional price/volume factor screen.

Read-only disposable research. Prints compact Markdown and never writes the DB.

Run:
    .venv/Scripts/python.exe -m backend.research_lab.price_volume_factor_screen
"""

from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict
from datetime import date

import numpy as np
from scipy import stats

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg
from backend.universe.library_fetch import (
    DUAL_BASIS_CONTRACT_REVISION,
    LIBRARY_CONTRACT_THROUGH,
    LIBRARY_DATASET_ID,
    LIBRARY_UNIVERSE_STAGE,
)


ANCHOR_DATASET_ID = "real-macro-0f184797-d738-4ecd-a615-83b0020c5753"
SPY = "SPY"
SECTORS = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")
HORIZONS = (5, 10, 21, 42, 63)
FACTORS = (
    "reversal_5d",
    "momentum_1m",
    "momentum_3_1",
    "momentum_6_1",
    "momentum_12_1",
    "high_52w",
    "trend_consistency_3m",
    "vol_scaled_momentum_6_1",
    "residual_momentum_6_1",
    "low_total_vol_3m",
    "low_beta_1y",
    "low_idio_vol_1y",
    "max_effect_1m",
    "low_dollar_volume_1m",
    "amihud_illiquidity_1m",
)
MIN_PRICE = 2.0
MIN_MEDIAN_DOLLAR_VOLUME = 1_000_000.0
MIN_BROAD_NAMES = 30
MIN_SECTOR_NAMES = 8


def finite(value) -> bool:
    return value is not None and math.isfinite(float(value))


def mean(values):
    clean = [float(value) for value in values if finite(value)]
    return statistics.fmean(clean) if clean else None


def number(value, digits=3):
    return "NA" if not finite(value) else f"{float(value):+.{digits}f}"


def pnumber(value):
    if not finite(value):
        return "NA"
    return "<.0001" if float(value) < 0.0001 else f"{float(value):.4f}"


def pct(value, digits=2):
    return "NA" if not finite(value) else f"{100 * float(value):+.{digits}f}%"


def trailing_return(values, start, end):
    first, last = values[start], values[end]
    if not finite(first) or not finite(last) or first <= 0:
        return None
    return float(last / first - 1.0)


def aligned_returns(values, start, end):
    window = values[start : end + 1]
    prior, current = window[:-1], window[1:]
    mask = np.isfinite(prior) & np.isfinite(current) & (prior > 0)
    result = np.full(len(prior), np.nan)
    result[mask] = current[mask] / prior[mask] - 1.0
    return result


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
    sector_by_symbol = {}
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
        "SELECT security_id FROM securities WHERE primary_symbol = ?", (SPY,)
    ).fetchone()
    if spy_security is None:
        raise RuntimeError("SPY security identity is missing")
    spy_rows = connection.execute(
        """SELECT time, COALESCE(adjusted_close, close) AS close
           FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ?
           AND COALESCE(adjusted_close, close) IS NOT NULL ORDER BY time""",
        (ANCHOR_DATASET_ID, spy_security["security_id"]),
    ).fetchall()
    dates = [row["time"] for row in spy_rows]
    spy = np.array([row["close"] for row in spy_rows], dtype=float)
    date_index = {day: index for index, day in enumerate(dates)}
    arrays = {
        symbol: {
            "close": np.full(len(dates), np.nan),
            "high": np.full(len(dates), np.nan),
            "raw_close": np.full(len(dates), np.nan),
            "volume": np.full(len(dates), np.nan),
        }
        for symbol in symbols
    }

    for row in connection.execute(
        """SELECT s.primary_symbol AS symbol, b.time, b.adjusted_close,
                  b.adjusted_high, b.raw_close, b.volume
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
        target["high"][index] = row["adjusted_high"]
        target["raw_close"][index] = row["raw_close"]
        target["volume"][index] = row["volume"]

    return {
        "dates": dates,
        "spy": spy,
        "symbols": symbols,
        "sector_by_symbol": sector_by_symbol,
        "arrays": arrays,
        "accepted": coverage["accepted"],
    }


def formation_indices(dates):
    last_by_month = {}
    for index, day in enumerate(dates):
        parsed = date.fromisoformat(day)
        last_by_month[(parsed.year, parsed.month)] = index
    return [
        index
        for index in last_by_month.values()
        if index >= 252 and index + max(HORIZONS) < len(dates)
    ]


def factor_snapshot(price, spy, index):
    close = price["close"]
    high = price["high"]
    raw_close = price["raw_close"]
    volume = price["volume"]
    if not finite(close[index]) or not finite(raw_close[index]) or raw_close[index] < MIN_PRICE:
        return None

    recent_dollar_volume = raw_close[index - 20 : index + 1] * volume[index - 20 : index + 1]
    recent_dollar_volume = recent_dollar_volume[np.isfinite(recent_dollar_volume) & (recent_dollar_volume > 0)]
    median_dollar_volume = float(np.median(recent_dollar_volume)) if len(recent_dollar_volume) >= 15 else None
    if median_dollar_volume is None or median_dollar_volume < MIN_MEDIAN_DOLLAR_VOLUME:
        return None

    stock_252 = aligned_returns(close, index - 252, index)
    spy_252 = aligned_returns(spy, index - 252, index)
    beta_mask = np.isfinite(stock_252) & np.isfinite(spy_252)
    beta = None
    idio_vol = None
    if int(np.sum(beta_mask)) >= 200:
        x = spy_252[beta_mask]
        y = stock_252[beta_mask]
        variance = float(np.var(x, ddof=1))
        if variance > 1e-12:
            beta = float(np.cov(y, x, ddof=1)[0, 1] / variance)
            idio_vol = float(np.std(y - beta * x, ddof=1))

    stock_63 = aligned_returns(close, index - 63, index)
    stock_21 = aligned_returns(close, index - 21, index)
    usable_63 = stock_63[np.isfinite(stock_63)]
    usable_21 = stock_21[np.isfinite(stock_21)]

    momentum_6_1 = trailing_return(close, index - 126, index - 21)
    pre_momentum_returns = aligned_returns(close, index - 126, index - 21)
    pre_momentum_returns = pre_momentum_returns[np.isfinite(pre_momentum_returns)]
    pre_momentum_vol = (
        float(np.std(pre_momentum_returns, ddof=1)) if len(pre_momentum_returns) >= 80 else None
    )

    residual_momentum = None
    if beta is not None:
        stock_resid = aligned_returns(close, index - 126, index - 21)
        spy_resid = aligned_returns(spy, index - 126, index - 21)
        mask = np.isfinite(stock_resid) & np.isfinite(spy_resid)
        if int(np.sum(mask)) >= 80:
            residual_momentum = float(np.sum(stock_resid[mask] - beta * spy_resid[mask]))

    amihud = None
    if len(usable_21) >= 15:
        daily_dollar_volume = raw_close[index - 19 : index + 1] * volume[index - 19 : index + 1]
        aligned_abs_return = np.abs(stock_21[-20:])
        mask = np.isfinite(daily_dollar_volume) & (daily_dollar_volume > 0) & np.isfinite(aligned_abs_return)
        if int(np.sum(mask)) >= 15:
            amihud = float(np.mean(aligned_abs_return[mask] / daily_dollar_volume[mask]))

    high_window = high[index - 251 : index + 1]
    high_window = high_window[np.isfinite(high_window)]
    maximum_high = float(np.max(high_window)) if len(high_window) >= 200 else None

    return {
        "reversal_5d": None
        if (value := trailing_return(close, index - 5, index)) is None
        else -value,
        "momentum_1m": trailing_return(close, index - 21, index),
        "momentum_3_1": trailing_return(close, index - 63, index - 21),
        "momentum_6_1": momentum_6_1,
        "momentum_12_1": trailing_return(close, index - 252, index - 21),
        "high_52w": None if maximum_high is None or maximum_high <= 0 else float(close[index] / maximum_high),
        "trend_consistency_3m": None if len(usable_63) < 50 else float(np.mean(usable_63 > 0)),
        "vol_scaled_momentum_6_1": None
        if momentum_6_1 is None or pre_momentum_vol is None or pre_momentum_vol <= 1e-12
        else momentum_6_1 / pre_momentum_vol,
        "residual_momentum_6_1": residual_momentum,
        "low_total_vol_3m": None
        if len(usable_63) < 50
        else -float(np.std(usable_63, ddof=1)),
        "low_beta_1y": None if beta is None else -beta,
        "low_idio_vol_1y": None if idio_vol is None else -idio_vol,
        "max_effect_1m": None if len(usable_21) < 15 else -float(np.max(usable_21)),
        "low_dollar_volume_1m": -math.log(median_dollar_volume),
        "amihud_illiquidity_1m": amihud,
    }


def broad_cell(observations):
    if len(observations) < MIN_BROAD_NAMES:
        return None
    x = np.array([row[1] for row in observations], dtype=float)
    y = np.array([row[2] for row in observations], dtype=float)
    result = stats.spearmanr(x, y)
    if not finite(result.statistic):
        return None
    order = np.argsort(x)
    bucket = max(1, len(order) // 5)
    spread = float(np.mean(y[order[-bucket:]]) - np.mean(y[order[:bucket]]))
    return float(result.statistic), spread, len(observations)


def sector_neutral_cell(observations):
    grouped = defaultdict(list)
    for symbol, factor, outcome, sector in observations:
        if sector:
            grouped[sector].append((symbol, factor, outcome))
    factor_ranks, outcome_ranks, spreads, usable = [], [], [], 0
    for rows in grouped.values():
        if len(rows) < MIN_SECTOR_NAMES:
            continue
        x = np.array([row[1] for row in rows], dtype=float)
        y = np.array([row[2] for row in rows], dtype=float)
        factor_ranks.extend(stats.rankdata(x, method="average") / (len(rows) + 1.0))
        outcome_ranks.extend(stats.rankdata(y, method="average") / (len(rows) + 1.0))
        order = np.argsort(x)
        bucket = max(1, len(order) // 5)
        spreads.append(float(np.mean(y[order[-bucket:]]) - np.mean(y[order[:bucket]])))
        usable += len(rows)
    if usable < MIN_BROAD_NAMES or not spreads:
        return None
    result = stats.spearmanr(factor_ranks, outcome_ranks)
    if not finite(result.statistic):
        return None
    return float(result.statistic), statistics.fmean(spreads), usable


def fold_for(day_string):
    day = date.fromisoformat(day_string)
    if day <= date(2018, 12, 31):
        return "development"
    if day <= date(2023, 6, 30):
        return "validation"
    return "holdout"


def hac_mean_p(values, lag):
    x = np.asarray(values, dtype=float)
    if len(x) < 3:
        return None
    residual = x - np.mean(x)
    long_run_variance = float(np.dot(residual, residual) / len(x))
    for distance in range(1, min(lag, len(x) - 1) + 1):
        covariance = float(np.dot(residual[distance:], residual[:-distance]) / len(x))
        long_run_variance += 2.0 * (1.0 - distance / (lag + 1.0)) * covariance
    standard_error = math.sqrt(max(long_run_variance, 0.0) / len(x))
    if standard_error <= 1e-12:
        return None
    statistic = float(np.mean(x) / standard_error)
    return float(2.0 * stats.t.sf(abs(statistic), df=len(x) - 1))


def summarize(rows, horizon, fold=None):
    selected = rows if fold is None else [row for row in rows if row["fold"] == fold]
    if not selected:
        return {"months": 0, "ic": None, "p": None, "spread": None, "hit": None, "names": None}
    values = [row["ic"] for row in selected]
    return {
        "months": len(selected),
        "ic": statistics.fmean(values),
        "p": hac_mean_p(values, max(0, math.ceil(horizon / 21) - 1)),
        "spread": statistics.fmean(row["spread"] for row in selected),
        "hit": statistics.fmean(value > 0 for value in values),
        "names": statistics.fmean(row["names"] for row in selected),
    }


def run(panel):
    rows = {
        view: {factor: {horizon: [] for horizon in HORIZONS} for factor in FACTORS}
        for view in ("broad", "sector-neutral")
    }
    formations = formation_indices(panel["dates"])
    for formation in formations:
        snapshots = {}
        for symbol in panel["symbols"]:
            snapshot = factor_snapshot(panel["arrays"][symbol], panel["spy"], formation)
            if snapshot:
                snapshots[symbol] = snapshot
        for horizon in HORIZONS:
            outcome_index = formation + horizon
            outcome_date = panel["dates"][outcome_index]
            outcomes = {}
            for symbol in snapshots:
                close = panel["arrays"][symbol]["close"]
                outcome = trailing_return(close, formation, outcome_index)
                if outcome is not None:
                    outcomes[symbol] = outcome
            for factor in FACTORS:
                observations = [
                    (symbol, snapshots[symbol][factor], outcomes[symbol])
                    for symbol in snapshots
                    if symbol in outcomes and finite(snapshots[symbol].get(factor))
                ]
                broad = broad_cell(observations)
                if broad:
                    rows["broad"][factor][horizon].append(
                        {
                            "date": panel["dates"][formation],
                            "outcome_date": outcome_date,
                            "fold": fold_for(outcome_date),
                            "ic": broad[0],
                            "spread": broad[1],
                            "names": broad[2],
                        }
                    )
                neutral_observations = [
                    (*row, panel["sector_by_symbol"].get(row[0])) for row in observations
                ]
                neutral = sector_neutral_cell(neutral_observations)
                if neutral:
                    rows["sector-neutral"][factor][horizon].append(
                        {
                            "date": panel["dates"][formation],
                            "outcome_date": outcome_date,
                            "fold": fold_for(outcome_date),
                            "ic": neutral[0],
                            "spread": neutral[1],
                            "names": neutral[2],
                        }
                    )
    return rows


def summarize_all(rows):
    summaries = {
        view: {
            factor: {
                horizon: {
                    "full": summarize(rows[view][factor][horizon], horizon),
                    "development": summarize(rows[view][factor][horizon], horizon, "development"),
                    "validation": summarize(rows[view][factor][horizon], horizon, "validation"),
                    "holdout": summarize(rows[view][factor][horizon], horizon, "holdout"),
                }
                for horizon in HORIZONS
            }
            for factor in FACTORS
        }
        for view in rows
    }
    cells = []
    for view in summaries:
        for factor in FACTORS:
            for horizon in HORIZONS:
                full = summaries[view][factor][horizon]["full"]
                if finite(full["p"]):
                    cells.append((view, factor, horizon, full["p"]))
    adjusted, _ = benjamini_hochberg([cell[3] for cell in cells])
    for cell, q_value in zip(cells, adjusted):
        view, factor, horizon, _ = cell
        summaries[view][factor][horizon]["full"]["q"] = q_value
    return summaries


def cell_text(summary):
    return (
        f"{number(summary['ic'])} / {pnumber(summary['p'])} / "
        f"{pnumber(summary.get('q'))} / {pct(summary['spread'])}"
    )


def stable_candidates(summaries):
    candidates = []
    for view in summaries:
        for factor in FACTORS:
            for horizon in HORIZONS:
                item = summaries[view][factor][horizon]
                full = item["full"]
                if not finite(full.get("q")) or full["q"] > 0.05 or not finite(full["ic"]):
                    continue
                sign = 1 if full["ic"] > 0 else -1
                validation, holdout = item["validation"], item["holdout"]
                stable = (
                    finite(validation["ic"])
                    and finite(holdout["ic"])
                    and validation["ic"] * sign > 0
                    and holdout["ic"] * sign > 0
                    and validation["spread"] * sign > 0
                    and holdout["spread"] * sign > 0
                )
                candidates.append((stable, abs(full["ic"]), view, factor, horizon, item))
    return sorted(candidates, key=lambda row: (not row[0], -row[1], row[2], row[3], row[4]))


def print_results(panel, rows, summaries):
    formations = formation_indices(panel["dates"])
    print("## Data audit")
    print("| Receipts | Price dates | Formation months | Broad names | Sector-neutral names | Screen |")
    print("| ---: | --- | ---: | ---: | ---: | --- |")
    print(
        f"| {panel['accepted']}/{len(panel['symbols'])} | {panel['dates'][0]} to {panel['dates'][-1]} ET | "
        f"{len(formations)} | {len(panel['symbols'])} | {len(panel['sector_by_symbol'])} | "
        f"raw close >= ${MIN_PRICE:.0f}; median 21d dollar volume >= ${MIN_MEDIAN_DOLLAR_VOLUME / 1_000_000:.0f}m |"
    )
    for view in ("broad", "sector-neutral"):
        print(f"\n## {view.title()} Rank IC surface")
        print("Cell = mean monthly Rank IC / HAC p / BH q / top-minus-bottom spread.")
        print("| Factor | 5d | 10d | 21d | 42d | 63d |")
        print("| --- | --- | --- | --- | --- | --- |")
        for factor in FACTORS:
            cells = [cell_text(summaries[view][factor][horizon]["full"]) for horizon in HORIZONS]
            print(f"| `{factor}` | " + " | ".join(cells) + " |")

    print("\n## Fold-stable significant cells")
    print("Stable requires full-family q<=.05 and the same IC/spread sign in validation and holdout.")
    print("| Stable | View | Factor | Horizon | Full IC / q / spread | Dev IC / spread | Val IC / spread | Holdout IC / spread | Months |")
    print("| --- | --- | --- | ---: | --- | --- | --- | --- | ---: |")
    candidates = stable_candidates(summaries)
    for stable, _magnitude, view, factor, horizon, item in candidates:
        full, dev, val, hold = item["full"], item["development"], item["validation"], item["holdout"]
        print(
            f"| {'yes' if stable else 'no'} | {view} | `{factor}` | {horizon} | "
            f"{number(full['ic'])} / {pnumber(full.get('q'))} / {pct(full['spread'])} | "
            f"{number(dev['ic'])} / {pct(dev['spread'])} | "
            f"{number(val['ic'])} / {pct(val['spread'])} | "
            f"{number(hold['ic'])} / {pct(hold['spread'])} | {full['months']} |"
        )
    if not candidates:
        print("| none | | | | | | | | |")

    print("\n## Strongest current readings")
    ranked = []
    for view in summaries:
        for factor in FACTORS:
            for horizon in HORIZONS:
                item = summaries[view][factor][horizon]["full"]
                if finite(item["ic"]):
                    ranked.append((abs(item["ic"]), view, factor, horizon, item))
    for _magnitude, view, factor, horizon, item in sorted(ranked, reverse=True)[:15]:
        print(
            f"- {view} `{factor}` {horizon}d: IC {number(item['ic'])}, "
            f"p {pnumber(item['p'])}, q {pnumber(item.get('q'))}, spread {pct(item['spread'])}, "
            f"hit {pct(item['hit'], 1)}, months {item['months']}, average names {item['names']:.0f}."
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database")
    args = parser.parse_args()
    connection = connect(resolve_database_path(args.database), read_only=True)
    try:
        panel = load_panel(connection)
    finally:
        connection.close()
    rows = run(panel)
    summaries = summarize_all(rows)
    print_results(panel, rows, summaries)


if __name__ == "__main__":
    main()
