from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.cross_sectional_ranking import _leadership_overlay


def _business_days(start: date, count: int) -> list[str]:
    result: list[str] = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _panel() -> tuple[list[str], dict[str, float], dict[str, dict[str, dict[str, float]]], dict[str, str]]:
    dates = _business_days(date(2024, 1, 2), 340)
    spy = {day: 100.0 * (1.0004 ** index) for index, day in enumerate(dates)}
    histories: dict[str, dict[str, dict[str, float]]] = {}
    sectors: dict[str, str] = {}
    for symbol_index in range(12):
        symbol = chr(ord("A") + symbol_index)
        daily_growth = 0.0005 + (11 - symbol_index) * 0.0001
        histories[symbol] = {
            day: {
                "price": 20.0 * (1.0 + daily_growth) ** index,
                "raw_close": 20.0 * (1.0 + daily_growth) ** index,
                "volume": float(2_000_000 - symbol_index * 50_000),
            }
            for index, day in enumerate(dates)
        }
        sectors[symbol] = "XLK" if symbol_index < 6 else "XLI"

    # L is an explicit short-term loss observation. The shock is entirely in
    # the final five shared sessions, so no positional or forward-filled date
    # can be mistaken for the endpoint.
    for index in range(len(dates) - 5, len(dates)):
        day = dates[index]
        shock = 1.0 - 0.04 * (index - (len(dates) - 6))
        histories["L"][day]["price"] *= shock
        histories["L"][day]["raw_close"] *= shock
    return dates, spy, histories, sectors


def test_leadership_overlay_builds_exact_date_sleeves_and_weights() -> None:
    dates, spy, histories, sectors = _panel()

    result = _leadership_overlay(dates, spy, histories, sectors)

    assert result["formation_count"] == 13
    assert len(result["liquidity_rank"]) == 12
    assert result["current_leaders"] == {"A"}
    assert result["appearances"]["A"] == 13
    assert result["persistence"]["A"] == pytest.approx(1.0)
    assert result["candidate_weight"]["A"] == pytest.approx(1.0)
    assert sum(result["candidate_weight"].values()) == pytest.approx(1.0)
    assert result["reversal_5d_percentile"]["L"] == pytest.approx(100.0)
    assert result["sector_relative_reversal_percentile"]["L"] == pytest.approx(100.0)


def test_leadership_overlay_does_not_substitute_a_nearby_symbol_session() -> None:
    dates, spy, histories, sectors = _panel()
    missing_symbol = "A"
    histories[missing_symbol].pop(dates[-64])

    result = _leadership_overlay(dates, spy, histories, sectors)

    assert missing_symbol not in result["liquidity_rank"]
    assert missing_symbol not in result["current_leaders"]
    assert missing_symbol not in result["rs_3m_percentile"]
