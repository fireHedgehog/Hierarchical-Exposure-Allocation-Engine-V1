from __future__ import annotations


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def suggested_weight(
    composite_score: float, *, base_weight: float, low_multiple: float = 0.2, high_multiple: float = 2.0
) -> float:
    """Naive tilt away from an equal-weight baseline, bounded to stay sane.

    A composite_score of 0 (neutral vs. peers) returns exactly base_weight —
    the equal-weight "staging portfolio" baseline described in
    docs/engine-milestones.md. Positive/negative scores tilt over/under that
    baseline; the multiple is clamped so one extreme reading can't propose
    an absurd position size.
    """

    multiple = _clamp(1.0 + composite_score, low_multiple, high_multiple)
    return base_weight * multiple
