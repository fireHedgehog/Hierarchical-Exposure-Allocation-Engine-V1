from __future__ import annotations

from backend.engine.indicators.macd import compute_ema, compute_macd
from backend.engine.indicators.rsi import compute_rsi


def test_rsi_is_none_until_seeded() -> None:
    closes = [100.0 + i for i in range(10)]
    rsi = compute_rsi(closes, period=14)
    assert all(value is None for value in rsi)
    assert len(rsi) == len(closes)


def test_rsi_approaches_extremes_for_pure_trends() -> None:
    up_only = [100.0 + i for i in range(30)]
    rsi_up = compute_rsi(up_only, period=14)
    assert rsi_up[-1] == 100.0

    down_only = [130.0 - i for i in range(30)]
    rsi_down = compute_rsi(down_only, period=14)
    assert rsi_down[-1] == 0.0


def test_rsi_stays_in_bounds_for_mixed_series() -> None:
    closes = [100.0]
    for i in range(60):
        closes.append(closes[-1] * (1 + (0.01 if i % 3 else -0.015)))
    rsi = compute_rsi(closes, period=14)
    for value in rsi:
        if value is not None:
            assert 0.0 <= value <= 100.0


def test_ema_seeds_with_simple_average_then_smooths() -> None:
    values = [10.0, 11.0, 12.0, 13.0, 14.0]
    ema = compute_ema(values, period=3)
    assert ema[0] is None
    assert ema[1] is None
    assert ema[2] == (10.0 + 11.0 + 12.0) / 3
    assert ema[3] is not None and ema[3] != ema[2]


def test_macd_line_is_none_until_slow_ema_ready_then_real() -> None:
    closes = [100.0 + i * 0.5 for i in range(40)]
    macd_line, signal_line, histogram = compute_macd(closes, fast=12, slow=26, signal=9)
    assert macd_line[24] is None  # slow EMA(26) not seeded yet
    assert macd_line[25] is not None  # seeded at index slow-1 = 25
    # A steady uptrend: fast EMA pulls ahead of slow EMA, so MACD should be positive.
    assert macd_line[-1] > 0
    assert len(macd_line) == len(signal_line) == len(histogram) == len(closes)


def test_macd_crossover_is_detectable_from_a_trend_reversal() -> None:
    rising = [100.0 + i * 1.5 for i in range(120)]
    falling = [rising[-1] - i * 1.5 for i in range(1, 120)]
    closes = rising + falling
    macd_line, signal_line, _histogram = compute_macd(closes)
    # Somewhere after the reversal, MACD should cross below signal.
    crossed = False
    for i in range(1, len(closes)):
        if macd_line[i - 1] is None or signal_line[i - 1] is None:
            continue
        if macd_line[i - 1] is not None and signal_line[i - 1] is not None:
            if macd_line[i - 1] >= signal_line[i - 1] and macd_line[i] < signal_line[i]:
                crossed = True
                break
    assert crossed
