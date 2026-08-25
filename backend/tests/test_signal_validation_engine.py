from __future__ import annotations

import random

import pytest

from backend.engine.research.signal_validation import (
    effective_number_of_bets,
    ic_series_stats,
    pairwise_correlation_matrix,
    rank_information_coefficient,
    redundancy_pairs,
)


def _independent_series(n_series: int, length: int, seed: int) -> dict[str, list[float]]:
    rng = random.Random(seed)
    return {f"factor_{i}": [rng.gauss(0, 1) for _ in range(length)] for i in range(n_series)}


def _redundant_series(n_series: int, length: int, seed: int, noise: float = 0.01) -> dict[str, list[float]]:
    rng = random.Random(seed)
    base = [rng.gauss(0, 1) for _ in range(length)]
    return {f"factor_{i}": [value + rng.gauss(0, noise) for value in base] for i in range(n_series)}


def test_rank_information_coefficient_detects_monotonic_relationship() -> None:
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [10.0, 8.0, 30.0, 20.0, 50.0]  # monotonic-ish but not linear
    rho, p_value = rank_information_coefficient(x, y)
    assert rho > 0.5
    assert 0.0 <= p_value <= 1.0


def test_rank_information_coefficient_requires_minimum_samples() -> None:
    with pytest.raises(ValueError):
        rank_information_coefficient([1.0, 2.0], [1.0, 2.0])


def test_ic_series_stats_real_mean_std_icir() -> None:
    stats_result = ic_series_stats([0.1, 0.2, 0.15, 0.05, 0.1])
    assert stats_result.sample_count == 5
    assert stats_result.ic_mean == pytest.approx(0.12, abs=1e-9)
    assert stats_result.ic_std > 0
    assert stats_result.icir == pytest.approx(stats_result.ic_mean / stats_result.ic_std)


def test_ic_series_stats_zero_variance_gives_none_icir_not_infinity() -> None:
    stats_result = ic_series_stats([0.1, 0.1, 0.1])
    assert stats_result.ic_std == pytest.approx(0.0)
    assert stats_result.icir is None


def test_pairwise_correlation_matrix_skips_mismatched_length_pairs() -> None:
    series = {"a": [1.0, 2.0, 3.0, 4.0], "b": [2.0, 4.0, 6.0, 8.0], "c": [1.0, 2.0]}
    matrix = pairwise_correlation_matrix(series)
    assert ("a", "b") in matrix
    assert matrix[("a", "b")] == pytest.approx(1.0, abs=1e-9)
    assert ("a", "c") not in matrix
    assert ("b", "c") not in matrix


def test_effective_number_of_bets_near_n_for_independent_factors() -> None:
    series = _independent_series(5, 500, seed=1)
    matrix = pairwise_correlation_matrix(series)
    enb = effective_number_of_bets(sorted(series), matrix)
    assert enb is not None
    # Independent factors should be close to, not necessarily exactly, 5 --
    # finite-sample correlation noise keeps it from landing on the integer.
    assert enb > 4.0


def test_effective_number_of_bets_near_one_for_redundant_factors() -> None:
    series = _redundant_series(5, 500, seed=2)
    matrix = pairwise_correlation_matrix(series)
    enb = effective_number_of_bets(sorted(series), matrix)
    assert enb is not None
    assert enb < 1.5


def test_effective_number_of_bets_is_none_when_a_pair_is_missing() -> None:
    # Only (a, b) provided; c is present in `keys` but has no correlation
    # entry with either -- must return an honest None, not a fabricated
    # value that silently assumed zero correlation.
    assert effective_number_of_bets(["a", "b", "c"], {("a", "b"): 0.5}) is None


def test_effective_number_of_bets_none_below_two_keys() -> None:
    assert effective_number_of_bets(["a"], {}) is None
    assert effective_number_of_bets([], {}) is None


def test_redundancy_pairs_flags_only_above_threshold_strongest_first() -> None:
    correlations = {
        ("momentum_1m", "momentum_3m"): 0.85,
        ("momentum_1m", "momentum_6m"): 0.2,
        ("momentum_3m", "momentum_6m"): 0.72,
    }
    flags = redundancy_pairs(correlations, threshold=0.7)
    assert [f"{flag.key_a}-{flag.key_b}" for flag in flags] == ["momentum_1m-momentum_3m", "momentum_3m-momentum_6m"]
    assert flags[0].correlation == pytest.approx(0.85)


def test_redundancy_pairs_empty_when_nothing_clears_threshold() -> None:
    assert redundancy_pairs({("a", "b"): 0.3}, threshold=0.7) == []
