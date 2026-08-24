from __future__ import annotations

import pytest

from backend.engine.research.significance import benjamini_hochberg, pearson_significance


def test_pearson_significance_perfect_positive_correlation() -> None:
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 4.0, 6.0, 8.0, 10.0]
    r, p = pearson_significance(x, y)
    assert r == pytest.approx(1.0)
    assert p < 0.001


def test_pearson_significance_perfect_negative_correlation() -> None:
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [10.0, 8.0, 6.0, 4.0, 2.0]
    r, p = pearson_significance(x, y)
    assert r == pytest.approx(-1.0)
    assert p < 0.001


def test_pearson_significance_no_correlation_has_high_p_value() -> None:
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    y = [3.0, 1.0, 4.0, 1.0, 5.0, 2.0]  # not monotonic with x
    r, p = pearson_significance(x, y)
    assert -1.0 <= r <= 1.0
    assert 0.0 <= p <= 1.0


def test_pearson_significance_requires_matching_lengths() -> None:
    with pytest.raises(ValueError):
        pearson_significance([1.0, 2.0], [1.0])


def test_pearson_significance_requires_at_least_three_samples() -> None:
    with pytest.raises(ValueError):
        pearson_significance([1.0, 2.0], [1.0, 2.0])


def test_benjamini_hochberg_matches_hand_verified_example() -> None:
    # p(1..5) = [0.01, 0.02, 0.03, 0.04, 0.5]; BH critical values at alpha=0.05
    # are (k/5)*0.05 = 0.01, 0.02, 0.03, 0.04, 0.05. p(k) <= crit(k) holds for
    # k=1..4 and fails at k=5, so ranks 1-4 are significant, rank 5 is not.
    p_values = [0.01, 0.02, 0.03, 0.04, 0.5]
    adjusted, significant = benjamini_hochberg(p_values, alpha=0.05)
    assert significant == [True, True, True, True, False]
    assert adjusted[:4] == [pytest.approx(0.05)] * 4
    assert adjusted[4] == pytest.approx(0.5)


def test_benjamini_hochberg_is_order_independent() -> None:
    p_values = [0.5, 0.04, 0.01, 0.03, 0.02]  # same set, shuffled order
    adjusted, significant = benjamini_hochberg(p_values, alpha=0.05)
    # index 0 held the largest p-value (0.5) -> not significant
    assert significant[0] is False
    assert all(significant[1:])


def test_benjamini_hochberg_empty_input() -> None:
    adjusted, significant = benjamini_hochberg([], alpha=0.05)
    assert adjusted == []
    assert significant == []


def test_benjamini_hochberg_all_null_p_values_none_significant() -> None:
    p_values = [0.9, 0.8, 0.95, 0.99]
    _, significant = benjamini_hochberg(p_values, alpha=0.05)
    assert not any(significant)


def test_benjamini_hochberg_adjusted_p_values_are_monotone_by_rank() -> None:
    p_values = [0.001, 0.2, 0.05, 0.6, 0.01]
    adjusted, _ = benjamini_hochberg(p_values, alpha=0.05)
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    ranked_adjusted = [adjusted[i] for i in order]
    assert ranked_adjusted == sorted(ranked_adjusted)
