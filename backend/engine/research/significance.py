from __future__ import annotations

from scipy import stats

# Milestone 4, step 1: real statistical significance, not a coin flip. Pearson
# correlation + a real two-sided p-value via scipy (the standard, tested
# implementation -- not hand-rolled). Multiple-comparisons correction IS
# hand-rolled (Benjamini-Hochberg is a dozen lines, directly testable against
# a textbook example) rather than pulling in a second stats dependency for
# one function.


def pearson_significance(x: list[float], y: list[float]) -> tuple[float, float]:
    """Real Pearson correlation coefficient and two-sided p-value.

    Requires at least 3 paired samples (scipy's own minimum for a defined
    p-value). Callers doing real research should require far more than 3 --
    see MIN_SAMPLES in factor_symbol_correlation.py -- this floor only
    guards against a degenerate call.
    """

    if len(x) != len(y):
        raise ValueError(f"x and y must be the same length, got {len(x)} and {len(y)}.")
    if len(x) < 3:
        raise ValueError(f"need at least 3 paired samples for a defined p-value, got {len(x)}.")
    result = stats.pearsonr(x, y)
    return float(result.statistic), float(result.pvalue)


def benjamini_hochberg(p_values: list[float], alpha: float = 0.05) -> tuple[list[float], list[bool]]:
    """Benjamini-Hochberg false-discovery-rate correction.

    Returns (adjusted_p_values, significant_flags), both aligned to the
    input order. Testing many factors against many symbols raises a real
    multiple-comparisons problem -- a naive p < alpha cutoff would flag
    false positives by chance alone; this is the standard correction for
    exactly that, not a naive per-test threshold.
    """

    m = len(p_values)
    if m == 0:
        return [], []
    # order[k-1] = index of the k-th smallest p-value (1-indexed rank k)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted_by_rank = [0.0] * m
    running_min = 1.0
    for rank in range(m, 0, -1):
        index = order[rank - 1]
        candidate = p_values[index] * m / rank
        running_min = min(running_min, candidate)
        adjusted_by_rank[rank - 1] = min(running_min, 1.0)
    adjusted = [0.0] * m
    for rank in range(1, m + 1):
        adjusted[order[rank - 1]] = adjusted_by_rank[rank - 1]
    significant = [adjusted[i] <= alpha for i in range(m)]
    return adjusted, significant
