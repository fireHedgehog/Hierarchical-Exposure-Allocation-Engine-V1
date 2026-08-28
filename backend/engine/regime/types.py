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
    # Current-vintage empirical position (0-100) of the exact-runtime score;
    # not a release-time-PIT probability. None for v1/v2. See scoring_v3.py.
    percentile_rank: float | None = None
