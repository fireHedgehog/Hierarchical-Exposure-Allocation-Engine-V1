from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from backend.engine.factors import Bar, InsufficientPriceDataError
from backend.engine.factors.momentum_v3 import (
    HORIZON_LOOKBACKS,
    compute_cross_section_v3,
    compute_horizon_weights,
)


def _bars(prices: list[float], start: date = date(2016, 1, 1)) -> list[Bar]:
    return [Bar(time=(start + timedelta(days=offset)).isoformat(), close=price) for offset, price in enumerate(prices)]


def _noisy_walk(count: int, seed: int, drift: float = 0.0, noise: float = 0.01) -> list[float]:
    rng = random.Random(seed)
    price = 100.0
    prices = [price]
    for _ in range(count - 1):
        price *= 1 + drift + rng.uniform(-noise, noise)
        prices.append(price)
    return prices


def test_insufficient_history_falls_back_to_equal_weight_not_a_block() -> None:
    """Same real fallback as v2 (0.42), now across 4 horizons instead of 3:
    too little history for a real IC test on every horizon must still
    produce a usable, equal-weighted composite -- never raise or silently
    zero everything out."""

    thin_universe = {symbol: _bars(_noisy_walk(40, seed=index)) for index, symbol in enumerate(["A", "B", "C"])}
    weights = compute_horizon_weights(thin_universe)
    assert len(weights) == len(HORIZON_LOOKBACKS) == 4
    assert all(item.status == "insufficient_data" for item in weights)
    assert all(item.weight == pytest.approx(1.0 / 4.0) for item in weights)
    assert sum(item.weight for item in weights) == pytest.approx(1.0)


def test_weights_always_sum_to_one_even_when_mixed() -> None:
    """Magnitude vector still normalizes to 1 across all 4 horizons, same
    invariant as v2 -- see v2's own test for why only magnitude, not the
    signed sum, is guaranteed."""

    rng = random.Random(7)
    universe = {
        f"SYM{i}": _bars(_noisy_walk(600, seed=i, drift=rng.uniform(-0.0005, 0.0005))) for i in range(8)
    }
    weights = compute_horizon_weights(universe)
    assert sum(abs(item.weight) for item in weights) == pytest.approx(1.0, abs=1e-9)


def test_significantly_reversal_shaped_horizon_gets_negative_weight() -> None:
    """0.42's sign fix, unchanged behavior, now proven against v3's 4-horizon
    blend: a horizon with a real, significant reversal relationship must
    still get a real negative weight and invert the composite ranking
    accordingly."""

    rng = random.Random(11)
    universe: dict[str, list[Bar]] = {}
    for i in range(40):
        count = 400
        prices = [100.0]
        block = 21
        drift = 0.0
        for step in range(1, count):
            if step % block == 0:
                drift = -drift if drift != 0.0 else rng.choice([0.01, -0.01])
            prices.append(prices[-1] * (1 + drift / block + rng.uniform(-0.002, 0.002)))
        universe[f"SYM{i}"] = _bars(prices)

    weights = compute_horizon_weights(universe)
    by_horizon = {item.horizon: item for item in weights}
    assert by_horizon["1m"].status == "ok"
    assert by_horizon["1m"].significant is True
    assert by_horizon["1m"].correlation is not None and by_horizon["1m"].correlation < 0
    assert by_horizon["1m"].weight < 0.0

    strong_recent_gain = _bars([100.0] * 379 + [100.0 * (1.05**i) for i in range(21)])
    flat_recent = _bars([100.0] * 400)
    ranked, _ = compute_cross_section_v3({"GAINER": strong_recent_gain, "FLAT": flat_recent, **universe})
    scores = {item.symbol: item.composite_score for item in ranked}
    assert scores["GAINER"] < scores["FLAT"]


def test_predictive_horizon_gets_more_weight_than_random_ones() -> None:
    """Same real statistical-discovery test as v2, unaffected by the new
    4th horizon: a genuinely predictive 1m should still outweight a noisy
    6m."""

    rng = random.Random(42)
    universe: dict[str, list[Bar]] = {}
    for i in range(40):
        count = 400
        prices = [100.0]
        block = 21
        drift = 0.0
        for step in range(1, count):
            if step % block == 0:
                drift = rng.choice([0.01, -0.01])
            prices.append(prices[-1] * (1 + drift / block + rng.uniform(-0.002, 0.002)))
        universe[f"SYM{i}"] = _bars(prices)

    weights = compute_horizon_weights(universe)
    by_horizon = {item.horizon: item for item in weights}
    assert by_horizon["1m"].status == "ok"
    assert by_horizon["1m"].weight >= by_horizon["6m"].weight


def test_compute_cross_section_v3_ranks_and_returns_weight_diagnostics() -> None:
    universe = {
        "UP": _bars(_noisy_walk(300, seed=1, drift=0.002)),
        "DOWN": _bars(_noisy_walk(300, seed=2, drift=-0.002)),
        "FLAT": _bars(_noisy_walk(300, seed=3, drift=0.0)),
    }
    ranked, weights = compute_cross_section_v3(universe)
    assert {item.symbol for item in ranked} == {"UP", "DOWN", "FLAT"}
    assert len(weights) == len(HORIZON_LOOKBACKS)
    for item in ranked:
        assert -1.0 <= item.composite_score <= 1.0


def test_all_symbols_thin_still_raises_like_v2() -> None:
    with pytest.raises(InsufficientPriceDataError):
        compute_cross_section_v3({"THIN": _bars(_noisy_walk(5, seed=1))})


def test_12m_skip1m_horizon_uses_skip_days_not_latest_close() -> None:
    """The real, defining difference from 1m/3m/6m: the 12-1 signal point is
    one month before the decision date, not the latest close (Jegadeesh &
    Titman 1993 -- short-term reversal is a distinct effect this horizon
    deliberately excludes). Construct a series where the anchor at the real
    signal point (t-21) and the latest close disagree sharply, and confirm
    the computed horizon return uses the signal point, not the naive
    latest-close calculation every other horizon uses."""

    prices = [100.0] * 400
    prices[400 - 1 - 252] = 80.0  # 12-months-back anchor
    prices[400 - 1 - 21] = 120.0  # real 12-1 signal point
    prices[-1] = 200.0  # latest close -- must NOT be used as the signal point
    ranked, _ = compute_cross_section_v3({"ONLY": _bars(prices)})
    returns_by_horizon = {item.horizon: item for item in ranked[0].returns}
    twelve_one = returns_by_horizon["12m_skip1m"]
    assert twelve_one.value == pytest.approx((120.0 - 80.0) / 80.0)
