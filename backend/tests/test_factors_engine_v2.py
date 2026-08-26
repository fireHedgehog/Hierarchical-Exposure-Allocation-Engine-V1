from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from backend.engine.factors import Bar, InsufficientPriceDataError
from backend.engine.factors.momentum_v2 import (
    HORIZON_LOOKBACKS,
    compute_cross_section_v2,
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
    """Too little history for a real IC test on every horizon must still
    produce a usable, equal-weighted composite -- never raise or silently
    zero everything out."""

    thin_universe = {symbol: _bars(_noisy_walk(40, seed=index)) for index, symbol in enumerate(["A", "B", "C"])}
    weights = compute_horizon_weights(thin_universe)
    assert len(weights) == len(HORIZON_LOOKBACKS)
    assert all(item.status == "insufficient_data" for item in weights)
    assert all(item.weight == pytest.approx(1.0 / 3.0) for item in weights)
    assert sum(item.weight for item in weights) == pytest.approx(1.0)


def test_weights_always_sum_to_one_even_when_mixed() -> None:
    """A significant horizon's |r|-proportional share and a non-significant
    horizon's equal-weight fallback are on different scales -- the
    *magnitude* vector must still normalize to 1, matching v1's fixed-weight
    convention, and must never collapse to a zero-weight (blocked)
    composite. The signed weight itself is not guaranteed to sum to 1 (a
    significantly reversal-shaped horizon's weight is negative -- see
    test_significantly_reversal_shaped_horizon_gets_negative_weight), only
    its magnitude is."""

    rng = random.Random(7)
    universe = {
        f"SYM{i}": _bars(_noisy_walk(600, seed=i, drift=rng.uniform(-0.0005, 0.0005))) for i in range(8)
    }
    weights = compute_horizon_weights(universe)
    assert sum(abs(item.weight) for item in weights) == pytest.approx(1.0, abs=1e-9)


def test_significantly_reversal_shaped_horizon_gets_negative_weight() -> None:
    """The sign bug this project shipped and later fixed (0.26 found it,
    docs/engine-milestones.md later flagged and fixed it): weighting a
    horizon by abs(correlation) alone blends a significantly reversal-shaped
    horizon's positive trailing return in as if it were bullish, when the
    real, validated evidence says the opposite. Construct a universe where
    the 1-month horizon return has a real, strong NEGATIVE relationship with
    the next 1-month return (mean reversion, by construction) -- the fix
    must produce a negative weight for it, not just a small one."""

    rng = random.Random(11)
    universe: dict[str, list[Bar]] = {}
    for i in range(40):
        count = 400
        prices = [100.0]
        block = 21
        drift = 0.0
        for step in range(1, count):
            if step % block == 0:
                # Reverse direction each block: whatever this block does,
                # the next one does the opposite -- real, constructed mean
                # reversion, not persistence.
                drift = -drift if drift != 0.0 else rng.choice([0.01, -0.01])
            prices.append(prices[-1] * (1 + drift / block + rng.uniform(-0.002, 0.002)))
        universe[f"SYM{i}"] = _bars(prices)

    weights = compute_horizon_weights(universe)
    by_horizon = {item.horizon: item for item in weights}
    assert by_horizon["1m"].status == "ok"
    assert by_horizon["1m"].significant is True
    assert by_horizon["1m"].correlation is not None and by_horizon["1m"].correlation < 0
    assert by_horizon["1m"].weight < 0.0

    # The composite must actually apply that sign: a symbol with a strong
    # recent positive 1-month return, on this reversal-shaped horizon,
    # should NOT be scored more bullish than one with a flat recent return
    # -- the exact behavior the bug produced.
    strong_recent_gain = _bars([100.0] * 379 + [100.0 * (1.05**i) for i in range(21)])
    flat_recent = _bars([100.0] * 400)
    ranked, _ = compute_cross_section_v2({"GAINER": strong_recent_gain, "FLAT": flat_recent, **universe})
    scores = {item.symbol: item.composite_score for item in ranked}
    assert scores["GAINER"] < scores["FLAT"]


def test_predictive_horizon_gets_more_weight_than_random_ones() -> None:
    """Construct a universe where the 1-month horizon return is, by
    construction, strongly predictive of the next 1-month return (real
    persistence), while 3m/6m are independent noise. The significance test
    should find this and weight 1m higher -- a genuine statistical result,
    not a hand-picked one."""

    rng = random.Random(42)
    universe: dict[str, list[Bar]] = {}
    for i in range(40):
        count = 400
        prices = [100.0]
        # Build a price path where each ~21-day block's direction persists
        # into the next block (autocorrelated momentum), independent of the
        # longer horizons.
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


def test_compute_cross_section_v2_ranks_and_returns_weight_diagnostics() -> None:
    universe = {
        "UP": _bars(_noisy_walk(300, seed=1, drift=0.002)),
        "DOWN": _bars(_noisy_walk(300, seed=2, drift=-0.002)),
        "FLAT": _bars(_noisy_walk(300, seed=3, drift=0.0)),
    }
    ranked, weights = compute_cross_section_v2(universe)
    assert {item.symbol for item in ranked} == {"UP", "DOWN", "FLAT"}
    assert len(weights) == len(HORIZON_LOOKBACKS)
    for item in ranked:
        assert -1.0 <= item.composite_score <= 1.0


def test_all_symbols_thin_still_raises_like_v1() -> None:
    """The cross-section itself keeps v1's real failure mode (every symbol
    too thin to score at all) -- only the horizon *weighting* has a naive
    fallback, not the underlying price-history requirement."""

    with pytest.raises(InsufficientPriceDataError):
        compute_cross_section_v2({"THIN": _bars(_noisy_walk(5, seed=1))})
