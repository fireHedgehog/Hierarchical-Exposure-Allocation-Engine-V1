from __future__ import annotations

# Wilder's RSI — the original, standard formulation (smoothed moving average
# of gains/losses, not a naive simple moving average). Naive as a TRADING
# rule, but the indicator math itself is the textbook definition.


def compute_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Returns one RSI value per input close, aligned by index.

    The first `period` entries are None — there isn't enough history yet to
    seed Wilder's smoothed average, and returning a fabricated number there
    would violate the one rule this whole engine runs on.
    """

    n = len(closes)
    result: list[float | None] = [None] * n
    if n <= period:
        return result

    deltas = [closes[i] - closes[i - 1] for i in range(1, n)]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [max(-delta, 0.0) for delta in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result[period] = _rsi_from_averages(avg_gain, avg_loss)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result[i + 1] = _rsi_from_averages(avg_gain, avg_loss)

    return result


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
