from __future__ import annotations

import math
import sqlite3
from collections import Counter
from datetime import date
from typing import Any

from backend.universe.library_fetch import LIBRARY_DATASET_ID, LIBRARY_UNIVERSE_STAGE


LEADERSHIP_WEEKS = 13
LEADERSHIP_LOOKBACK = 63
LIQUID_POOL_SIZE = 100
MIN_RAW_PRICE = 5.0
MIN_MATURE_HISTORY = 252
SECTOR_ANCHORS = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")


def _return(values: list[float], sessions: int) -> float | None:
    if len(values) <= sessions or values[-sessions - 1] <= 0:
        return None
    return values[-1] / values[-sessions - 1] - 1


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _percentiles(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    pairs = sorted((float(row[key]), row["symbol"]) for row in rows if row[key] is not None)
    if not pairs:
        return {}
    if len(pairs) == 1:
        return {pairs[0][1]: 50.0}
    result: dict[str, float] = {}
    index = 0
    while index < len(pairs):
        end = index + 1
        while end < len(pairs) and pairs[end][0] == pairs[index][0]:
            end += 1
        percentile = ((index + end - 1) / 2) / (len(pairs) - 1) * 100
        for _, symbol in pairs[index:end]:
            result[symbol] = percentile
        index = end
    return result


def _weekly_formations(dates: list[str], count: int = LEADERSHIP_WEEKS) -> list[int]:
    last_by_week: dict[tuple[int, int], int] = {}
    for index, value in enumerate(dates):
        parsed = date.fromisoformat(value)
        iso = parsed.isocalendar()
        last_by_week[(iso.year, iso.week)] = index
    mature = [index for index in last_by_week.values() if index >= MIN_MATURE_HISTORY]
    return mature[-count:]


def _leadership_overlay(
    dates: list[str],
    spy_by_date: dict[str, float],
    histories: dict[str, dict[str, dict[str, float | None]]],
    sector_by_symbol: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Translate H-XSEC-S5-002 exactly: liquid Top-100, 3M top decile,
    and the natural average weight of the latest 13 equal weekly sleeves.

    Every endpoint is a shared SPY-session date. Missing values stay missing;
    no symbol-specific row position or forward fill enters the evidence layer.
    """

    formations = _weekly_formations(dates)
    selections: list[list[str]] = []
    current_liquidity_rank: dict[str, int] = {}
    current_percentile: dict[str, float] = {}
    current_leaders: set[str] = set()
    current_reversal_return: dict[str, float] = {}
    current_reversal_percentile: dict[str, float] = {}
    current_sector_relative: dict[str, float] = {}
    current_sector_reversal_percentile: dict[str, float] = {}

    for formation in formations:
        endpoint_indices = (formation, formation - 5, formation - 21, formation - 63, formation - 126, formation - 252)
        endpoint_dates = [dates[index] for index in endpoint_indices]
        formation_date = dates[formation]
        lookback_date = dates[formation - LEADERSHIP_LOOKBACK]
        volume_dates = dates[formation - 20 : formation + 1]
        spy_now = spy_by_date.get(formation_date)
        spy_then = spy_by_date.get(lookback_date)
        if spy_now is None or spy_then is None or spy_now <= 0 or spy_then <= 0:
            continue
        spy_return = spy_now / spy_then - 1.0

        eligible: list[tuple[str, float, float, float]] = []
        for symbol, history in histories.items():
            endpoints = [history.get(day) for day in endpoint_dates]
            if any(item is None or item.get("price") is None or float(item["price"]) <= 0 for item in endpoints):
                continue
            current = history[formation_date]
            raw_close = current.get("raw_close")
            if raw_close is None or float(raw_close) < MIN_RAW_PRICE:
                continue
            dollar_volume: list[float] = []
            for day in volume_dates:
                item = history.get(day)
                if item is None or item.get("raw_close") is None or item.get("volume") is None:
                    dollar_volume = []
                    break
                raw, volume = float(item["raw_close"]), float(item["volume"])
                if raw <= 0 or volume <= 0:
                    dollar_volume = []
                    break
                dollar_volume.append(raw * volume)
            if len(dollar_volume) != 21:
                continue
            own_now = float(history[formation_date]["price"])
            own_then = float(history[lookback_date]["price"])
            relative_strength = own_now / own_then - 1.0 - spy_return
            return_5d = own_now / float(history[endpoint_dates[1]]["price"]) - 1.0
            median_dollar_volume = sorted(dollar_volume)[len(dollar_volume) // 2]
            eligible.append((symbol, median_dollar_volume, relative_strength, return_5d))

        liquid = sorted(eligible, key=lambda item: (-item[1], item[0]))[:LIQUID_POOL_SIZE]
        if not liquid:
            continue
        relative_rows = [{"symbol": symbol, "rs_3m": value} for symbol, _, value, _ in liquid]
        percentiles = _percentiles(relative_rows, "rs_3m")
        leader_count = max(1, len(liquid) // 10)
        leaders = [symbol for symbol, _, _, _ in sorted(liquid, key=lambda item: (-item[2], item[0]))[:leader_count]]
        selections.append(leaders)
        if formation == formations[-1]:
            current_liquidity_rank = {symbol: index for index, (symbol, _, _, _) in enumerate(liquid, 1)}
            current_percentile = percentiles
            current_leaders = set(leaders)

            reversal_rows = [
                {"symbol": symbol, "reversal_5d": -return_5d}
                for symbol, _, _, return_5d in liquid
            ]
            current_reversal_return = {symbol: return_5d for symbol, _, _, return_5d in liquid}
            current_reversal_percentile = _percentiles(reversal_rows, "reversal_5d")
            sector_members: dict[str, list[tuple[str, float]]] = {}
            for symbol, _, _, return_5d in liquid:
                sector = (sector_by_symbol or {}).get(symbol)
                if sector:
                    sector_members.setdefault(sector, []).append((symbol, return_5d))
            sector_relative_rows: list[dict[str, Any]] = []
            current_sector_relative: dict[str, float] = {}
            for members in sector_members.values():
                if len(members) < 3:
                    continue
                sector_mean = _mean([value for _, value in members])
                for symbol, value in members:
                    relative = value - sector_mean
                    current_sector_relative[symbol] = relative
                    sector_relative_rows.append({"symbol": symbol, "sector_relative_reversal": -relative})
            current_sector_reversal_percentile = _percentiles(
                sector_relative_rows, "sector_relative_reversal"
            )

    appearances = Counter(symbol for selection in selections for symbol in selection)
    sleeve_weights: Counter[str] = Counter()
    if selections:
        for selection in selections:
            for symbol in selection:
                sleeve_weights[symbol] += 1.0 / len(selection) / len(selections)
    return {
        "formation_count": len(selections),
        "liquidity_rank": current_liquidity_rank,
        "rs_3m_percentile": current_percentile,
        "current_leaders": current_leaders,
        "appearances": appearances,
        "persistence": {
            symbol: count / len(selections) for symbol, count in appearances.items()
        } if selections else {},
        "candidate_weight": dict(sleeve_weights),
        "return_5d": current_reversal_return,
        "reversal_5d_percentile": current_reversal_percentile,
        "sector_relative_return_5d": current_sector_relative,
        "sector_relative_reversal_percentile": current_sector_reversal_percentile,
    }


def get_cross_sectional_ranking(connection: sqlite3.Connection) -> dict[str, Any]:
    members = connection.execute(
        """
        WITH cohort AS (
          SELECT DISTINCT symbol FROM staging_universe_membership WHERE stage = ?
        ), mapped AS (
          SELECT primary_symbol, MIN(security_id) AS security_id, COUNT(*) AS matches
          FROM securities GROUP BY primary_symbol
        )
        SELECT cohort.symbol, staging.name, staging.category, mapped.security_id
        FROM cohort
        JOIN staging_symbols AS staging ON staging.symbol = cohort.symbol
        JOIN mapped ON mapped.primary_symbol = cohort.symbol AND mapped.matches = 1
        WHERE staging.research_scope = 'general'
        ORDER BY cohort.symbol
        """,
        (LIBRARY_UNIVERSE_STAGE,),
    ).fetchall()
    security_ids = [row["security_id"] for row in members]
    sector_by_symbol: dict[str, str] = {}
    sector_placeholders = ",".join("?" for _ in SECTOR_ANCHORS)
    for row in connection.execute(
        f"""SELECT DISTINCT symbol, anchor FROM staging_universe_membership
             WHERE stage = ? AND anchor IN ({sector_placeholders}) ORDER BY symbol""",
        (LIBRARY_UNIVERSE_STAGE, *SECTOR_ANCHORS),
    ):
        # The research compiler currently enforces one primary sector. If a
        # future disposable roster breaks that contract, omit the ambiguous
        # sector-relative reading instead of silently choosing a membership.
        if row["symbol"] in sector_by_symbol:
            sector_by_symbol[row["symbol"]] = ""
        else:
            sector_by_symbol[row["symbol"]] = row["anchor"]
    bars: dict[str, list[sqlite3.Row]] = {}
    if security_ids:
        placeholders = ",".join("?" for _ in security_ids)
        records = connection.execute(
            f"""
            WITH recent AS (
              SELECT security_id, time, COALESCE(adjusted_close, close) AS price,
                     COALESCE(raw_close, close) AS raw_close, volume,
                     ROW_NUMBER() OVER (PARTITION BY security_id ORDER BY time DESC) AS rn
              FROM symbol_bars
              WHERE dataset_snapshot_id = ? AND security_id IN ({placeholders})
                AND COALESCE(adjusted_close, close) IS NOT NULL
                AND time >= date(
                  (SELECT MAX(time) FROM symbol_bars WHERE dataset_snapshot_id = ?),
                  '-700 days'
                )
            )
            SELECT security_id, time, price, raw_close, volume FROM recent
            WHERE rn <= 340 ORDER BY security_id, time
            """,
            (LIBRARY_DATASET_ID, *security_ids, LIBRARY_DATASET_ID),
        ).fetchall()
        for bar in records:
            bars.setdefault(bar["security_id"], []).append(bar)

    latest_counts = Counter(history[-1]["time"] for history in bars.values() if history)
    latest = max(latest_counts, key=lambda day: (latest_counts[day], day)) if latest_counts else None
    # SPY is an active desk reference and is intentionally not duplicated in
    # the disposable library dataset. Resolve its newest sufficiently deep
    # stored dataset independently, while keeping the ranked cohort on Stage 2.
    spy_security = connection.execute(
        "SELECT security_id FROM securities WHERE primary_symbol = 'SPY' ORDER BY security_id LIMIT 1"
    ).fetchone()
    spy_history: list[sqlite3.Row] = []
    spy_dataset_id = None
    if spy_security:
        spy_dataset = connection.execute(
            """
            SELECT dataset_snapshot_id, MAX(time) AS latest, COUNT(*) AS bar_count
            FROM symbol_bars
            WHERE security_id = ? AND time <= ? AND COALESCE(adjusted_close, close) IS NOT NULL
            GROUP BY dataset_snapshot_id HAVING COUNT(*) >= 340 AND MAX(time) = ?
            ORDER BY latest DESC LIMIT 1
            """,
            (spy_security["security_id"], latest, latest),
        ).fetchone()
        if spy_dataset:
            spy_dataset_id = spy_dataset["dataset_snapshot_id"]
            spy_history = list(reversed(connection.execute(
                    """
                    SELECT time, COALESCE(adjusted_close, close) AS price FROM symbol_bars
                    WHERE dataset_snapshot_id = ? AND security_id = ? AND time <= ?
                      AND COALESCE(adjusted_close, close) IS NOT NULL
                    ORDER BY time DESC LIMIT 340
                    """,
                    (spy_dataset_id, spy_security["security_id"], latest),
                ).fetchall()))
    spy_dates = [row["time"] for row in spy_history]
    spy_by_date = {row["time"]: float(row["price"]) for row in spy_history}
    histories: dict[str, dict[str, dict[str, float | None]]] = {}
    for member in members:
        history = bars.get(member["security_id"], [])
        if not history or history[-1]["time"] != latest:
            continue
        histories[member["symbol"]] = {
            row["time"]: {
                "price": float(row["price"]),
                "raw_close": float(row["raw_close"]) if row["raw_close"] is not None else None,
                "volume": float(row["volume"]) if row["volume"] is not None else None,
            }
            for row in history
        }
    leadership = _leadership_overlay(spy_dates, spy_by_date, histories, sector_by_symbol) if len(spy_dates) >= 340 else {
        "formation_count": 0,
        "liquidity_rank": {},
        "rs_3m_percentile": {},
        "current_leaders": set(),
        "appearances": {},
        "persistence": {},
        "candidate_weight": {},
        "return_5d": {},
        "reversal_5d_percentile": {},
        "sector_relative_return_5d": {},
        "sector_relative_reversal_percentile": {},
    }
    spy_returns: dict[int, float | None] = {}
    for period in (63, 126, 252):
        if len(spy_dates) <= period:
            spy_returns[period] = None
            continue
        then = spy_by_date[spy_dates[-1 - period]]
        now = spy_by_date[spy_dates[-1]]
        spy_returns[period] = now / then - 1.0 if then > 0 else None
    rows: list[dict[str, Any]] = []
    for member in members:
        history = bars.get(member["security_id"], [])
        if not history or history[-1]["time"] != latest:
            continue
        values = [float(bar["price"]) for bar in history]
        if len(values) < 220:
            continue
        current = values[-1]
        by_date = histories.get(member["symbol"], {})
        sma20, sma50, sma100, sma200 = (_mean(values[-period:]) for period in (20, 50, 100, 200))
        prior_sma50 = _mean(values[-70:-20])
        prior_sma200 = _mean(values[-220:-20])
        rs: dict[int, float | None] = {}
        for period in (63, 126, 252):
            lookback_date = spy_dates[-1 - period] if len(spy_dates) > period else None
            past = by_date.get(lookback_date or "", {}).get("price")
            own = current / float(past) - 1.0 if past is not None and float(past) > 0 else None
            benchmark = spy_returns[period]
            rs[period] = own - benchmark if own is not None and benchmark is not None else None
        high_window = max(values[-252:])
        liquid = [float(bar["raw_close"]) * float(bar["volume"]) for bar in history[-21:] if bar["raw_close"] and bar["volume"]]
        row = {
            "symbol": member["symbol"], "name": member["name"], "category": member["category"],
            "as_of": history[-1]["time"], "price": current,
            "rs_3m": rs[63], "rs_6m": rs[126], "rs_12m": rs[252],
            "high_52w_distance": current / high_window - 1,
            "trend_distance": _mean([math.log(current / average) for average in (sma20, sma50, sma100, sma200)]),
            "slope": _mean([sma50 / prior_sma50 - 1, sma200 / prior_sma200 - 1]),
            "above_all_mas": current > sma20 and current > sma50 and current > sma100 and current > sma200,
            "ordered_mas": current > sma20 > sma50 > sma100 > sma200,
            "median_dollar_volume_21d": sorted(liquid)[len(liquid) // 2] if liquid else None,
            "liquidity_rank": leadership["liquidity_rank"].get(member["symbol"]),
            "is_liquid_top100": member["symbol"] in leadership["liquidity_rank"],
            "rs_3m_percentile": leadership["rs_3m_percentile"].get(member["symbol"]),
            "is_current_leader": member["symbol"] in leadership["current_leaders"],
            "leadership_appearances_13w": leadership["appearances"].get(member["symbol"], 0)
                if leadership["formation_count"] else None,
            "leadership_persistence": leadership["persistence"].get(member["symbol"], 0.0)
                if leadership["formation_count"] else None,
            "candidate_weight": leadership["candidate_weight"].get(member["symbol"], 0.0)
                if leadership["formation_count"] else None,
            "return_5d": leadership["return_5d"].get(member["symbol"]),
            "reversal_5d_percentile": leadership["reversal_5d_percentile"].get(member["symbol"]),
            "sector_relative_return_5d": leadership["sector_relative_return_5d"].get(member["symbol"]),
            "sector_relative_reversal_percentile": leadership["sector_relative_reversal_percentile"].get(member["symbol"]),
        }
        rows.append(row)

    weights = {"rs_3m": .25, "rs_6m": .25, "rs_12m": .15, "high_52w_distance": .15, "trend_distance": .10, "slope": .10}
    percentiles = {key: _percentiles(rows, key) for key in weights}
    for row in rows:
        available = [(weight, percentiles[key].get(row["symbol"])) for key, weight in weights.items()]
        usable = [(weight, value) for weight, value in available if value is not None]
        row["score"] = round(sum(weight * value for weight, value in usable) / sum(weight for weight, _ in usable), 1) if usable else None
        row["technical_context_score"] = row["score"]
        reversal_percentiles = [
            value for value in (
                row["reversal_5d_percentile"],
                row["sector_relative_reversal_percentile"],
            ) if value is not None
        ]
        row["is_reversal_watch"] = bool(reversal_percentiles and max(reversal_percentiles) >= 90.0)

    return {
        "status": "descriptive_research", "dataset_snapshot_id": LIBRARY_DATASET_ID,
        "benchmark_dataset_snapshot_id": spy_dataset_id,
        "universe_stage": LIBRARY_UNIVERSE_STAGE, "member_count": len(members),
        "eligible_count": len(rows), "latest_price_date": latest, "rows": rows,
        "leadership_formation_count": leadership["formation_count"],
        "liquid_top100_count": len(leadership["liquidity_rank"]),
        "current_leader_count": len(leadership["current_leaders"]),
        "active_sleeve_count": sum(1 for value in leadership["candidate_weight"].values() if value > 0),
        "reversal_watch_count": sum(1 for row in rows if row["is_reversal_watch"]),
        "sources": [
            {"role": "Universe", "table": "staging_universe_membership", "selection": "stage = stage-2"},
            {"role": "Metadata", "table": "staging_symbols", "selection": "research_scope = general"},
            {"role": "Identity", "table": "securities", "selection": "unique primary_symbol mapping"},
            {"role": "Prices", "table": "symbol_bars", "selection": f"dataset_snapshot_id = {LIBRARY_DATASET_ID}"},
        ],
    }
