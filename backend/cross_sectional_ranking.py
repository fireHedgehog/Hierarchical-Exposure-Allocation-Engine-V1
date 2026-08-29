from __future__ import annotations

import math
import sqlite3
from typing import Any

from backend.universe.library_fetch import LIBRARY_DATASET_ID, LIBRARY_UNIVERSE_STAGE


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
                  '-420 days'
                )
            )
            SELECT security_id, time, price, raw_close, volume FROM recent
            WHERE rn <= 253 ORDER BY security_id, time
            """,
            (LIBRARY_DATASET_ID, *security_ids, LIBRARY_DATASET_ID),
        ).fetchall()
        for bar in records:
            bars.setdefault(bar["security_id"], []).append(bar)

    latest = max((history[-1]["time"] for history in bars.values() if history), default=None)
    # SPY is an active desk reference and is intentionally not duplicated in
    # the disposable library dataset. Resolve its newest sufficiently deep
    # stored dataset independently, while keeping the ranked cohort on Stage 2.
    spy_security = connection.execute(
        "SELECT security_id FROM securities WHERE primary_symbol = 'SPY' ORDER BY security_id LIMIT 1"
    ).fetchone()
    spy_values: list[float] = []
    spy_dataset_id = None
    if spy_security:
        spy_dataset = connection.execute(
            """
            SELECT dataset_snapshot_id, MAX(time) AS latest, COUNT(*) AS bar_count
            FROM symbol_bars
            WHERE security_id = ? AND time <= ? AND COALESCE(adjusted_close, close) IS NOT NULL
            GROUP BY dataset_snapshot_id HAVING COUNT(*) >= 253
            ORDER BY latest DESC LIMIT 1
            """,
            (spy_security["security_id"], latest),
        ).fetchone()
        if spy_dataset:
            spy_dataset_id = spy_dataset["dataset_snapshot_id"]
            spy_values = [
                float(row["price"])
                for row in reversed(connection.execute(
                    """
                    SELECT COALESCE(adjusted_close, close) AS price FROM symbol_bars
                    WHERE dataset_snapshot_id = ? AND security_id = ? AND time <= ?
                      AND COALESCE(adjusted_close, close) IS NOT NULL
                    ORDER BY time DESC LIMIT 253
                    """,
                    (spy_dataset_id, spy_security["security_id"], latest),
                ).fetchall())
            ]
    spy_returns = {period: _return(spy_values, period) for period in (63, 126, 252)}
    rows: list[dict[str, Any]] = []
    for member in members:
        history = bars.get(member["security_id"], [])
        values = [float(bar["price"]) for bar in history]
        if len(values) < 220:
            continue
        current = values[-1]
        sma20, sma50, sma100, sma200 = (_mean(values[-period:]) for period in (20, 50, 100, 200))
        prior_sma50 = _mean(values[-70:-20])
        prior_sma200 = _mean(values[-220:-20])
        rs: dict[int, float | None] = {}
        for period in (63, 126, 252):
            own = _return(values, period)
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
        }
        rows.append(row)

    weights = {"rs_3m": .25, "rs_6m": .25, "rs_12m": .15, "high_52w_distance": .15, "trend_distance": .10, "slope": .10}
    percentiles = {key: _percentiles(rows, key) for key in weights}
    for row in rows:
        available = [(weight, percentiles[key].get(row["symbol"])) for key, weight in weights.items()]
        usable = [(weight, value) for weight, value in available if value is not None]
        row["score"] = round(sum(weight * value for weight, value in usable) / sum(weight for weight, _ in usable), 1) if usable else None

    return {
        "status": "descriptive_research", "dataset_snapshot_id": LIBRARY_DATASET_ID,
        "benchmark_dataset_snapshot_id": spy_dataset_id,
        "universe_stage": LIBRARY_UNIVERSE_STAGE, "member_count": len(members),
        "eligible_count": len(rows), "latest_price_date": latest, "rows": rows,
        "sources": [
            {"role": "Universe", "table": "staging_universe_membership", "selection": "stage = stage-2"},
            {"role": "Metadata", "table": "staging_symbols", "selection": "research_scope = general"},
            {"role": "Identity", "table": "securities", "selection": "unique primary_symbol mapping"},
            {"role": "Prices", "table": "symbol_bars", "selection": f"dataset_snapshot_id = {LIBRARY_DATASET_ID}"},
        ],
    }
