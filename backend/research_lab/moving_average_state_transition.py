"""H-XSEC-S2-003 Development-only moving-average state experiment.

Disposable, read-only research.  This first release deliberately truncates the
price panel at 2018-12-31; Validation and Holdout are not callable here yet.

Run:
    .venv/Scripts/python.exe -m backend.research_lab.moving_average_state_transition
"""

from __future__ import annotations

import argparse
import bisect
import math
import statistics
from collections import defaultdict
from datetime import date

import numpy as np
from scipy import stats

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg
from backend.research_lab.price_volume_factor_screen import load_panel


END = date(2018, 12, 31)
HORIZONS = (5, 10, 21, 42, 63, 126)
CHECKPOINTS = np.array(HORIZONS) - 1
EVENTS = ("E1", "E5", "EB20", "ES")
SIGNALS = ("D4", "MAD")
VIEWS = ("Broad", "Within-sector")
INDEXES = ("SPY", "QQQ", "DIA", "IWM")
SECTORS = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")
PRIMARY_FLOOR = 25_000_000.0
SENSITIVITY_FLOOR = 10_000_000.0
MIN_PRICE = 5.0
MIN_BROAD = 30
MIN_SECTOR = 10
MIN_TAIL = 2
MIN_CONTROLS = 3
PERMUTATIONS = 10_000
SEED = 20260829
ANCHOR_DATASET_ID = "real-macro-0f184797-d738-4ecd-a615-83b0020c5753"


def finite(value):
    return value is not None and math.isfinite(float(value))


def number(value, digits=3):
    return "NA" if not finite(value) else f"{float(value):+.{digits}f}"


def pct(value, digits=2):
    return "NA" if not finite(value) else f"{100.0 * float(value):+.{digits}f}%"


def pnumber(value):
    if not finite(value):
        return "insufficient"
    return "<.0001" if float(value) < 0.0001 else f"{float(value):.4f}"


def rolling_mean(values, window):
    values = np.asarray(values, dtype=float)
    good = np.isfinite(values) & (values > 0)
    sums = np.concatenate(([0.0], np.cumsum(np.where(good, values, 0.0))))
    counts = np.concatenate(([0], np.cumsum(good.astype(np.int32))))
    result = np.full(len(values), np.nan, dtype=float)
    total = sums[window:] - sums[:-window]
    count = counts[window:] - counts[:-window]
    target = result[window - 1 :]
    target[count == window] = total[count == window] / window
    return result


def rolling_median_dollar_volume(raw_close, volume):
    dollar_volume = np.asarray(raw_close, dtype=float) * np.asarray(volume, dtype=float)
    result = np.full(len(dollar_volume), np.nan, dtype=float)
    if len(dollar_volume) < 21:
        return result
    windows = np.lib.stride_tricks.sliding_window_view(dollar_volume, 21)
    good = np.all(np.isfinite(windows) & (windows > 0), axis=1)
    medians = np.full(len(windows), np.nan, dtype=float)
    medians[good] = np.median(windows[good], axis=1)
    result[20:] = medians
    return result


def consecutive_age(state):
    result = np.zeros(len(state), dtype=np.int16)
    age = 0
    for index, active in enumerate(state):
        age = age + 1 if active else 0
        result[index] = min(age, np.iinfo(np.int16).max)
    return result


def event_flags(close, observable, a4, s4, age_a):
    flags = {event: np.zeros(len(close), dtype=bool) for event in EVENTS}
    seen_breakout = False
    seen_ordered = False
    valid_episode = False
    for index in range(len(close)):
        if not observable[index] or not a4[index]:
            seen_breakout = False
            seen_ordered = False
            valid_episode = False
            continue
        genuine_start = index > 0 and observable[index - 1] and not a4[index - 1]
        if genuine_start:
            valid_episode = True
            seen_breakout = False
            seen_ordered = False
            flags["E1"][index] = True
        elif index == 0 or not observable[index - 1]:
            valid_episode = False
        if not valid_episode:
            continue
        if age_a[index] == 5:
            flags["E5"][index] = True
        if not seen_breakout and index >= 20:
            prior = close[index - 20 : index]
            if np.all(np.isfinite(prior) & (prior > 0)) and close[index] > np.max(prior):
                flags["EB20"][index] = True
                seen_breakout = True
        if not seen_ordered and s4[index]:
            flags["ES"][index] = True
            seen_ordered = True
    return flags


def price_features(close):
    close = np.asarray(close, dtype=float)
    means = {window: rolling_mean(close, window) for window in (20, 50, 100, 200)}
    ready = np.isfinite(close) & (close > 0)
    for average in means.values():
        ready &= np.isfinite(average) & (average > 0)
    d4 = np.full(len(close), np.nan, dtype=float)
    mad = np.full(len(close), np.nan, dtype=float)
    if np.any(ready):
        distances = np.vstack([np.log(close / means[window]) for window in (20, 50, 100, 200)])
        d4[ready] = np.mean(distances[:, ready], axis=0)
        mad[ready] = np.log(means[20][ready] / means[200][ready])
    a4 = ready.copy()
    s4 = ready.copy()
    for window in (20, 50, 100, 200):
        a4 &= close > means[window]
    s4 &= close > means[20]
    s4 &= means[20] > means[50]
    s4 &= means[50] > means[100]
    s4 &= means[100] > means[200]
    age_a = consecutive_age(a4)
    age_s = consecutive_age(s4)
    return {
        "D4": d4,
        "MAD": mad,
        "A4": a4,
        "S4": s4,
        "age_A4": age_a,
        "age_S4": age_s,
        "events": event_flags(close, ready, a4, s4, age_a),
        "means": means,
    }


def realized_volatility(close):
    close = np.asarray(close, dtype=float)
    returns = np.full(len(close), np.nan, dtype=float)
    valid = np.isfinite(close[1:]) & np.isfinite(close[:-1]) & (close[1:] > 0) & (close[:-1] > 0)
    returns[1:][valid] = np.log(close[1:][valid] / close[:-1][valid])
    result = np.full(len(close), np.nan, dtype=float)
    if len(close) < 64:
        return result
    windows = np.lib.stride_tricks.sliding_window_view(returns[1:], 63)
    good = np.all(np.isfinite(windows), axis=1)
    values = np.full(len(windows), np.nan, dtype=float)
    values[good] = np.std(windows[good], axis=1, ddof=1)
    result[63:] = values
    return result


def expanding_quintile(values):
    result = np.full(len(values), -1, dtype=np.int8)
    prior = []
    for index, value in enumerate(values):
        if not finite(value):
            continue
        if len(prior) >= 252:
            percentile = bisect.bisect_right(prior, float(value)) / len(prior)
            result[index] = min(4, int(5 * percentile))
        bisect.insort(prior, float(value))
    return result


def half_year(day_string):
    parsed = date.fromisoformat(day_string)
    return parsed.year * 2 + (1 if parsed.month >= 7 else 0)


def average_quintiles(values):
    values = np.asarray(values, dtype=float)
    ranks = stats.rankdata(values, method="average") / len(values)
    return np.minimum(4, np.ceil(5 * ranks).astype(int) - 1)


def cluster_t(values, blocks):
    values = np.asarray(values, dtype=float)
    good = np.isfinite(values)
    values = values[good]
    blocks = np.asarray(blocks)[good]
    unique = np.unique(blocks)
    if len(values) < 30 or len(unique) < 8:
        return None
    estimate = float(np.mean(values))
    scores = np.array([np.sum(values[blocks == block] - estimate) for block in unique])
    variance = len(unique) / (len(unique) - 1.0) * float(np.sum(scores * scores)) / (len(values) ** 2)
    if variance <= 1e-18:
        return None
    return estimate / math.sqrt(variance)


def family_signs(rows):
    blocks = sorted({half_year(day) for row in rows.values() for day in row["dates"]})
    rng = np.random.default_rng(SEED)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(PERMUTATIONS, len(blocks)))
    return blocks, {block: index for index, block in enumerate(blocks)}, signs


def curve_p(matrix, dates, global_blocks, block_lookup, signs):
    matrix = np.asarray(matrix, dtype=float)
    date_blocks = np.array([half_year(day) for day in dates])
    observed = [cluster_t(matrix[:, column], date_blocks) for column in range(matrix.shape[1])]
    if not any(finite(value) for value in observed):
        return None, None, observed, 0, len(dates)
    observed_max = max(float(value) for value in observed if finite(value))
    null_max = np.full(PERMUTATIONS, -np.inf, dtype=float)
    usable_block_count = 0
    for column in range(matrix.shape[1]):
        values = matrix[:, column]
        good = np.isfinite(values)
        if int(np.sum(good)) < 30:
            continue
        selected_values = values[good]
        selected_blocks = date_blocks[good]
        unique = np.unique(selected_blocks)
        if len(unique) < 8:
            continue
        usable_block_count = max(usable_block_count, len(unique))
        columns = np.array([block_lookup[int(block)] for block in unique], dtype=int)
        block_sums = np.array([np.sum(selected_values[selected_blocks == block]) for block in unique])
        block_counts = np.array([np.sum(selected_blocks == block) for block in unique], dtype=float)
        draw_signs = signs[:, columns]
        draw_sum = draw_signs @ block_sums
        draw_mean = draw_sum / len(selected_values)
        scores = draw_signs * block_sums - draw_mean[:, None] * block_counts
        variance = len(unique) / (len(unique) - 1.0) * np.sum(scores * scores, axis=1) / (len(selected_values) ** 2)
        draw_t = np.divide(
            draw_mean,
            np.sqrt(variance),
            out=np.zeros_like(draw_mean),
            where=variance > 1e-18,
        )
        null_max = np.maximum(null_max, draw_t)
    if usable_block_count < 8:
        return None, observed_max, observed, usable_block_count, len(dates)
    p_value = (1.0 + float(np.sum(null_max >= observed_max))) / (PERMUTATIONS + 1.0)
    return p_value, observed_max, observed, usable_block_count, len(dates)


def apply_family_inference(rows):
    global_blocks, lookup, signs = family_signs(rows)
    for row in rows.values():
        result = curve_p(row["matrix"], row["dates"], global_blocks, lookup, signs)
        row["p"], row["max_t"], row["t"], row["blocks"], row["n_dates"] = result
        row["q"] = None
    family_keys = list(rows)
    if family_keys:
        adjusted, _ = benjamini_hochberg(
            [rows[key]["p"] if finite(rows[key]["p"]) else 1.0 for key in family_keys]
        )
        for key, value in zip(family_keys, adjusted):
            rows[key]["q"] = float(value)
    return rows


def load_references(connection, dates):
    date_index = {day: index for index, day in enumerate(dates)}
    references = {}
    for symbol in dict.fromkeys((*SECTORS, *INDEXES)):
        identities = connection.execute(
            "SELECT security_id FROM securities WHERE primary_symbol = ? ORDER BY security_id",
            (symbol,),
        ).fetchall()
        if len(identities) != 1:
            raise RuntimeError(f"reference identity is not unique: {symbol} ({len(identities)})")
        values = np.full(len(dates), np.nan, dtype=float)
        for row in connection.execute(
            """SELECT time, COALESCE(adjusted_close, close) AS close
               FROM symbol_bars
               WHERE dataset_snapshot_id = ? AND security_id = ?
               ORDER BY time""",
            (ANCHOR_DATASET_ID, identities[0]["security_id"]),
        ):
            index = date_index.get(row["time"])
            if index is not None:
                values[index] = row["close"]
        references[symbol] = values
    return references


def prepare(panel):
    end_index = max(index for index, day in enumerate(panel["dates"]) if date.fromisoformat(day) <= END)
    dates = panel["dates"][: end_index + 1]
    names = sorted(panel["sector_by_symbol"])
    missing = [symbol for symbol in (*SECTORS, *INDEXES) if symbol not in panel["reference_arrays"]]
    if missing:
        raise RuntimeError(f"reference ETFs missing from Stage 2 panel: {', '.join(missing)}")

    close = np.vstack([panel["arrays"][symbol]["close"][: end_index + 1] for symbol in names])
    raw_close = np.vstack([panel["arrays"][symbol]["raw_close"][: end_index + 1] for symbol in names])
    volume = np.vstack([panel["arrays"][symbol]["volume"][: end_index + 1] for symbol in names])
    n_names, n_dates = close.shape
    d4 = np.full((n_names, n_dates), np.nan, dtype=np.float32)
    mad = np.full((n_names, n_dates), np.nan, dtype=np.float32)
    adv = np.full((n_names, n_dates), np.nan, dtype=np.float64)
    a4 = np.zeros((n_names, n_dates), dtype=bool)
    s4 = np.zeros((n_names, n_dates), dtype=bool)
    age_a = np.zeros((n_names, n_dates), dtype=np.int16)
    age_s = np.zeros((n_names, n_dates), dtype=np.int16)
    flags = {event: np.zeros((n_names, n_dates), dtype=bool) for event in EVENTS}
    for row in range(n_names):
        feature = price_features(close[row])
        d4[row] = feature["D4"]
        mad[row] = feature["MAD"]
        a4[row] = feature["A4"]
        s4[row] = feature["S4"]
        age_a[row] = feature["age_A4"]
        age_s[row] = feature["age_S4"]
        adv[row] = rolling_median_dollar_volume(raw_close[row], volume[row])
        for event in EVENTS:
            flags[event][row] = feature["events"][event]

    references = {}
    for symbol in dict.fromkeys((*SECTORS, *INDEXES)):
        series = np.asarray(panel["reference_arrays"][symbol][: end_index + 1], dtype=float)
        references[symbol] = {"close": series, **price_features(series)}
    sector_codes = np.array([SECTORS.index(panel["sector_by_symbol"][symbol]) for symbol in names], dtype=np.int8)
    reference_ready = np.zeros((n_names, n_dates), dtype=bool)
    for sector_code, sector in enumerate(SECTORS):
        reference_ready[sector_codes == sector_code] = np.isfinite(references[sector]["D4"])

    spy = references["SPY"]
    regime = np.full(n_dates, "Unavailable", dtype=object)
    ready = np.isfinite(spy["close"]) & np.isfinite(spy["means"][50]) & np.isfinite(spy["means"][200])
    above_50 = spy["close"] > spy["means"][50]
    fifty_above_200 = spy["means"][50] > spy["means"][200]
    regime[ready & above_50 & fifty_above_200] = "Bull"
    regime[ready & ~above_50 & fifty_above_200] = "Correction"
    regime[ready & above_50 & ~fifty_above_200] = "Repair"
    regime[ready & ~above_50 & ~fifty_above_200] = "Bear"

    return {
        "dates": dates,
        "names": names,
        "name_index": {symbol: index for index, symbol in enumerate(names)},
        "close": close,
        "raw_close": raw_close,
        "volume": volume,
        "D4": d4,
        "MAD": mad,
        "ADV": adv,
        "A4": a4,
        "S4": s4,
        "age_A4": age_a,
        "age_S4": age_s,
        "events": flags,
        "sector_codes": sector_codes,
        "references": references,
        "reference_ready": reference_ready,
        "regime": regime,
        "accepted": panel["accepted"],
        "all_symbols": len(panel["symbols"]),
    }


def eligibility(model, floor):
    return (
        np.isfinite(model["D4"])
        & np.isfinite(model["MAD"])
        & np.isfinite(model["raw_close"])
        & (model["raw_close"] >= MIN_PRICE)
        & np.isfinite(model["ADV"])
        & (model["ADV"] >= floor)
        & model["reference_ready"]
    )


def month_ends(dates, maximum_signal):
    result = {}
    for index, day in enumerate(dates):
        parsed = date.fromisoformat(day)
        result[(parsed.year, parsed.month)] = index
    return [index for index in result.values() if index <= maximum_signal]


def forward_paths(close, signal):
    entry = signal + 1
    window = close[:, entry : entry + 127]
    good = np.all(np.isfinite(window) & (window > 0), axis=1)
    paths = np.full((len(close), 126), np.nan, dtype=float)
    mdd = np.full((len(close), 126), np.nan, dtype=float)
    if np.any(good):
        wealth = window[good] / window[good, :1]
        paths[good] = np.log(wealth[:, 1:])
        drawdown = wealth / np.maximum.accumulate(wealth, axis=1) - 1.0
        mdd[good] = np.minimum.accumulate(drawdown, axis=1)[:, 1:]
    return paths, mdd, good


def one_path(close, signal):
    entry = signal + 1
    window = close[entry : entry + 127]
    if len(window) != 127 or not np.all(np.isfinite(window) & (window > 0)):
        return None
    return np.log(window[1:] / window[0])


def continuous_cell(signal_values, outcomes, sectors, view):
    if view == "Broad":
        if len(signal_values) < MIN_BROAD:
            return None
        ic = stats.spearmanr(signal_values, outcomes).statistic
        quintile = average_quintiles(signal_values)
        high = outcomes[quintile == 4]
        low = outcomes[quintile == 0]
        if not finite(ic) or len(high) < MIN_TAIL or len(low) < MIN_TAIL:
            return None
        return float(ic), float(np.mean(high) - np.mean(low)), len(signal_values), 1

    sector_ics, sector_spreads, used = [], [], 0
    for sector in range(len(SECTORS)):
        selected = sectors == sector
        if int(np.sum(selected)) < MIN_SECTOR:
            continue
        x, y = signal_values[selected], outcomes[selected]
        quintile = average_quintiles(x)
        high, low = y[quintile == 4], y[quintile == 0]
        if len(high) < MIN_TAIL or len(low) < MIN_TAIL:
            continue
        ic = stats.spearmanr(x, y).statistic
        if not finite(ic):
            continue
        sector_ics.append(float(ic))
        sector_spreads.append(float(np.mean(high) - np.mean(low)))
        used += len(x)
    if not sector_ics:
        return None
    return statistics.fmean(sector_ics), statistics.fmean(sector_spreads), used, len(sector_ics)


def analyze_continuous(model, eligible):
    maximum_signal = len(model["dates"]) - 128
    formations = month_ends(model["dates"], maximum_signal)
    observations = {(view, signal): [] for view in VIEWS for signal in SIGNALS}
    for formation in formations:
        paths, _mdd, full = forward_paths(model["close"], formation)
        selected = eligible[:, formation] & full
        indices = np.flatnonzero(selected)
        if len(indices) < MIN_BROAD:
            continue
        for signal in SIGNALS:
            x = np.asarray(model[signal][indices, formation], dtype=float)
            for view in VIEWS:
                ic_values, spreads, names, sectors_used = [], [], [], []
                for checkpoint in CHECKPOINTS:
                    cell = continuous_cell(
                        x,
                        paths[indices, checkpoint],
                        model["sector_codes"][indices],
                        view,
                    )
                    if cell is None:
                        break
                    ic_values.append(cell[0])
                    spreads.append(cell[1])
                    names.append(cell[2])
                    sectors_used.append(cell[3])
                if len(ic_values) == len(HORIZONS):
                    observations[(view, signal)].append(
                        {
                            "date": model["dates"][formation],
                            "ic": np.array(ic_values),
                            "spread": np.array(spreads),
                            "names": statistics.fmean(names),
                            "sectors": statistics.fmean(sectors_used),
                        }
                    )
    rows = {}
    for key, values in observations.items():
        rows[key] = {
            "dates": [row["date"] for row in values],
            "matrix": np.vstack([row["ic"] for row in values]) if values else np.empty((0, len(HORIZONS))),
            "spread_matrix": np.vstack([row["spread"] for row in values]) if values else np.empty((0, len(HORIZONS))),
            "names": statistics.fmean(row["names"] for row in values) if values else None,
            "sectors": statistics.fmean(row["sectors"] for row in values) if values else None,
        }
    return apply_family_inference(rows), formations


def date_quintiles(model, eligible_today, signal):
    q_d4 = np.full(len(model["names"]), -1, dtype=np.int8)
    q_liquidity = np.full(len(model["names"]), -1, dtype=np.int8)
    for sector in range(len(SECTORS)):
        indices = np.flatnonzero(eligible_today & (model["sector_codes"] == sector))
        if len(indices) == 0:
            continue
        q_d4[indices] = average_quintiles(model["D4"][indices, signal])
        q_liquidity[indices] = average_quintiles(model["ADV"][indices, signal])
    return q_d4, q_liquidity


def breadth_label(value):
    if not finite(value):
        return "Unavailable"
    if value <= 0.20:
        return "Isolated"
    if value <= 0.50:
        return "Building"
    return "Broad"


def analyze_events(model, eligible, primary_context=None):
    maximum_signal = len(model["dates"]) - 128
    cohorts = {event: [] for event in EVENTS}
    coverage = {
        event: {"dates": set(), "names": 0, "sectors": np.zeros(len(SECTORS), dtype=int)} for event in EVENTS
    }
    overlap_cells = 0
    unique_event_cells = 0
    daily_eligible = []
    for signal in range(199, maximum_signal + 1):
        eligible_today = eligible[:, signal]
        daily_eligible.append(int(np.sum(eligible_today)))
        event_any = np.zeros(len(model["names"]), dtype=bool)
        for event in EVENTS:
            event_any |= model["events"][event][:, signal] & eligible_today
        if not np.any(event_any):
            continue

        paths, mdd, full = forward_paths(model["close"], signal)
        q_d4, q_liquidity = date_quintiles(model, eligible_today, signal)
        spy_path = one_path(model["references"]["SPY"]["close"], signal)
        sector_paths = {sector: one_path(model["references"][sector]["close"], signal) for sector in SECTORS}
        event_count = np.zeros(len(model["names"]), dtype=np.int8)
        for event in EVENTS:
            event_count += (model["events"][event][:, signal] & eligible_today & full).astype(np.int8)
        overlap_cells += int(np.sum(event_count >= 2))
        unique_event_cells += int(np.sum(event_count >= 1))

        context_base = eligible_today if primary_context is None else primary_context[:, signal]
        breadth = float(np.mean(model["A4"][context_base, signal])) if np.any(context_base) else None
        for event in EVENTS:
            firing = model["events"][event][:, signal] & eligible_today & full
            event_indices = np.flatnonzero(firing)
            if len(event_indices) == 0 or spy_path is None:
                continue
            absolute_paths, spy_paths, sector_relative = [], [], []
            deltas, event_mdds, matched_event_mdds, control_mdds = [], [], [], []
            state_lives, state_failures, state_exit_returns, state_exit_holds = [], [], [], []
            matched_names = 0
            used_sectors = []
            event_set = set(event_indices.tolist())
            relevant_age = model["age_S4"] if event == "ES" else model["age_A4"]
            relevant_state = model["S4"] if event == "ES" else model["A4"]
            for stock in event_indices:
                sector_code = int(model["sector_codes"][stock])
                sector = SECTORS[sector_code]
                sector_path = sector_paths[sector]
                if sector_path is None:
                    continue
                stock_c = paths[stock] - sector_path
                absolute_paths.append(paths[stock])
                spy_paths.append(paths[stock] - spy_path)
                sector_relative.append(stock_c)
                used_sectors.append(sector_code)
                event_mdds.append(mdd[stock])

                controls = (
                    eligible_today
                    & full
                    & (model["sector_codes"] == sector_code)
                    & (relevant_age[:, signal] >= 21)
                    & (q_d4 == q_d4[stock])
                    & (q_liquidity == q_liquidity[stock])
                    & ~model["events"][event][:, signal]
                )
                if event_set:
                    controls[np.fromiter(event_set, dtype=int)] = False
                control_indices = np.flatnonzero(controls)
                if len(control_indices) >= MIN_CONTROLS:
                    control_c = np.mean(paths[control_indices] - sector_path, axis=0)
                    deltas.append(stock_c - control_c)
                    matched_event_mdds.append(mdd[stock])
                    control_mdds.append(np.mean(mdd[control_indices], axis=0))
                    matched_names += 1

                future_state = relevant_state[stock, signal + 1 : signal + 127]
                failures = np.flatnonzero(~future_state)
                hold = int(failures[0] + 1) if len(failures) else 126
                state_lives.append(hold)
                state_failures.append(bool(len(failures)))
                state_exit_holds.append(hold)
                state_exit_returns.append(float(stock_c[hold - 1]))

            if not sector_relative:
                continue
            coverage[event]["dates"].add(model["dates"][signal])
            coverage[event]["names"] += len(sector_relative)
            for sector_code in used_sectors:
                coverage[event]["sectors"][sector_code] += 1
            cohorts[event].append(
                {
                    "date": model["dates"][signal],
                    "names": len(sector_relative),
                    "matched": matched_names,
                    "absolute": np.mean(absolute_paths, axis=0),
                    "spy": np.mean(spy_paths, axis=0),
                    "C": np.mean(sector_relative, axis=0),
                    "Delta": np.mean(deltas, axis=0) if deltas else np.full(126, np.nan),
                    "all_mdd": np.mean(event_mdds, axis=0),
                    "mdd": np.mean(matched_event_mdds, axis=0) if matched_event_mdds else np.full(126, np.nan),
                    "control_mdd": np.mean(control_mdds, axis=0) if control_mdds else np.full(126, np.nan),
                    "state_lives": state_lives,
                    "state_failures": state_failures,
                    "state_exit": statistics.fmean(state_exit_returns),
                    "state_hold": statistics.fmean(state_exit_holds),
                    "regime": model["regime"][signal],
                    "breadth": breadth_label(breadth),
                }
            )

    rows = {}
    for event, values in cohorts.items():
        rows[event] = {
            "dates": [row["date"] for row in values],
            "matrix": np.vstack([row["Delta"][CHECKPOINTS] for row in values]) if values else np.empty((0, 6)),
            "cohorts": values,
        }
    apply_family_inference(rows)
    coverage["mean_eligible"] = statistics.fmean(daily_eligible) if daily_eligible else None
    analyzed = slice(199, maximum_signal + 1)
    coverage["mean_eligible_sector"] = np.array(
        [
            np.mean(np.sum(eligible[model["sector_codes"] == sector, analyzed], axis=0))
            for sector in range(len(SECTORS))
        ]
    )
    coverage["overlap"] = overlap_cells
    coverage["event_cells"] = unique_event_cells
    return rows, coverage


def nan_column_mean(matrix):
    matrix = np.asarray(matrix, dtype=float)
    result = []
    for column in range(matrix.shape[1]):
        values = matrix[:, column]
        values = values[np.isfinite(values)]
        result.append(float(np.mean(values)) if len(values) else np.nan)
    return np.array(result)


def kaplan_meier(lives, failures):
    lives = np.asarray(lives, dtype=int)
    failures = np.asarray(failures, dtype=bool)
    survival = 1.0
    curve = np.full(126, np.nan, dtype=float)
    for day in range(1, 127):
        at_risk = int(np.sum(lives >= day))
        events = int(np.sum((lives == day) & failures))
        if at_risk:
            survival *= 1.0 - events / at_risk
        curve[day - 1] = survival
    return curve


def summarize_event_rows(rows):
    summaries = {}
    for event, row in rows.items():
        cohorts = row["cohorts"]
        if not cohorts:
            summaries[event] = {"p": row["p"], "q": row["q"], "dates": 0, "names": 0}
            continue
        summary = {
            "p": row["p"],
            "q": row["q"],
            "blocks": row["blocks"],
            "dates": len(cohorts),
            "names": sum(item["names"] for item in cohorts),
            "matched": sum(item["matched"] for item in cohorts),
            "delta_dates": sum(np.all(np.isfinite(item["Delta"])) for item in cohorts),
        }
        for key in ("absolute", "spy", "C", "Delta"):
            summary[key] = nan_column_mean(np.vstack([item[key] for item in cohorts]))
        lives = [life for item in cohorts for life in item["state_lives"]]
        failures = [failure for item in cohorts for failure in item["state_failures"]]
        summary["survival"] = kaplan_meier(lives, failures)
        summary["all_mdd"] = np.nanmedian(np.vstack([item["all_mdd"] for item in cohorts]), axis=0)
        summary["mdd"] = np.nanmedian(np.vstack([item["mdd"] for item in cohorts]), axis=0)
        summary["control_mdd"] = np.nanmedian(np.vstack([item["control_mdd"] for item in cohorts]), axis=0)
        summary["state_exit"] = statistics.fmean(item["state_exit"] for item in cohorts)
        summary["state_hold"] = statistics.fmean(item["state_hold"] for item in cohorts)
        curve = summary["C"]
        endpoints = (0, 5, 10, 21, 42, 63, 126)
        summary["marginal"] = np.array([curve[endpoints[i + 1] - 1] - (0.0 if i == 0 else curve[endpoints[i] - 1]) for i in range(6)])
        summary["marginal_rate"] = summary["marginal"] / np.array([5, 5, 11, 21, 21, 63])
        if np.any(np.isfinite(curve)) and float(np.nanmax(curve)) > 0:
            peak = float(np.nanmax(curve))
            peak_day = int(np.nanargmax(curve) + 1)
            t50 = int(np.flatnonzero(curve >= 0.5 * peak)[0] + 1)
            giveback = np.flatnonzero(curve[peak_day:] <= 0.5 * peak)
            giveback_day = int(peak_day + giveback[0] + 1) if len(giveback) else None
            summary["peak"] = peak
            summary["peak_day"] = peak_day
            summary["t50"] = t50
            summary["giveback"] = giveback_day
        else:
            summary.update({"peak": None, "peak_day": None, "t50": None, "giveback": None})
        survival = summary["survival"]
        median_failure = np.flatnonzero(survival <= 0.5)
        summary["state_median"] = int(median_failure[0] + 1) if len(median_failure) else None
        exhaustion = None
        for index in range(5):
            if summary["marginal"][index] <= 0 and summary["marginal"][index + 1] <= 0:
                exhaustion = f"blocks {index + 1}-{index + 2}"
                break
        summary["exhaustion"] = exhaustion
        summaries[event] = summary
    return summaries


def context_rows(event_rows):
    result = []
    for event, row in event_rows.items():
        for axis in ("regime", "breadth"):
            groups = defaultdict(list)
            for cohort in row["cohorts"]:
                groups[cohort[axis]].append(cohort["C"][CHECKPOINTS])
            for label, values in sorted(groups.items()):
                matrix = np.vstack(values)
                result.append((axis, label, event, len(values), nan_column_mean(matrix)))
    return result


def analyze_indexes(model):
    result = {}
    maximum_signal = len(model["dates"]) - 128
    for symbol in INDEXES:
        reference = model["references"][symbol]
        vol_q = expanding_quintile(realized_volatility(reference["close"]))
        for event in EVENTS:
            candidate_paths = defaultdict(list)
            event_paths, delta_paths, event_dates = [], [], []
            relevant_age = reference["age_S4"] if event == "ES" else reference["age_A4"]
            for signal in range(199, maximum_signal + 1):
                path = one_path(reference["close"], signal)
                key = (model["regime"][signal], int(vol_q[signal]))
                valid_key = key[0] != "Unavailable" and key[1] >= 0
                if reference["events"][event][signal] and path is not None and valid_key:
                    event_paths.append(path)
                    prior = candidate_paths.get(key, [])
                    delta_paths.append(path - np.mean(prior, axis=0) if len(prior) >= MIN_CONTROLS else np.full(126, np.nan))
                    event_dates.append(model["dates"][signal])
                if (
                    path is not None
                    and valid_key
                    and relevant_age[signal] >= 21
                    and not reference["events"][event][signal]
                ):
                    candidate_paths[key].append(path)
            result[(symbol, event)] = {
                "dates": event_dates,
                "event": nan_column_mean(np.vstack(event_paths)) if event_paths else np.full(126, np.nan),
                "delta": nan_column_mean(np.vstack(delta_paths)) if delta_paths else np.full(126, np.nan),
                "n": len(event_paths),
                "matched": sum(np.all(np.isfinite(path)) for path in delta_paths),
            }
    composites = {}
    for event in EVENTS:
        composites[event] = {
            "event": nan_column_mean(np.vstack([result[(symbol, event)]["event"] for symbol in INDEXES])),
            "delta": nan_column_mean(np.vstack([result[(symbol, event)]["delta"] for symbol in INDEXES])),
            "n": sum(result[(symbol, event)]["n"] for symbol in INDEXES),
        }
    return result, composites


def continuous_summary(rows):
    summary = {}
    for key, row in rows.items():
        summary[key] = {
            "ic": nan_column_mean(row["matrix"]) if len(row["matrix"]) else np.full(6, np.nan),
            "spread": nan_column_mean(row["spread_matrix"]) if len(row["spread_matrix"]) else np.full(6, np.nan),
            "p": row["p"],
            "q": row["q"],
            "dates": len(row["dates"]),
            "blocks": row["blocks"],
            "names": row["names"],
            "sectors": row["sectors"],
        }
    return summary


def candidate_decision(summaries):
    bands = (("short", (5, 10)), ("medium", (21, 42)), ("long", (63, 126)))
    for event in EVENTS:
        row = summaries[event]
        if not finite(row.get("q")) or row["q"] > 0.10:
            continue
        for label, horizons in bands:
            points = [HORIZONS.index(horizon) for horizon in horizons]
            if not all(row["C"][CHECKPOINTS[index]] > 0 and row["Delta"][CHECKPOINTS[index]] > 0 for index in points):
                continue
            long_index = horizons[-1] - 1
            if not finite(row["control_mdd"][long_index]) or row["mdd"][long_index] < row["control_mdd"][long_index]:
                continue
            return event, label
    return None


def print_results(model, primary, sensitivity, index_result, composites):
    continuous_rows, formations, event_rows, coverage = primary
    sensitivity_continuous, _sensitivity_formations, sensitivity_events, sensitivity_coverage = sensitivity
    continuous = continuous_summary(continuous_rows)
    events = summarize_event_rows(event_rows)
    sensitivity_c = continuous_summary(sensitivity_continuous)
    sensitivity_e = summarize_event_rows(sensitivity_events)

    finite_spy = np.flatnonzero(np.isfinite(model["references"]["SPY"]["close"]))
    print("## Data audit")
    print("| Release | Receipts | Truncated price calendar | Primary cohort | Complete-path month-ends | Inference |")
    print("| --- | ---: | --- | ---: | ---: | --- |")
    print(
        f"| Development only | {model['accepted']}/{model['all_symbols']} | "
        f"{model['dates'][finite_spy[0]]} to {model['dates'][finite_spy[-1]]} ET | "
        f"{len(model['names'])} unique-sector names | {len(formations)} | "
        f"10,000 half-year block sign flips, seed {SEED} |"
    )

    print("\n## Coverage and overlap - $25m primary")
    print("| Mean eligible | E1 dates/names | E5 dates/names | EB20 dates/names | ES dates/names | Same-name/day overlap |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: |")
    cells = [f"{len(coverage[event]['dates'])}/{coverage[event]['names']}" for event in EVENTS]
    overlap = coverage["overlap"] / coverage["event_cells"] if coverage["event_cells"] else None
    print(f"| {coverage['mean_eligible']:.1f} | " + " | ".join(cells) + f" | {coverage['overlap']} ({pct(overlap, 1)}) |")

    print("\n| Sector ETF | Actual reference start | Mean eligible | E1 | E5 | EB20 | ES |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for sector_code, sector in enumerate(SECTORS):
        available = np.flatnonzero(np.isfinite(model["references"][sector]["close"]))
        event_counts = [coverage[event]["sectors"][sector_code] for event in EVENTS]
        print(
            f"| {sector} | {model['dates'][available[0]] if len(available) else 'missing'} | "
            f"{coverage['mean_eligible_sector'][sector_code]:.1f} | "
            + " | ".join(str(value) for value in event_counts)
            + " |"
        )

    print("\n## Continuous cross-section - Development")
    print("Cell = mean month-end Rank IC / Q5-Q1 log-return spread. p/q is one curve-level test.")
    print("| View / signal | 5d | 10d | 21d | 42d | 63d | 126d | p / q | Dates / blocks |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | ---: |")
    for key in (("Broad", "D4"), ("Broad", "MAD"), ("Within-sector", "D4"), ("Within-sector", "MAD")):
        row = continuous[key]
        cells = [f"{number(row['ic'][i])} / {pct(row['spread'][i])}" for i in range(6)]
        print(f"| {key[0]} `{key[1]}` | " + " | ".join(cells) + f" | {pnumber(row['p'])} / {pnumber(row['q'])} | {row['dates']} / {row['blocks']} |")

    print("\n## Event checkpoints - $25m primary, Development")
    print("| Event | h | C dates/names; Delta dates/names | Absolute | vs SPY | C vs sector | Delta | KM survival | Median MDD all; matched/control |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for event in EVENTS:
        row = events[event]
        if row.get("dates", 0) == 0:
            print(f"| {event} | | 0 | | | | | | |")
            continue
        for horizon, checkpoint in zip(HORIZONS, CHECKPOINTS):
            print(
                f"| {event} | {horizon} | {row['dates']}/{row['names']}; {row['delta_dates']}/{row['matched']} | "
                f"{pct(row['absolute'][checkpoint])} | {pct(row['spy'][checkpoint])} | "
                f"{pct(row['C'][checkpoint])} | {pct(row['Delta'][checkpoint])} | "
                f"{pct(row['survival'][horizon - 1], 1)} | "
                f"{pct(row['all_mdd'][horizon - 1])}; {pct(row['mdd'][horizon - 1])} / {pct(row['control_mdd'][horizon - 1])} |"
            )

    print("\n## Edge path and duration")
    print("Each block is total sector excess (basis points per session).")
    print("| Event | Curve p/q | 1-5 | 6-10 | 11-21 | 22-42 | 43-63 | 64-126 | Peak / T50 | Giveback | Exhaustion | KM state median | State-exit C / mean hold |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |")
    for event in EVENTS:
        row = events[event]
        if row.get("dates", 0) == 0:
            continue
        giveback = f"day {row['giveback']}" if row["giveback"] is not None else ">126/NA"
        state_median = str(row["state_median"]) if row["state_median"] is not None else ">126"
        print(
            f"| {event} | {pnumber(row['p'])} / {pnumber(row['q'])} | "
            + " | ".join(
                f"{pct(value)} ({10000 * rate:+.2f})"
                for value, rate in zip(row["marginal"], row["marginal_rate"])
            )
            + f" | {row['peak_day']} / {row['t50']} | {giveback} | "
            f"{row['exhaustion'] if row['exhaustion'] is not None else 'none'} | {state_median} | "
            f"{pct(row['state_exit'])} / {row['state_hold']:.1f}d |"
        )

    print("\n## Context diagnostics - sector-relative C")
    print("| Axis | State | Event | N dates | 5d | 21d | 63d | 126d |")
    print("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for axis, label, event, count, curve in context_rows(event_rows):
        print(f"| {axis} | {label} | {event} | {count} | {pct(curve[0])} | {pct(curve[2])} | {pct(curve[4])} | {pct(curve[5])} |")

    print("\n## Correlated index sanity panel")
    print("Cell = event absolute log return / delta vs prior persistent-state dates. Composite equal weights ETFs, not events.")
    print("| Panel | Event | N (matched) | 5d | 21d | 63d | 126d |")
    print("| --- | --- | ---: | --- | --- | --- | --- |")
    for event in EVENTS:
        composite = composites[event]
        cells = [f"{pct(composite['event'][checkpoint])} / {pct(composite['delta'][checkpoint])}" for checkpoint in (4, 20, 62, 125)]
        print(f"| Equal-weight composite | {event} | {composite['n']} | " + " | ".join(cells) + " |")
        for symbol in INDEXES:
            row = index_result[(symbol, event)]
            cells = [f"{pct(row['event'][checkpoint])} / {pct(row['delta'][checkpoint])}" for checkpoint in (4, 20, 62, 125)]
            print(f"| {symbol} | {event} | {row['n']} ({row['matched']}) | " + " | ".join(cells) + " |")

    print("\n## $10m liquidity sensitivity")
    print("Sensitivity can weaken a primary result but cannot rescue a primary failure.")
    print("| Row | 5d | 21d | 63d | 126d | p/q | Coverage |")
    print("| --- | ---: | ---: | ---: | ---: | --- | ---: |")
    for key in (("Broad", "D4"), ("Broad", "MAD"), ("Within-sector", "D4"), ("Within-sector", "MAD")):
        row = sensitivity_c[key]
        values = [number(row["ic"][index]) for index in (0, 2, 4, 5)]
        print(f"| {key[0]} `{key[1]}` IC | " + " | ".join(values) + f" | {pnumber(row['p'])}/{pnumber(row['q'])} | {row['dates']} dates |")
    for event in EVENTS:
        row = sensitivity_e[event]
        values = [pct(row["Delta"][checkpoint]) for checkpoint in (4, 20, 62, 125)] if row.get("dates", 0) else ["NA"] * 4
        print(
            f"| {event} Delta | " + " | ".join(values)
            + f" | {pnumber(row.get('p'))}/{pnumber(row.get('q'))} | "
            f"C {row.get('dates', 0)}d/{row.get('names', 0)}n; "
            f"Delta {row.get('delta_dates', 0)}d/{row.get('matched', 0)}n |"
        )
    print(f"\n$10m mean eligible: {sensitivity_coverage['mean_eligible']:.1f}.")

    decision = candidate_decision(events)
    print("\n## Development nomination gate")
    if decision is None:
        print("No event family satisfies every frozen Development gate. Validation remains locked.")
    else:
        print(f"Nominate `{decision[0]}-{decision[1]}` for manual review before Validation. Validation remains locked in this release.")


def run(model):
    primary_eligible = eligibility(model, PRIMARY_FLOOR)
    sensitivity_eligible = eligibility(model, SENSITIVITY_FLOOR)
    primary_continuous, formations = analyze_continuous(model, primary_eligible)
    primary_events, primary_coverage = analyze_events(model, primary_eligible, primary_eligible)
    sensitivity_continuous, sensitivity_formations = analyze_continuous(model, sensitivity_eligible)
    sensitivity_events, sensitivity_coverage = analyze_events(model, sensitivity_eligible, primary_eligible)
    index_result, composites = analyze_indexes(model)
    print_results(
        model,
        (primary_continuous, formations, primary_events, primary_coverage),
        (sensitivity_continuous, sensitivity_formations, sensitivity_events, sensitivity_coverage),
        index_result,
        composites,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database")
    args = parser.parse_args()
    connection = connect(resolve_database_path(args.database), read_only=True)
    try:
        panel = load_panel(connection)
        panel["reference_arrays"] = load_references(connection, panel["dates"])
    finally:
        connection.close()
    model = prepare(panel)
    run(model)


if __name__ == "__main__":
    main()
