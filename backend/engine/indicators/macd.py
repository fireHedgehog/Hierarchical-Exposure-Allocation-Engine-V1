from __future__ import annotations


def compute_ema(values: list[float], period: int) -> list[float | None]:
    """Exponential moving average, seeded by a simple average of the first
    `period` values (the standard convention). None until seeded."""

    n = len(values)
    result: list[float | None] = [None] * n
    if n < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    alpha = 2.0 / (period + 1)
    ema = seed
    for i in range(period, n):
        ema = values[i] * alpha + ema * (1 - alpha)
        result[i] = ema
    return result


def compute_macd(
    closes: list[float], *, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Standard MACD(12,26,9). Returns (macd_line, signal_line, histogram),
    each aligned to `closes` by index, None wherever there isn't enough
    history yet to compute a real value."""

    n = len(closes)
    fast_ema = compute_ema(closes, fast)
    slow_ema = compute_ema(closes, slow)
    macd_line: list[float | None] = [None] * n
    for i in range(n):
        if fast_ema[i] is not None and slow_ema[i] is not None:
            macd_line[i] = fast_ema[i] - slow_ema[i]

    valid_indices = [i for i in range(n) if macd_line[i] is not None]
    signal_line: list[float | None] = [None] * n
    if len(valid_indices) >= signal:
        valid_values = [macd_line[i] for i in valid_indices]  # type: ignore[list-item]
        signal_over_valid = compute_ema(valid_values, signal)
        for offset, i in enumerate(valid_indices):
            signal_line[i] = signal_over_valid[offset]

    histogram: list[float | None] = [None] * n
    for i in range(n):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = macd_line[i] - signal_line[i]  # type: ignore[operator]

    return macd_line, signal_line, histogram
