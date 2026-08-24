from __future__ import annotations

from dataclasses import dataclass


class InsufficientPriceDataError(ValueError):
    """A symbol has too little price history to score."""


@dataclass(frozen=True)
class Bar:
    time: str  # ISO date, ascending order not required by caller
    close: float


@dataclass(frozen=True)
class HorizonReturn:
    horizon: str
    lookback_days: int
    weight: float
    value: float | None  # None when history doesn't reach this horizon


@dataclass(frozen=True)
class SymbolMomentum:
    symbol: str
    last_close: float
    last_date: str
    returns: list[HorizonReturn]
    blended_return: float  # weighted average of available horizon returns
    composite_score: float  # blended_return, cross-sectionally z-scored and clamped to [-1, 1]
    rank: int
    direction: str  # 'bullish' | 'bearish' | 'neutral'
    strength: float  # abs(composite_score), clamped [0, 1]
