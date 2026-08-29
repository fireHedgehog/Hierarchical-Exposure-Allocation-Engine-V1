"""H-XSEC-S2-001 and its gated H-THEME-S2-001 consumer.

One read-only, disposable loop.  It prints compact Markdown ledgers and never
writes the database or a result file.

Run:
    .venv/Scripts/python.exe -m backend.research_lab.quarter_start_leadership_acceptance
"""

from __future__ import annotations

import argparse
import calendar
import math
import statistics
from collections import Counter, defaultdict, deque
from datetime import date

import numpy as np

from backend.database import connect, resolve_database_path
from backend.universe.library_fetch import (
    DUAL_BASIS_CONTRACT_REVISION,
    LIBRARY_CONTRACT_THROUGH,
    LIBRARY_DATASET_ID,
    LIBRARY_UNIVERSE_STAGE,
)


ANCHOR_DATASET_ID = "real-macro-0f184797-d738-4ecd-a615-83b0020c5753"
SECTORS = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")
SPY = "SPY"
FIRST_SESSIONS = 21
LEADER_COUNT = 3
CONTROL_LAST_RANK = 10
MIN_GROUP_COVERAGE = 0.80


def mean(values):
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return statistics.fmean(clean) if clean else None


def median(values):
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return statistics.median(clean) if clean else None


def pct(value, digits=1):
    return "NA" if value is None or not math.isfinite(float(value)) else f"{100 * value:+.{digits}f}%"


def number(value, digits=2):
    return "NA" if value is None or not math.isfinite(float(value)) else f"{value:.{digits}f}"


def qkey(day_string):
    d = date.fromisoformat(day_string)
    return d.year, (d.month - 1) // 3 + 1


def qlabel(q):
    return f"{q[0]}Q{q[1]}"


def next_q(q, steps=1):
    year, quarter = q
    serial = year * 4 + quarter - 1 + steps
    return serial // 4, serial % 4 + 1


def quarter_calendar_end(q):
    month = q[1] * 3
    return date(q[0], month, calendar.monthrange(q[0], month)[1])


def quarter_calendar_start(q):
    return date(q[0], (q[1] - 1) * 3 + 1, 1)


def is_complete_quarter(q, indices, dates, cutoff):
    if quarter_calendar_end(q) > cutoff or not indices:
        return False
    first = date.fromisoformat(dates[indices[0]])
    last = date.fromisoformat(dates[indices[-1]])
    # Exchange holidays/weekends need room, but a partial first/last month does not.
    return (first - quarter_calendar_start(q)).days <= 7 and (quarter_calendar_end(q) - last).days <= 7


def fold_for(outcome_q):
    if outcome_q <= (2018, 4):
        return "development"
    if outcome_q <= (2023, 2):
        return "validation"
    if outcome_q <= (2026, 2):
        return "holdout"
    return "right-censored"


def finite(value):
    return value is not None and math.isfinite(float(value))


def total_return(values, start, end):
    first, last = values[start], values[end]
    if not finite(first) or not finite(last) or first <= 0:
        return None
    return float(last / first - 1.0)


def path_margin(values, start, end, base):
    if not finite(base) or base <= 0 or start > end:
        return None, 0.0
    path = values[start : end + 1]
    usable = path[np.isfinite(path)]
    coverage = len(usable) / len(path) if len(path) else 0.0
    if not len(usable):
        return None, coverage
    return float(np.min(usable / base - 1.0)), coverage


def max_drawdown(values, start, end):
    path = values[start : end + 1]
    usable = path[np.isfinite(path)]
    if len(usable) < 2:
        return None
    peaks = np.maximum.accumulate(usable)
    return float(np.min(usable / peaks - 1.0))


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
                         AND r.contract_revision = ?
                         AND r.requested_to >= ?
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
        accepted = 0 if coverage is None else coverage["accepted"] or 0
        eligible = 0 if coverage is None else coverage["eligible"] or 0
        raise RuntimeError(f"price gate closed: {accepted}/{eligible} accepted receipts")

    anchor_security = connection.execute(
        "SELECT security_id FROM securities WHERE primary_symbol = ?", (SPY,)
    ).fetchone()
    if anchor_security is None:
        raise RuntimeError("SPY security identity is missing")
    spy_rows = connection.execute(
        """SELECT time, COALESCE(adjusted_close, close) AS close
           FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ?
           AND COALESCE(adjusted_close, close) IS NOT NULL ORDER BY time""",
        (ANCHOR_DATASET_ID, anchor_security["security_id"]),
    ).fetchall()
    dates = [row["time"] for row in spy_rows]
    if not dates:
        raise RuntimeError(f"SPY is missing from anchor dataset {ANCHOR_DATASET_ID}")
    date_index = {day: i for i, day in enumerate(dates)}
    n_dates = len(dates)

    anchors = {}
    for symbol in (SPY, *SECTORS):
        security = connection.execute(
            "SELECT security_id FROM securities WHERE primary_symbol = ?", (symbol,)
        ).fetchone()
        if security is None:
            raise RuntimeError(f"anchor identity missing: {symbol}")
        values = np.full(n_dates, np.nan)
        for row in connection.execute(
            """SELECT time, COALESCE(adjusted_close, close) AS close
               FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ?
               AND COALESCE(adjusted_close, close) IS NOT NULL ORDER BY time""",
            (ANCHOR_DATASET_ID, security["security_id"]),
        ):
            index = date_index.get(row["time"])
            if index is not None:
                values[index] = row["close"]
        anchors[symbol] = values

    memberships = defaultdict(list)
    for row in connection.execute(
        f"""SELECT DISTINCT m.anchor, m.symbol
             FROM staging_universe_membership AS m
             JOIN staging_symbols AS s ON s.symbol = m.symbol
             WHERE m.stage = ? AND m.anchor IN ({','.join('?' for _ in SECTORS)})
               AND s.research_scope = 'general'
             ORDER BY m.anchor, m.symbol""",
        (LIBRARY_UNIVERSE_STAGE, *SECTORS),
    ):
        memberships[row["anchor"]].append(row["symbol"])
    members = sorted({symbol for symbols in memberships.values() for symbol in symbols})
    if any(not memberships[sector] for sector in SECTORS):
        raise RuntimeError("at least one primary sector has no frozen members")

    duplicate_views = sum(len(symbols) for symbols in memberships.values()) - len(members)
    prices = {
        symbol: {
            "close": np.full(n_dates, np.nan),
            "open": np.full(n_dates, np.nan),
            "high": np.full(n_dates, np.nan),
            "low": np.full(n_dates, np.nan),
        }
        for symbol in members
    }
    placeholders = ",".join("?" for _ in members)
    query = f"""
        SELECT s.primary_symbol AS symbol, b.time, b.adjusted_close, b.adjusted_open,
               b.adjusted_high, b.adjusted_low
        FROM symbol_bars AS b
        JOIN securities AS s ON s.security_id = b.security_id
        WHERE b.dataset_snapshot_id = ? AND s.primary_symbol IN ({placeholders})
        ORDER BY s.primary_symbol, b.time
    """
    range_anomalies = {"floating": 0, "over_1bp": 0, "over_1pct": 0}
    for row in connection.execute(query, (LIBRARY_DATASET_ID, *members)):
        index = date_index.get(row["time"])
        if index is None:
            continue
        target = prices[row["symbol"]]
        close = row["adjusted_close"]
        open_ = row["adjusted_open"]
        high = row["adjusted_high"]
        low = row["adjusted_low"]
        target["close"][index] = close
        target["open"][index] = open_
        if all(finite(value) for value in (open_, high, low, close)):
            floor, ceiling = min(open_, close), max(open_, close)
            deviation = max(
                0.0,
                (low - floor) / floor,
                (ceiling - high) / ceiling,
            )
            if deviation > 1e-8:
                range_anomalies["floating"] += 1
            if deviation > 0.0001:
                range_anomalies["over_1bp"] += 1
            if deviation > 0.01:
                range_anomalies["over_1pct"] += 1
            # A range diagnostic cannot exclude an observed open or close.
            # Expand only in disposable memory; source fields stay untouched.
            target["high"][index] = max(high, open_, close)
            target["low"][index] = min(low, open_, close)
        else:
            target["high"][index] = high
            target["low"][index] = low

    return {
        "dates": dates,
        "anchors": anchors,
        "memberships": memberships,
        "members": members,
        "prices": prices,
        "eligible": coverage["eligible"],
        "duplicate_views": duplicate_views,
        "range_anomalies": range_anomalies,
    }


def rolling_gap_state(panel):
    cache = {}
    for symbol, price in panel["prices"].items():
        closes, opens = price["close"], price["open"]
        gaps = np.full(len(closes), np.nan)
        zscores = np.full(len(closes), np.nan)
        history = deque()
        running_sum = 0.0
        running_squares = 0.0
        for i in range(1, len(closes)):
            if finite(opens[i]) and finite(closes[i - 1]) and closes[i - 1] > 0:
                gap = float(opens[i] / closes[i - 1] - 1.0)
                gaps[i] = gap
                if len(history) == 60:
                    variance = max(
                        (running_squares - running_sum * running_sum / 60) / 59,
                        0.0,
                    )
                    sigma = math.sqrt(variance)
                    if sigma > 0:
                        zscores[i] = gap / sigma
                history.append(gap)
                running_sum += gap
                running_squares += gap * gap
                if len(history) > 60:
                    old = history.popleft()
                    running_sum -= old
                    running_squares -= old * old
        cache[symbol] = (gaps, zscores)
    return cache


def rank_returns(symbols, arrays, start, end):
    returns = {}
    for symbol in symbols:
        value = total_return(arrays[symbol], start, end)
        if value is not None:
            returns[symbol] = value
    ordered = sorted(returns, key=lambda symbol: (-returns[symbol], symbol))
    return returns, {symbol: rank + 1 for rank, symbol in enumerate(ordered)}


def first_gap_event(gap_state, symbol, first_indices):
    gaps, zscores = gap_state[symbol]
    for index in first_indices:
        if finite(gaps[index]) and gaps[index] > 0 and finite(zscores[index]) and zscores[index] >= 2:
            return index, float(gaps[index]), float(zscores[index])
    return None


def decide_security(record, panel, q_indices, end_rank, spy_end_return, anchor_end_return):
    price = panel["prices"][record["symbol"]]
    if record["panel"] == "A":
        start = record["event_index"]
    else:
        start = q_indices[FIRST_SESSIONS]
    margin, coverage = path_margin(price["close"], start, q_indices[-1], record["base"])
    low_margin, low_coverage = path_margin(price["low"], start, q_indices[-1], record["base"])
    end_return = total_return(price["close"], q_indices[0], q_indices[-1])
    end_anchor_excess = None if end_return is None or anchor_end_return is None else end_return - anchor_end_return
    end_spy_excess = None if end_return is None or spy_end_return is None else end_return - spy_end_return
    record.update(
        hold_margin=margin,
        intraday_margin=low_margin,
        hold_coverage=min(coverage, low_coverage),
        q0_end_rank=end_rank.get(record["symbol"]),
        q0_end_spy_excess=end_spy_excess,
        q0_end_anchor_excess=end_anchor_excess,
    )
    if record["panel"] == "A" and finite(price["close"][q_indices[-1]]) and record["raw_gap"]:
        retained_return = float(price["close"][q_indices[-1]] / record["base"] - 1.0)
        record["gap_retained_fraction"] = retained_return / record["raw_gap"]
    if record["panel"] == "B":
        relative_days = []
        spy_close = panel["anchors"][SPY]
        for index in q_indices[1:]:
            own_day = total_return(price["close"], index - 1, index)
            spy_day = total_return(spy_close, index - 1, index)
            if own_day is not None and spy_day is not None:
                relative_days.append(own_day > spy_day)
        record["positive_relative_day_fraction"] = mean(relative_days)
    if min(coverage, low_coverage) < MIN_GROUP_COVERAGE or margin is None:
        record["decision"] = "missing"
    else:
        record["decision"] = (
            "held"
            if margin >= 0
            and end_rank.get(record["symbol"], 10_000) <= LEADER_COUNT
            and end_return is not None
            and end_return > 0
            and end_spy_excess is not None
            and end_spy_excess > 0
            and end_anchor_excess is not None
            and end_anchor_excess > 0
            else "failed"
        )


def form_security_quarter(panel, gap_state, sector, q, q_indices, prior_indices, current=False):
    members = panel["memberships"][sector]
    closes = {symbol: panel["prices"][symbol]["close"] for symbol in members}
    prior_returns, prior_rank = rank_returns(members, closes, prior_indices[0], prior_indices[-1])
    day21 = q_indices[FIRST_SESSIONS - 1]
    early_returns, early_rank = rank_returns(members, closes, q_indices[0], day21)
    end_returns, end_rank = rank_returns(members, closes, q_indices[0], q_indices[-1])
    spy_early = total_return(panel["anchors"][SPY], q_indices[0], day21)
    anchor_early = total_return(panel["anchors"][sector], q_indices[0], day21)
    spy_end = total_return(panel["anchors"][SPY], q_indices[0], q_indices[-1])
    anchor_end = total_return(panel["anchors"][sector], q_indices[0], q_indices[-1])
    if spy_early is None or anchor_early is None or spy_end is None or anchor_end is None:
        return [], []

    leaders, controls = [], []
    for symbol, rank in early_rank.items():
        if rank > CONTROL_LAST_RANK or prior_rank.get(symbol, 10_000) <= LEADER_COUNT:
            continue
        early = early_returns[symbol]
        if early <= 0 or early <= spy_early or early <= anchor_early:
            continue
        event = first_gap_event(gap_state, symbol, q_indices[:FIRST_SESSIONS])
        if event:
            event_index, raw_gap, normalized_gap = event
            previous_high = panel["prices"][symbol]["high"][event_index - 1]
            event_open = panel["prices"][symbol]["open"][event_index]
            record = {
                "panel": "A",
                "q0": q,
                "q1": next_q(q),
                "group": sector,
                "symbol": symbol,
                "rank21": rank,
                "origin_date": panel["dates"][event_index],
                "event_index": event_index,
                "base": float(panel["prices"][symbol]["close"][event_index - 1]),
                "origin_magnitude": normalized_gap,
                "raw_gap": raw_gap,
                "breakaway_gap": finite(previous_high) and event_open > previous_high,
                "early_spy_excess": early - spy_early,
                "early_anchor_excess": early - anchor_early,
            }
        else:
            record = {
                "panel": "B",
                "q0": q,
                "q1": next_q(q),
                "group": sector,
                "symbol": symbol,
                "rank21": rank,
                "origin_date": panel["dates"][q_indices[0]],
                "event_index": None,
                "base": float(panel["prices"][symbol]["close"][q_indices[0]]),
                "origin_magnitude": early - anchor_early,
                "raw_gap": None,
                "breakaway_gap": None,
                "early_spy_excess": early - spy_early,
                "early_anchor_excess": early - anchor_early,
            }
        if rank <= LEADER_COUNT:
            decide_security(record, panel, q_indices, end_rank, spy_end, anchor_end)
            if current:
                record["decision"] = "forming"
            leaders.append(record)
        else:
            record["decision"] = "control"
            record["hold_margin"] = None
            controls.append(record)
    return leaders, controls


def form_anchor_quarter(panel, q, q_indices, prior_indices, current=False):
    prior_returns, prior_rank = rank_returns(SECTORS, panel["anchors"], prior_indices[0], prior_indices[-1])
    day21 = q_indices[FIRST_SESSIONS - 1]
    early_returns, early_rank = rank_returns(SECTORS, panel["anchors"], q_indices[0], day21)
    end_returns, end_rank = rank_returns(SECTORS, panel["anchors"], q_indices[0], q_indices[-1])
    spy_early = total_return(panel["anchors"][SPY], q_indices[0], day21)
    spy_end = total_return(panel["anchors"][SPY], q_indices[0], q_indices[-1])
    leaders, controls = [], []
    if spy_early is None or spy_end is None:
        return leaders, controls
    for sector, rank in early_rank.items():
        if rank > CONTROL_LAST_RANK or prior_rank.get(sector, 10_000) <= LEADER_COUNT:
            continue
        early = early_returns[sector]
        if early <= 0 or early <= spy_early:
            continue
        record = {
            "panel": "C",
            "q0": q,
            "q1": next_q(q),
            "group": sector,
            "symbol": sector,
            "rank21": rank,
            "origin_date": panel["dates"][q_indices[0]],
            "event_index": None,
            "base": float(panel["anchors"][sector][q_indices[0]]),
            "origin_magnitude": early - spy_early,
            "early_spy_excess": early - spy_early,
            "early_anchor_excess": None,
            "breakaway_gap": None,
        }
        if rank <= LEADER_COUNT:
            margin, coverage = path_margin(
                panel["anchors"][sector], q_indices[FIRST_SESSIONS], q_indices[-1], record["base"]
            )
            end_return = end_returns.get(sector)
            end_excess = None if end_return is None else end_return - spy_end
            record.update(
                hold_margin=margin,
                intraday_margin=None,
                hold_coverage=coverage,
                q0_end_rank=end_rank.get(sector),
                q0_end_spy_excess=end_excess,
                q0_end_anchor_excess=None,
            )
            record["decision"] = (
                "held"
                if coverage >= MIN_GROUP_COVERAGE
                and margin is not None
                and margin >= 0
                and end_rank.get(sector, 10_000) <= LEADER_COUNT
                and end_return is not None
                and end_return > 0
                and end_excess is not None
                and end_excess > 0
                else "failed"
            )
            if current:
                record["decision"] = "forming"
            leaders.append(record)
        else:
            record["decision"] = "control"
            record["hold_margin"] = None
            controls.append(record)
    return leaders, controls


def group_context(panel, sector, q_indices, q1_indices, excluded):
    spy_q0 = total_return(panel["anchors"][SPY], q_indices[0], q_indices[-1])
    spy_q1 = total_return(panel["anchors"][SPY], q_indices[-1], q1_indices[-1])
    anchor_q1 = total_return(panel["anchors"][sector], q_indices[-1], q1_indices[-1])
    roster = [symbol for symbol in panel["memberships"][sector] if symbol not in excluded]
    q0_excess, q1_excess = [], []
    q0_by_symbol, q1_by_symbol = {}, {}
    q1_by_symbol = {}
    for symbol in roster:
        close = panel["prices"][symbol]["close"]
        r0 = total_return(close, q_indices[0], q_indices[-1])
        r1 = total_return(close, q_indices[-1], q1_indices[-1])
        if r0 is not None and r1 is not None and spy_q0 is not None and spy_q1 is not None:
            q0_excess.append(r0 - spy_q0)
            q1_excess.append(r1 - spy_q1)
            q0_by_symbol[symbol] = r0 - spy_q0
            q1_by_symbol[symbol] = r1 - spy_q1
    coverage = len(q1_excess) / len(roster) if roster else 0.0
    adequate = anchor_q1 is not None and spy_q1 is not None and coverage >= MIN_GROUP_COVERAGE
    q0_top3 = set(sorted(q0_by_symbol, key=lambda symbol: (-q0_by_symbol[symbol], symbol))[:3])
    q1_top3 = set(sorted(q1_by_symbol, key=lambda symbol: (-q1_by_symbol[symbol], symbol))[:3])
    return {
        "anchor_excess": None if anchor_q1 is None or spy_q1 is None else anchor_q1 - spy_q1,
        "member_median_excess": median(q1_excess),
        "member_mean_excess": mean(q1_excess),
        "participation_delta": (
            mean([value > 0 for value in q1_excess]) - mean([value > 0 for value in q0_excess])
            if q0_excess and q1_excess
            else None
        ),
        "coverage": coverage,
        "adequate": adequate,
        "anchor_max_drawdown": max_drawdown(panel["anchors"][sector], q_indices[-1], q1_indices[-1]),
        "q1_by_symbol": q1_by_symbol,
        "new_top3_members": sorted(q1_top3 - q0_top3),
    }


def attach_q1(panel, record, q_indices, q1_indices, context):
    if record["panel"] == "C":
        close = panel["anchors"][record["symbol"]]
        peers = SECTORS
        arrays = panel["anchors"]
        anchor_excess = context["anchor_excess"]
    else:
        close = panel["prices"][record["symbol"]]["close"]
        peers = panel["memberships"][record["group"]]
        arrays = {symbol: panel["prices"][symbol]["close"] for symbol in peers}
        anchor_return = total_return(panel["anchors"][record["group"]], q_indices[-1], q1_indices[-1])
        security_return = total_return(close, q_indices[-1], q1_indices[-1])
        anchor_excess = None if security_return is None or anchor_return is None else security_return - anchor_return
    security_return = total_return(close, q_indices[-1], q1_indices[-1])
    spy_return = total_return(panel["anchors"][SPY], q_indices[-1], q1_indices[-1])
    _, rank = rank_returns(peers, arrays, q_indices[-1], q1_indices[-1])
    record.update(
        fold=fold_for(record["q1"]),
        q1_return=security_return,
        q1_spy_excess=None if security_return is None or spy_return is None else security_return - spy_return,
        q1_anchor_excess=anchor_excess,
        q1_rank=rank.get(record["symbol"]),
        q1_top3=record["symbol"] in rank and rank[record["symbol"]] <= LEADER_COUNT,
        q1_max_drawdown=max_drawdown(close, q_indices[-1], q1_indices[-1]),
        group_context=context,
    )


def run_cross(panel):
    quarter_indices = defaultdict(list)
    for index, day in enumerate(panel["dates"]):
        quarter_indices[qkey(day)].append(index)
    cutoff = date.fromisoformat(LIBRARY_CONTRACT_THROUGH)
    gap_state = rolling_gap_state(panel)
    leaders, controls = [], []
    current_leaders = []

    for q in sorted(quarter_indices):
        prior, q1 = next_q(q, -1), next_q(q)
        indices = quarter_indices[q]
        if (
            len(indices) < FIRST_SESSIONS
            or prior not in quarter_indices
            or not is_complete_quarter(prior, quarter_indices[prior], panel["dates"], cutoff)
        ):
            continue
        current = quarter_calendar_end(q) > cutoff
        security_leaders, security_controls = [], []
        for sector in SECTORS:
            formed, compared = form_security_quarter(
                panel, gap_state, sector, q, indices, quarter_indices[prior], current=current
            )
            security_leaders.extend(formed)
            security_controls.extend(compared)
        anchor_leaders, anchor_controls = form_anchor_quarter(
            panel, q, indices, quarter_indices[prior], current=current
        )
        if current:
            for record in security_leaders + anchor_leaders:
                record["observation_state"] = "forming"
            current_leaders.extend(security_leaders + anchor_leaders)
            continue
        if q1 not in quarter_indices or not is_complete_quarter(q1, quarter_indices[q1], panel["dates"], cutoff):
            for record in security_leaders + anchor_leaders:
                record["observation_state"] = f"{record['decision']}; Q1 immature"
            current_leaders.extend(security_leaders + anchor_leaders)
            continue

        q1_indices = quarter_indices[q1]
        origins_by_group = defaultdict(set)
        for record in security_leaders:
            origins_by_group[record["group"]].add(record["symbol"])
        contexts = {
            sector: group_context(panel, sector, indices, q1_indices, origins_by_group[sector])
            for sector in SECTORS
        }
        for record in security_leaders + security_controls:
            attach_q1(panel, record, indices, q1_indices, contexts[record["group"]])
        for record in anchor_leaders + anchor_controls:
            attach_q1(panel, record, indices, q1_indices, contexts[record["group"]])
        leaders.extend(security_leaders + anchor_leaders)
        controls.extend(security_controls + anchor_controls)

    return leaders, controls, current_leaders, quarter_indices


def quarter_weighted(records, field):
    by_group = defaultdict(list)
    for record in records:
        value = record
        for key in field.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if finite(value):
            by_group[(record["q1"], record["group"])].append(float(value))
    by_quarter = defaultdict(list)
    for (outcome_q, _), values in by_group.items():
        by_quarter[outcome_q].append(statistics.fmean(values))
    return mean([statistics.fmean(values) for values in by_quarter.values()])


def paired_difference(left, right, field="q1_spy_excess", by_group=True):
    left_group, right_group = defaultdict(list), defaultdict(list)
    for record in left:
        if finite(record.get(field)):
            key = (record["q1"], record["group"] if by_group else "all-sectors")
            left_group[key].append(record[field])
    for record in right:
        if finite(record.get(field)):
            key = (record["q1"], record["group"] if by_group else "all-sectors")
            right_group[key].append(record[field])
    by_quarter = defaultdict(list)
    for key in left_group.keys() & right_group.keys():
        by_quarter[key[0]].append(mean(left_group[key]) - mean(right_group[key]))
    return mean([mean(values) for values in by_quarter.values()]), len(left_group.keys() & right_group.keys())


def worst_loo(records, field, kinds=(("name", "symbol"), ("sector", "group"))):
    if len(records) < 3:
        return "insufficient"
    candidates = []
    for kind, key in kinds:
        for entity in sorted({record[key] for record in records}):
            remaining = [record for record in records if record[key] != entity]
            result = quarter_weighted(remaining, field)
            if result is not None:
                candidates.append((result, kind, entity))
    if not candidates:
        return "insufficient"
    result, kind, entity = min(candidates)
    return f"{kind} {entity}: {pct(result)}"


def minimum_loo(records, field, kinds):
    values = []
    for _, key in kinds:
        for entity in sorted({record[key] for record in records}):
            result = quarter_weighted([record for record in records if record[key] != entity], field)
            if result is not None:
                values.append(result)
    return min(values) if values else None


def worst_group_loo(records):
    candidates = []
    for sector in sorted({record["group"] for record in records}):
        remaining = [record for record in records if record["group"] != sector]
        anchor = quarter_weighted(remaining, "group_context.anchor_excess")
        member = quarter_weighted(remaining, "group_context.member_median_excess")
        if anchor is not None and member is not None:
            candidates.append((min(anchor, member), sector, anchor, member))
    if not candidates:
        return "insufficient"
    _, sector, anchor, member = min(candidates)
    return f"sector {sector}: A {pct(anchor)} / M {pct(member)}"


def fold_summary(records, controls, panel_name, fold):
    selected = [record for record in records if record["panel"] == panel_name and record["fold"] == fold]
    held = [record for record in selected if record["decision"] == "held"]
    failed = [record for record in selected if record["decision"] == "failed"]
    compared = [record for record in controls if record["panel"] == panel_name and record["fold"] == fold]
    by_group = panel_name != "C"
    leader_control, lc_cells = paired_difference(selected, compared, by_group=by_group)
    held_failed, hf_cells = paired_difference(held, failed, by_group=by_group)
    primary = held
    return {
        "all": selected,
        "held": held,
        "failed": failed,
        "controls": compared,
        "quarters": len({record["q0"] for record in selected}),
        "groups": len({(record["q0"], record["group"]) for record in selected}),
        "origin": quarter_weighted(selected, "origin_magnitude"),
        "held_origin": quarter_weighted(held, "origin_magnitude"),
        "failed_origin": quarter_weighted(failed, "origin_magnitude"),
        "margin": quarter_weighted(primary, "hold_margin"),
        "leader": quarter_weighted(primary, "q1_spy_excess"),
        "failed_leader": quarter_weighted(failed, "q1_spy_excess"),
        "rank1_leader": quarter_weighted(
            [record for record in selected if record["rank21"] == 1], "q1_spy_excess"
        ),
        "rank23_leader": quarter_weighted(
            [record for record in selected if record["rank21"] in (2, 3)], "q1_spy_excess"
        ),
        "survival": quarter_weighted(primary, "q1_top3"),
        "drawdown": quarter_weighted(primary, "q1_max_drawdown"),
        "anchor": quarter_weighted(primary, "group_context.anchor_excess"),
        "member": quarter_weighted(primary, "group_context.member_median_excess"),
        "member_mean": quarter_weighted(primary, "group_context.member_mean_excess"),
        "participation": quarter_weighted(primary, "group_context.participation_delta"),
        "adequate": quarter_weighted(primary, "group_context.adequate"),
        "leader_control": leader_control,
        "lc_cells": lc_cells,
        "held_failed": held_failed,
        "hf_cells": hf_cells,
        "loo": (
            f"L {worst_loo(primary, 'q1_spy_excess')}; "
            f"G {worst_group_loo(primary)}"
        ),
        "leader_loo_min": minimum_loo(
            primary, "q1_spy_excess", (("name", "symbol"), ("sector", "group"))
        ),
        "anchor_loo_min": minimum_loo(
            primary, "group_context.anchor_excess", (("sector", "group"),)
        ),
        "member_loo_min": minimum_loo(
            primary, "group_context.member_median_excess", (("sector", "group"),)
        ),
    }


def cross_reading(summaries):
    validation, holdout = summaries["validation"], summaries["holdout"]
    required = (validation, holdout)
    if any(not item["held"] or item["adequate"] is None or item["adequate"] < 0.999 for item in required):
        return "inconclusive / localized"
    group_positive = all(item["anchor"] > 0 and item["member"] > 0 for item in required)
    leader_positive = all(item["leader"] > 0 for item in required)
    group_nonpositive = all(item["anchor"] <= 0 and item["member"] <= 0 for item in required)
    leader_nonpositive = all(item["leader"] <= 0 for item in required)
    group_robust = all(
        item["anchor_loo_min"] is not None
        and item["anchor_loo_min"] > 0
        and item["member_loo_min"] is not None
        and item["member_loo_min"] > 0
        for item in required
    )
    leader_robust = all(
        item["leader_loo_min"] is not None and item["leader_loo_min"] > 0
        for item in required
    )
    if group_positive and group_robust:
        return "group confirmed"
    if leader_positive and leader_robust and group_nonpositive:
        return "leader only"
    if leader_nonpositive and group_nonpositive:
        return "both failed"
    return "inconclusive / localized"


def build_theme(panel, cross_records, quarter_indices):
    grouped = defaultdict(list)
    for record in cross_records:
        if record["panel"] in ("A", "B"):
            grouped[(record["q0"], record["group"])].append(record)
    cutoff = date.fromisoformat(LIBRARY_CONTRACT_THROUGH)
    rows = []
    for (q0, sector), origins in sorted(grouped.items()):
        q1, q2 = next_q(q0), next_q(q0, 2)
        context = origins[0]["group_context"]
        leader_complete = all(finite(record["q1_spy_excess"]) and finite(record["q1_anchor_excess"]) for record in origins)
        leader_spy = median([record["q1_spy_excess"] for record in origins]) if leader_complete else None
        leader_anchor = median([record["q1_anchor_excess"] for record in origins]) if leader_complete else None
        if not leader_complete or not context["adequate"]:
            response = "unclassified"
        elif context["anchor_excess"] > 0 and context["member_median_excess"] > 0:
            response = "group confirmed"
        elif leader_spy > 0 and leader_anchor > 0 and context["anchor_excess"] <= 0 and context["member_median_excess"] <= 0:
            response = "leader only"
        elif leader_spy <= 0 and leader_anchor <= 0 and context["anchor_excess"] <= 0 and context["member_median_excess"] <= 0:
            response = "leader failed"
        else:
            response = "unclassified"

        q0_indices, q1_indices = quarter_indices[q0], quarter_indices[q1]
        peers = panel["memberships"][sector]
        arrays = {symbol: panel["prices"][symbol]["close"] for symbol in peers}
        _, q1_rank = rank_returns(peers, arrays, q0_indices[-1], q1_indices[-1])
        q1_top3 = {symbol for symbol, rank in q1_rank.items() if rank <= LEADER_COUNT}
        origin_names = {record["symbol"] for record in origins}
        handoff = sorted(q1_top3 - origin_names) if not (q1_top3 & origin_names) else []
        row = {
            "q0": q0,
            "q1": q1,
            "q2": q2,
            "group": sector,
            "origins": sorted(origin_names),
            "origin_types": "+".join(sorted({record["panel"] for record in origins})),
            "held_states": f"H{sum(r['decision'] == 'held' for r in origins)}/F{sum(r['decision'] == 'failed' for r in origins)}",
            "leader_spy": leader_spy,
            "leader_anchor": leader_anchor,
            "q1_top3_fraction": mean([record["q1_top3"] for record in origins]),
            "anchor_q1": context["anchor_excess"],
            "member_q1": context["member_median_excess"],
            "participation_q1": context["participation_delta"],
            "coverage": context["coverage"],
            "handoff": handoff,
            "response": response,
        }
        if q2 not in quarter_indices or not is_complete_quarter(
            q2, quarter_indices[q2], panel["dates"], cutoff
        ):
            row["fold"] = "right-censored"
            rows.append(row)
            continue

        q2_indices = quarter_indices[q2]
        spy_q2 = total_return(panel["anchors"][SPY], q1_indices[-1], q2_indices[-1])
        anchor_q2 = total_return(panel["anchors"][sector], q1_indices[-1], q2_indices[-1])
        nonorigins = [symbol for symbol in peers if symbol not in origin_names]
        q2_excess, q2_by_symbol = [], {}
        for symbol in nonorigins:
            value = total_return(panel["prices"][symbol]["close"], q1_indices[-1], q2_indices[-1])
            if value is not None and spy_q2 is not None:
                q2_excess.append(value - spy_q2)
                q2_by_symbol[symbol] = value - spy_q2
        _, q2_rank = rank_returns(peers, arrays, q1_indices[-1], q2_indices[-1])
        q2_top3 = {symbol for symbol, rank in q2_rank.items() if rank <= LEADER_COUNT}
        q2_coverage = len(q2_excess) / len(nonorigins) if nonorigins else 0.0
        row.update(
            fold=fold_for(q2),
            anchor_q2=None if anchor_q2 is None or spy_q2 is None else anchor_q2 - spy_q2,
            member_q2=median(q2_excess),
            member_mean_q2=mean(q2_excess),
            q2_max_drawdown=max_drawdown(panel["anchors"][sector], q1_indices[-1], q2_indices[-1]),
            leader_survival=mean([symbol in q2_top3 for symbol in origin_names]),
            leader_survival_by_name={symbol: symbol in q2_top3 for symbol in origin_names},
            handoff_survival=mean([symbol in q2_top3 for symbol in handoff]),
            participation_q2=mean([value > 0 for value in q2_excess]),
            q2_coverage=q2_coverage,
            q2_adequate=anchor_q2 is not None and spy_q2 is not None and q2_coverage >= MIN_GROUP_COVERAGE,
        )
        rows.append(row)
    return rows


def theme_weighted(rows, field):
    by_quarter = defaultdict(list)
    for row in rows:
        if finite(row.get(field)):
            by_quarter[row["q2"]].append(row[field])
    return mean([mean(values) for values in by_quarter.values()])


def theme_loo(rows, field):
    if len(rows) < 3:
        return "insufficient"
    candidates = []
    for sector in sorted({row["group"] for row in rows}):
        result = theme_weighted([row for row in rows if row["group"] != sector], field)
        if result is not None:
            candidates.append((result, sector))
    if not candidates:
        return "insufficient"
    result, sector = min(candidates)
    origin_candidates = []
    all_origins = sorted({name for row in rows for name in row.get("origins", [])})
    for origin in all_origins:
        by_quarter = defaultdict(list)
        for row in rows:
            states = [
                state
                for name, state in row.get("leader_survival_by_name", {}).items()
                if name != origin
            ]
            if states:
                by_quarter[row["q2"]].append(mean(states))
        value = mean([mean(values) for values in by_quarter.values()])
        if value is not None:
            origin_candidates.append((value, origin))
    origin_text = "origin insufficient"
    if origin_candidates:
        origin_value, origin = min(origin_candidates)
        origin_text = f"origin {origin}: {pct(origin_value)}"
    return f"sector {sector}: {pct(result)}; {origin_text}"


def theme_reading(response, by_fold):
    validation, holdout = by_fold.get("validation", []), by_fold.get("holdout", [])
    if not validation or not holdout or any(not row.get("q2_adequate") for row in validation + holdout):
        return "inconclusive / localized"
    anchor = [theme_weighted(validation, "anchor_q2"), theme_weighted(holdout, "anchor_q2")]
    member = [theme_weighted(validation, "member_q2"), theme_weighted(holdout, "member_q2")]
    if any(value is None for value in anchor + member):
        return "inconclusive / localized"
    if response == "group confirmed" and all(value > 0 for value in anchor + member):
        return "durable group confirmation"
    if response == "group confirmed" and all(value <= 0 for value in anchor + member):
        return "adverse or late broadening"
    if response == "leader only" and all(value <= 0 for value in anchor + member):
        return "leader-only response"
    return "inconclusive / localized"


def print_cross(panel, records, controls, current):
    print("\n## Data audit")
    print("| Contract | Receipts | Primary members | Membership overlap | Source range anomalies | Anchor close source |")
    print("| --- | ---: | ---: | ---: | ---: | --- |")
    print(
        f"| {DUAL_BASIS_CONTRACT_REVISION} through {LIBRARY_CONTRACT_THROUGH} ET | "
        f"{panel['eligible']}/{panel['eligible']} | {len(panel['members'])} | "
        f"{panel['duplicate_views']} | "
        f"{panel['range_anomalies']['over_1bp']} >1bp / {panel['range_anomalies']['over_1pct']} >1% | "
        f"`{ANCHOR_DATASET_ID}` legacy adjusted `close` |"
    )

    print("\n## Cross result ledger")
    print("| Panel | Fold | Held / failed; comparisons | Q0 | Leaders / groups | Origin | Hold margin | Q1 leader excess / top-3 | Q1 max DD | Anchor excess | Non-origin median / EW | Participation | Worst LOO | Reading |")
    print("| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |")
    all_summaries = {}
    for panel_name in ("A", "B", "C"):
        summaries = {
            fold: fold_summary(records, controls, panel_name, fold)
            for fold in ("development", "validation", "holdout")
        }
        all_summaries[panel_name] = summaries
        reading = cross_reading(summaries)
        for fold, result in summaries.items():
            comparisons = (
                f"H{len(result['held'])}/F{len(result['failed'])}; "
                f"L-C {pct(result['leader_control'])} n={result['lc_cells']}; "
                f"H-F {pct(result['held_failed'])} n={result['hf_cells']}"
            )
            leader = (
                f"H {pct(result['leader'])} / F {pct(result['failed_leader'])}; "
                f"top3 {pct(result['survival'])}; "
                f"R1 {pct(result['rank1_leader'])} / R2-3 {pct(result['rank23_leader'])}"
            )
            if panel_name == "A":
                origin = f"H {number(result['held_origin'])}z / F {number(result['failed_origin'])}z"
            else:
                origin = f"H {pct(result['held_origin'])} / F {pct(result['failed_origin'])}"
            print(
                f"| {panel_name} | {fold} | {comparisons} | {result['quarters']} | "
                f"{len(result['all'])}/{result['groups']}; cov {pct(result['adequate'])} | {origin} | "
                f"{pct(result['margin'])} | {leader} | {pct(result['drawdown'])} | "
                f"{pct(result['anchor'])} | M {pct(result['member'])} / EW {pct(result['member_mean'])} | "
                f"{pct(result['participation'])} | {result['loo']} | {reading} |"
            )

    print("\n## Origin and acceptance diagnostics")
    print("| Panel | Frozen leaders | Primary origin diagnostic | Close-held with intraday breach |")
    print("| --- | ---: | --- | ---: |")
    for panel_name in ("A", "B", "C"):
        selected = [record for record in records if record["panel"] == panel_name]
        close_held = [record for record in selected if record["decision"] == "held"]
        intraday_breach = (
            None
            if panel_name == "C"
            else mean(
                [
                    record.get("intraday_margin") is not None
                    and record["intraday_margin"] < 0
                    for record in close_held
                ]
            )
        )
        if panel_name == "A":
            diagnostic = (
                f"raw gap {pct(quarter_weighted(selected, 'raw_gap'))}; "
                f"breakaway {pct(quarter_weighted(selected, 'breakaway_gap'))}; "
                f"retained {number(quarter_weighted(selected, 'gap_retained_fraction'))}x"
            )
        elif panel_name == "B":
            diagnostic = (
                f"Q0-to-day21 anchor excess {pct(quarter_weighted(selected, 'origin_magnitude'))}; "
                f"positive relative days {pct(quarter_weighted(selected, 'positive_relative_day_fraction'))}"
            )
        else:
            entrants = Counter(
                name
                for record in selected
                for name in record["group_context"]["new_top3_members"]
            )
            entrant_text = ", ".join(
                f"{name}({count})" for name, count in entrants.most_common(3)
            ) or "none"
            diagnostic = (
                f"Q0-to-day21 SPY excess {pct(quarter_weighted(selected, 'origin_magnitude'))}; "
                f"most frequent new Q1 top-three members {entrant_text}"
            )
        print(f"| {panel_name} | {len(selected)} | {diagnostic} | {pct(intraday_breach)} |")

    print("\n## Current observation view")
    print("| As of / Q0 | Subject | Group | Panel | Origin | Base | Current margin | Rank | State | Coverage |")
    print("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: |")
    if not current:
        print("| none | | | | | | | | | |")
    for record in sorted(current, key=lambda item: (item["panel"], item["group"], item["rank21"])):
        origin = (
            f"{number(record['origin_magnitude'])}z"
            if record["panel"] == "A"
            else pct(record["origin_magnitude"])
        )
        print(
            f"| {panel['dates'][-1]} / {qlabel(record['q0'])} | {record['symbol']} | "
            f"{record['group']} | {record['panel']} | {origin} | "
            f"{number(record['base'])} | {pct(record['hold_margin'])} | "
            f"{record.get('q0_end_rank', 'NA')} | {record.get('observation_state', record['decision'])} | "
            f"{pct(record.get('hold_coverage'))} |"
        )

    print("\n## Frozen NVDA / MU traces")
    print("| Name | Q0 / panel / group | Origin date | Rank 21 | Hold margin | Q0 decision | Q1 excess / rank |")
    print("| --- | --- | --- | ---: | ---: | --- | --- |")
    traces = [record for record in records if record["symbol"] in ("NVDA", "MU")]
    if not traces:
        print("| none | | | | | | |")
    for record in sorted(traces, key=lambda item: (item["symbol"], item["q0"], item["panel"])):
        print(
            f"| {record['symbol']} | {qlabel(record['q0'])} / {record['panel']} / {record['group']} | "
            f"{record['origin_date']} | {record['rank21']} | {pct(record['hold_margin'])} | "
            f"{record['decision']} | {pct(record['q1_spy_excess'])} / {record.get('q1_rank', 'NA')} |"
        )
    return all_summaries


def print_theme(rows, gate_open):
    print(
        "\nTheme gate: "
        + ("earned by the frozen Cross reading." if gate_open else "not earned; Q2 rows are diagnostic only and authorize no claim.")
    )
    print("\n## Theme Q1 response inventory")
    print("| Q1 response | Episodes | Adequate Q1 | Leader excess / top-3 | Anchor excess | Non-origin median | Participation change | Handoffs |")
    print("| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |")
    for response in ("group confirmed", "leader only", "leader failed", "unclassified"):
        selected = [row for row in rows if row["response"] == response]
        print(
            f"| {response} | {len(selected)} | {sum(row['coverage'] >= MIN_GROUP_COVERAGE for row in selected)} | "
            f"{pct(mean([row['leader_spy'] for row in selected]))} / "
            f"{pct(mean([row['q1_top3_fraction'] for row in selected]))} | "
            f"{pct(mean([row['anchor_q1'] for row in selected]))} | "
            f"{pct(mean([row['member_q1'] for row in selected]))} | "
            f"{pct(mean([row['participation_q1'] for row in selected]))} | "
            f"{sum(bool(row['handoff']) for row in selected)} |"
        )

    print("\n## Theme Q2 result ledger")
    print("| Q1 response | Fold | Quarters / sectors | Q2 anchor | Q2 non-origin median / EW | Q2 max DD | Leader / handoff survival | Participation Q1 delta -> Q2 level | Worst LOO | Reading |")
    print("| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- | --- |")
    for response in ("group confirmed", "leader only", "leader failed", "unclassified"):
        by_fold = {
            fold: [row for row in rows if row["response"] == response and row.get("fold") == fold]
            for fold in ("development", "validation", "holdout")
        }
        reading = theme_reading(response, by_fold)
        for fold, selected in by_fold.items():
            if not selected:
                continue
            print(
                f"| {response} | {fold} | {len({row['q2'] for row in selected})}/{len(selected)} | "
                f"{pct(theme_weighted(selected, 'anchor_q2'))} | "
                f"M {pct(theme_weighted(selected, 'member_q2'))} / "
                f"EW {pct(theme_weighted(selected, 'member_mean_q2'))} | "
                f"{pct(theme_weighted(selected, 'q2_max_drawdown'))} | "
                f"{pct(theme_weighted(selected, 'leader_survival'))} / "
                f"{pct(theme_weighted(selected, 'handoff_survival'))} | "
                f"{pct(theme_weighted(selected, 'participation_q1'))} -> "
                f"{pct(theme_weighted(selected, 'participation_q2'))} | "
                f"{theme_loo(selected, 'anchor_q2')} | {reading} |"
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
    leaders, controls, current, quarter_indices = run_cross(panel)
    cross_summaries = print_cross(panel, leaders, controls, current)
    theme_gate = any(
        cross_reading(cross_summaries[panel_name]) in ("group confirmed", "leader only")
        for panel_name in ("A", "B")
    )
    theme = build_theme(panel, leaders, quarter_indices)
    print_theme(theme, theme_gate)
    print(
        f"\nCompleted: {len(leaders)} frozen Cross leaders, {len(controls)} matched rank-4/10 controls, "
        f"and {len(theme)} frozen sector-quarter Theme episodes."
    )


if __name__ == "__main__":
    main()
