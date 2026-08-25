from __future__ import annotations

import statistics
from dataclasses import dataclass

import numpy as np
from scipy import stats

# Milestone 4 step 2 (docs/engine-milestones.md), generalized into a
# reusable research-evidence utility rather than a one-off script: "number
# of factors != number of independent bets." Ten correlated factors do not
# represent ten independent views -- PCA on their correlation matrix
# reveals how many they actually are, and the same pairwise-correlation
# matrix flags a new candidate factor that is really "~0.85x an existing
# one" in different clothing.
#
# Pure math over already-extracted, already-aligned paired series -- no DB,
# no network, standalone-testable, matching every other engine/ module in
# this project. Extraction (which factors, which dates, which forward
# returns) lives in backend/research_repository.py.


def rank_information_coefficient(x: list[float], y: list[float]) -> tuple[float, float]:
    """Spearman rank correlation + two-sided p-value -- Rank IC, robust to
    outliers and nonlinearity that Pearson IC (pearson_significance in
    significance.py) is not. Same 3-sample floor as pearson_significance."""

    if len(x) != len(y):
        raise ValueError(f"x and y must be the same length, got {len(x)} and {len(y)}.")
    if len(x) < 3:
        raise ValueError(f"need at least 3 paired samples for a defined p-value, got {len(x)}.")
    result = stats.spearmanr(x, y)
    return float(result.statistic), float(result.pvalue)


@dataclass(frozen=True)
class ICSeriesStats:
    ic_mean: float
    ic_std: float
    icir: float | None  # None when ic_std is ~0 -- undefined, never fabricated as infinity
    sample_count: int


def ic_series_stats(ic_values: list[float]) -> ICSeriesStats:
    """Real mean/std/ICIR across a series of real per-period IC values (one
    IC per rebalance date). A genuine per-period ICIR is a stricter, distinct
    thing from a single pooled-sample IC (what momentum_v2.py's horizon test
    computes) -- kept separate here rather than blurred together."""

    if not ic_values:
        raise ValueError("need at least one IC value.")
    mean = statistics.fmean(ic_values)
    std = statistics.pstdev(ic_values) if len(ic_values) > 1 else 0.0
    icir = mean / std if std > 1e-12 else None
    return ICSeriesStats(ic_mean=mean, ic_std=std, icir=icir, sample_count=len(ic_values))


def pairwise_correlation_matrix(series_by_key: dict[str, list[float]]) -> dict[tuple[str, str], float]:
    """Real pairwise Pearson correlation for every pair of series that share
    the same length. Series must already be aligned by the caller (same
    index = same real date) -- this function does not attempt to guess an
    alignment across mismatched series, since silent date-alignment
    guessing is exactly the kind of misalignment risk this project's
    point-in-time rules exist to prevent. Returns one entry per unordered
    pair; self-correlation is not included."""

    keys = sorted(series_by_key)
    matrix: dict[tuple[str, str], float] = {}
    for i, key_a in enumerate(keys):
        for key_b in keys[i + 1:]:
            series_a = series_by_key[key_a]
            series_b = series_by_key[key_b]
            if len(series_a) != len(series_b) or len(series_a) < 3:
                continue
            correlation = float(np.corrcoef(series_a, series_b)[0, 1])
            matrix[(key_a, key_b)] = correlation
    return matrix


def effective_number_of_bets(
    keys: list[str], pairwise_correlations: dict[tuple[str, str], float]
) -> float | None:
    """PCA-based effective number of independent bets among `keys`: eigen-
    decompose their (keys x keys) correlation matrix, then take the inverse
    Herfindahl index (1 / sum(normalized_eigenvalue_i^2)) of the spectrum --
    a standard concentration-index measure applied to PCA eigenvalues,
    equal to len(keys) when every factor is orthogonal and close to 1 when
    every factor loads on a single common driver. This is the disclosed,
    real formula backing this project's "10 factors -> ENB ~ 2" example.

    Returns None -- an honest null, not a value computed from a silently
    assumed-zero correlation -- if fewer than 2 keys, or any pair's real
    correlation is missing from pairwise_correlations (too few paired
    samples to have computed it)."""

    n = len(keys)
    if n < 2:
        return None
    matrix = np.eye(n)
    for i, key_a in enumerate(keys):
        for j in range(i + 1, n):
            key_b = keys[j]
            pair = pairwise_correlations.get((key_a, key_b), pairwise_correlations.get((key_b, key_a)))
            if pair is None:
                return None
            matrix[i, j] = matrix[j, i] = pair
    eigenvalues = np.linalg.eigvalsh(matrix)
    eigenvalues = np.clip(eigenvalues, 0.0, None)  # a PSD matrix's eigenvalues are >= 0; clip only float noise
    total = float(eigenvalues.sum())
    if total <= 1e-12:
        return None
    weights = eigenvalues / total
    herfindahl = float(np.sum(weights**2))
    if herfindahl <= 1e-12:
        return None
    return 1.0 / herfindahl


@dataclass(frozen=True)
class RedundancyFlag:
    key_a: str
    key_b: str
    correlation: float


def redundancy_pairs(
    pairwise_correlations: dict[tuple[str, str], float], *, threshold: float = 0.7
) -> list[RedundancyFlag]:
    """Pairs whose |correlation| clears `threshold` -- the concrete "new
    factor looks like ~0.85x an existing factor" check. 0.7 is a disclosed,
    common quant-research convention for flagging redundancy, not a value
    fit to this project's own data. Sorted strongest-first."""

    flags = [
        RedundancyFlag(key_a=key_a, key_b=key_b, correlation=correlation)
        for (key_a, key_b), correlation in pairwise_correlations.items()
        if abs(correlation) >= threshold
    ]
    return sorted(flags, key=lambda flag: -abs(flag.correlation))
