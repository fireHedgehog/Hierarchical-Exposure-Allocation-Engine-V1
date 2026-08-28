from __future__ import annotations

import statistics
from datetime import date

from backend.engine.regime.types import (
    InsufficientSeriesDataError,
    RegimeEvidenceItem,
    RegimeFactor,
    RegimeResult,
    SeriesObservation,
)

# naive-v3: real z-score normalization + redundancy-aware cluster weighting,
# replacing v2's hand-picked-scale surprise score and v1's hand-picked
# per-factor weights (see docs/hypotheses/archive/staging_1/macro-research/README.md for the
# full research arc this is built from).
#
# Real problem v1/v2 had, found by H-MACRO08 (real pairwise correlation +
# effective-number-of-bets across every free indicator this project fetches):
# growth/inflation/employment factors (growth, inflation, ppi, pce,
# employment) are pairwise correlated 0.77-0.998 with each other -- one real
# latent signal, not five -- yet v1/v2's hand-picked WEIGHTS gave that single
# cluster 0.65 of total weight (0.15+0.15+0.10+0.15+0.10), vs. 0.25 for
# market stress (liquidity+volatility) and 0.10 for rates. Real,
# unintentional 2.5x over-weighting of one redundant cluster.
#
# Fix: every factor is scored as a real z-score, (latest - trailing_mean) /
# trailing_stdev -- an adaptive normalization (naturally wider for a
# volatile series like VIX, narrower for a stable one like core PCE),
# replacing the hand-picked `scale` divisor v1/v2 used per factor. Factors
# are grouped into 3 real, evidence-based clusters (H-MACRO08's finding):
# growth_inflation, rate_level, market_stress -- weight is split equally
# across clusters, then equally across each cluster's own members, so no
# cluster can outvote another just by having more correlated names in it.
# A 4th cluster (policy operations: WALCL/WTREGEN/IORB/SOFR) is deliberately
# excluded -- its sign is genuinely ambiguous (balance-sheet expansion can
# mean either crisis liquidity injection, risk-off cause, or accommodative
# ease, risk-on outcome, context-dependent) -- a real, disclosed gap, not
# guessed (see docs/hypotheses/archive/staging_1/macro-research/composite-methodology-v1.md).
#
# `confidence` is a legacy schema name. The value is the current-vintage
# historical six-month adverse-excursion frequency for the runtime's state
# zone, not model confidence and not a release-time-PIT probability. The exact
# 13-factor translation is H-MACRO-S3-CV-001. Nothing here is a timing or
# trading signal.

STRESSED_TERCILE_CUTOFF = -0.33
CALM_TERCILE_CUTOFF = 0.33
# Current-vintage historical frequency of SPY falling at least 10% below the
# anchor close within six months, by exact-runtime zone (H-MACRO-S3-CV-001).
# These preserve a numeric staging output while remaining explicitly distinct
# from a release-time-PIT calibrated probability.
CURRENT_VINTAGE_ADVERSE_FREQUENCY_ADVERSE = 11 / 31
CURRENT_VINTAGE_ADVERSE_FREQUENCY_MIXED = 43 / 200
CURRENT_VINTAGE_ADVERSE_FREQUENCY_SUPPORTIVE = 1 / 21

# Exact 13-factor current-vintage (composite score, empirical percentile)
# checkpoints from H-MACRO-S3-CV-001's 258 monthly-strided runtime anchors.
# The persisted column retains its old name for compatibility.
PERCENTILE_CHECKPOINTS: tuple[tuple[float, float], ...] = (
    (-0.6053, 0.0), (-0.4216, 5.0), (-0.3533, 10.0), (-0.2280, 20.0),
    (-0.1776, 25.0), (-0.1034, 33.0), (-0.0643, 40.0), (0.0043, 50.0),
    (0.0220, 55.0), (0.0512, 60.0), (0.1075, 67.0), (0.1665, 75.0),
    (0.2206, 80.0), (0.2852, 90.0), (0.3676, 95.0), (0.6299, 100.0),
)


def _percentile_rank(composite: float) -> float:
    points = PERCENTILE_CHECKPOINTS
    if composite <= points[0][0]:
        return points[0][1]
    if composite >= points[-1][0]:
        return points[-1][1]
    for (score_lo, pct_lo), (score_hi, pct_hi) in zip(points, points[1:]):
        if score_lo <= composite <= score_hi:
            if score_hi == score_lo:
                return pct_lo
            fraction = (composite - score_lo) / (score_hi - score_lo)
            return pct_lo + fraction * (pct_hi - pct_lo)
    return 50.0  # unreachable given the bounds checks above; a safe, honest fallback


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _yoy_series(observations: list[SeriesObservation]) -> list[tuple[str, float]]:
    """Real (observation_date, YoY value) pairs -- each YoY point compares
    an observation against the closest real observation at least one real
    year earlier, never interpolated."""

    ordered = sorted(observations, key=lambda item: item.observation_date)
    result: list[tuple[str, float]] = []
    for i, obs in enumerate(ordered):
        target = date.fromisoformat(obs.observation_date).replace(
            year=date.fromisoformat(obs.observation_date).year - 1
        ).isoformat()
        prior = [o for o in ordered[:i] if o.observation_date <= target]
        if not prior:
            continue
        year_ago = prior[-1]
        if year_ago.value == 0:
            continue
        result.append((obs.observation_date, (obs.value - year_ago.value) / abs(year_ago.value)))
    return result


def _zscore_factor(
    *,
    key: str,
    name: str,
    series_id: str,
    observations: list[SeriesObservation],
    sign: float,
    is_yoy: bool,
    trailing_window: int,
) -> RegimeFactor:
    ordered = sorted(observations, key=lambda item: item.observation_date)
    if is_yoy:
        points = _yoy_series(ordered)
    else:
        points = [(obs.observation_date, obs.value) for obs in ordered]
    if len(points) < trailing_window + 1:
        raise InsufficientSeriesDataError(
            f"{series_id}: need at least {trailing_window + 1} real{' YoY' if is_yoy else ''} "
            f"points for a trailing z-score, have {len(points)}."
        )
    latest_date, latest_value = points[-1]
    trailing = [value for _, value in points[-(trailing_window + 1) : -1]]
    mean = statistics.fmean(trailing)
    stdev = statistics.pstdev(trailing)
    z = 0.0 if stdev < 1e-9 else (latest_value - mean) / stdev
    contribution = _clamp(sign * z / 2.5)  # naive, disclosed: z=+/-2.5 already an extreme real reading
    status = "pass" if contribution >= 0 else "caution"
    shape = "YoY" if is_yoy else "level"
    return RegimeFactor(
        key=key,
        name=name,
        raw_value=latest_value,
        threshold=mean,
        filter_status=status,
        filter_explanation=(
            f"{series_id} latest {shape} is {latest_value:+.4f}, a real z-score of {z:+.2f} against its own "
            f"trailing {trailing_window}-period mean ({mean:+.4f}) and stdev ({stdev:.4f})."
        ),
        contribution=contribution,
        direction="positive" if contribution > 0.05 else "negative" if contribution < -0.05 else "neutral",
        contribution_explanation=(
            f"z={z:+.2f} scaled by sign {sign:+.0f} and a naive /2.5 band into [-1, 1] -- naive-v3: real, "
            "adaptive z-score against this factor's own trailing history, not a hand-picked scale constant."
        ),
        evidence=[
            RegimeEvidenceItem(
                key=f"{series_id.lower()}_latest",
                label=f"{series_id} latest observation",
                value=latest_value,
                detail=f"Most recent real observation, {latest_date}.",
                observed_at=ordered[-1].observed_at,
                available_at=ordered[-1].available_at,
            ),
            RegimeEvidenceItem(
                key=f"{series_id.lower()}_trailing_zscore_basis",
                label=f"{series_id} trailing {trailing_window}-period mean / stdev",
                value=mean,
                detail=f"Real trailing mean {mean:+.4f}, stdev {stdev:.4f}, from the {trailing_window} real points immediately preceding this one.",
                observed_at=ordered[-1].observed_at,
                available_at=ordered[-1].available_at,
            ),
        ],
    )


# (key, name, series_id, sign, is_yoy, trailing_window) per cluster.
CLUSTERS: dict[str, list[tuple[str, str, str, float, bool, int]]] = {
    "growth_inflation": [
        ("growth", "Growth", "INDPRO", 1.0, True, 6),
        ("employment", "Employment growth", "PAYEMS", 1.0, True, 6),
        ("gdp", "Real GDP", "GDPC1", 1.0, True, 4),
        ("inflation", "Inflation", "CPIAUCSL", -1.0, True, 6),
        ("pce", "Core PCE inflation", "PCEPILFE", -1.0, True, 6),
        ("ppi", "Producer prices", "PPIACO", -1.0, True, 6),
    ],
    "rate_level": [
        ("rates_10y", "10-year yield", "DGS10", -1.0, False, 60),
        ("rates_30y", "30-year yield", "DGS30", -1.0, False, 60),
        ("real_yield_10y", "10-year real yield", "DFII10", -1.0, False, 60),
    ],
    "market_stress": [
        ("liquidity", "Financial conditions", "NFCI", -1.0, False, 26),
        ("volatility", "Volatility", "VIXCLS", -1.0, False, 60),
        ("credit_hy", "High-yield credit spread", "BAMLH0A0HYM2", -1.0, False, 20),
        ("credit_ig", "Investment-grade credit spread", "BAMLC0A0CM", -1.0, False, 20),
    ],
}


def compute_regime_v3(series: dict[str, list[SeriesObservation]], as_of: date) -> RegimeResult:
    """naive-v3 regime composite: real z-score per factor, 3 evidence-based
    clusters (H-MACRO08), redundancy-aware weighting, and an exact-runtime
    current-vintage adverse-frequency reference. Policy operations remain excluded; Liquidity/Guidance from
    the Fed-response research track are a separate concern.

    Null-tolerant by cluster and by factor, matching this project's
    established macro convention: a missing series (e.g. credit spreads
    before they existed) is skipped, not a hard failure, as long as at
    least one factor in at least one cluster has real data.
    """

    factors: list[RegimeFactor] = []
    cluster_scores: dict[str, list[float]] = {}

    for cluster_name, members in CLUSTERS.items():
        cluster_factors: list[RegimeFactor] = []
        for key, name, series_id, sign, is_yoy, window in members:
            try:
                factor = _zscore_factor(
                    key=key, name=name, series_id=series_id,
                    observations=series.get(series_id, []),
                    sign=sign, is_yoy=is_yoy, trailing_window=window,
                )
            except InsufficientSeriesDataError:
                continue
            cluster_factors.append(factor)
        if cluster_factors:
            factors.extend(cluster_factors)
            cluster_scores[cluster_name] = [f.contribution for f in cluster_factors]

    if not factors:
        raise InsufficientSeriesDataError("naive-v3: no cluster had at least one factor with real data.")

    # Real weight normalization: equal share per cluster that actually has
    # data this run, equal share per member within it -- a cluster missing
    # entirely this run doesn't leave "dead" weight unassigned (the
    # null-tolerant behavior this project's macro composite has always had,
    # preserved here). This weights dict is descriptive (what share of the
    # composite each factor represents) -- the composite score itself is
    # computed by averaging cluster means directly below, which is
    # mathematically identical to this weighted sum for equal-sized clusters
    # and is what was actually validated in the real backtest.
    active_clusters = list(cluster_scores)
    cluster_weight = 1.0 / len(active_clusters)
    weights: dict[str, float] = {}
    for cluster_name in active_clusters:
        members_in_cluster = [f for f in factors if f.key in {m[0] for m in CLUSTERS[cluster_name]}]
        member_weight = cluster_weight / len(members_in_cluster)
        for factor in members_in_cluster:
            weights[factor.key] = member_weight

    cluster_means = [statistics.fmean(scores) for scores in cluster_scores.values()]
    composite = statistics.fmean(cluster_means)

    if composite <= STRESSED_TERCILE_CUTOFF:
        historical_rate = CURRENT_VINTAGE_ADVERSE_FREQUENCY_ADVERSE
        tercile = "stressed"
    elif composite >= CALM_TERCILE_CUTOFF:
        historical_rate = CURRENT_VINTAGE_ADVERSE_FREQUENCY_SUPPORTIVE
        tercile = "calm"
    else:
        historical_rate = CURRENT_VINTAGE_ADVERSE_FREQUENCY_MIXED
        tercile = "middle"
    confidence = historical_rate
    percentile_rank = _percentile_rank(composite)

    if composite >= 0.15:
        label = "Supportive macro-financial state"
    elif composite <= -0.15:
        label = "Adverse macro-financial state"
    else:
        label = "Mixed macro-financial state"

    cluster_summary = ", ".join(
        f"{name} {statistics.fmean(scores):+.2f}" for name, scores in cluster_scores.items()
    )
    summary = (
        f"Staging-v3 macro-financial state {composite:+.2f} ({cluster_summary}); {percentile_rank:.0f}/100 "
        "on the exact 13-factor current-vintage environment distribution. In historical anchors from the "
        f"same runtime, the '{tercile}' zone was followed by SPY falling at least 10% below its anchor close "
        f"within six months {historical_rate:.1%} of the time. This is an adverse-frequency reference, not "
        "a release-time-PIT probability. Use as risk context, not entry timing or a trade instruction."
    )

    return RegimeResult(
        label=label, confidence=confidence, summary=summary, factors=factors, weights=weights,
        percentile_rank=percentile_rank,
    )
