from __future__ import annotations

from dataclasses import dataclass


class InsufficientSeriesDataError(ValueError):
    """A required series has no usable observation to score against."""


@dataclass(frozen=True)
class SeriesObservation:
    observation_date: str  # YYYY-MM-DD
    value: float
    observed_at: str
    available_at: str


@dataclass(frozen=True)
class RegimeEvidenceItem:
    key: str
    label: str
    value: float
    detail: str
    observed_at: str
    available_at: str


@dataclass(frozen=True)
class RegimeFactor:
    key: str
    name: str
    raw_value: float
    threshold: float
    filter_status: str  # 'pass' | 'caution'
    filter_explanation: str
    contribution: float  # normalized to [-1, 1], pre-weight
    direction: str  # 'positive' | 'negative' | 'neutral'
    contribution_explanation: str
    evidence: list[RegimeEvidenceItem]


@dataclass(frozen=True)
class RegimeResult:
    label: str
    confidence: float
    summary: str
    factors: list[RegimeFactor]
    weights: dict[str, float]
    # Real historical percentile rank (0-100) of the composite score against
    # its own real backtest distribution -- naive-v3 only; None for v1/v2,
    # which have no such distribution computed. See scoring_v3.py.
    percentile_rank: float | None = None
