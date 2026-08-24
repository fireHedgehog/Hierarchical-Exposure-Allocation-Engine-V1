from __future__ import annotations

from datetime import date, timedelta

from backend.engine.regime.types import (
    InsufficientSeriesDataError,
    RegimeEvidenceItem,
    RegimeFactor,
    RegimeResult,
    SeriesObservation,
)

# First-pass, deliberately naive scoring. Coefficients (weights, scales,
# thresholds) below are hand-picked, not fit — that is an explicit, accepted
# tradeoff for this milestone (see docs/engine-milestones.md, Milestone 3).
# What is NOT accepted: any output value that isn't actually computed from a
# real fetched observation. Every number this module returns traces back to
# an entry in the `series` argument passed in by the caller.

WEIGHTS: dict[str, float] = {
    "growth": 0.15,
    "inflation": 0.15,
    "ppi": 0.10,
    "pce": 0.15,
    "employment": 0.10,
    "liquidity": 0.15,
    "volatility": 0.10,
    "rates": 0.10,
}


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _direction(value: float, *, neutral_band: float = 0.05) -> str:
    if value > neutral_band:
        return "positive"
    if value < -neutral_band:
        return "negative"
    return "neutral"


def _latest(series_key: str, observations: list[SeriesObservation]) -> SeriesObservation:
    if not observations:
        raise InsufficientSeriesDataError(f"{series_key}: no observations available.")
    return max(observations, key=lambda item: item.observation_date)


def _closest_to(
    series_key: str, observations: list[SeriesObservation], target_date: date
) -> SeriesObservation:
    if not observations:
        raise InsufficientSeriesDataError(f"{series_key}: no observations available.")
    return min(
        observations,
        key=lambda item: abs((date.fromisoformat(item.observation_date) - target_date).days),
    )


def _score_yoy_factor(
    *,
    key: str,
    name: str,
    series_id: str,
    observations: list[SeriesObservation],
    as_of: date,
    sign: float,
    target: float,
    scale: float,
    threshold_label: str,
) -> RegimeFactor:
    latest = _latest(series_id, observations)
    year_ago = _closest_to(series_id, observations, as_of - timedelta(days=365))
    yoy = (latest.value - year_ago.value) / abs(year_ago.value)
    contribution = _clamp(sign * (yoy - target) / scale)
    status = "pass" if contribution >= 0 else "caution"
    return RegimeFactor(
        key=key,
        name=name,
        raw_value=yoy,
        threshold=target,
        filter_status=status,
        filter_explanation=(
            f"{series_id} year-over-year change is {yoy:+.2%} against a "
            f"{threshold_label} of {target:+.2%}."
        ),
        contribution=contribution,
        direction=_direction(contribution),
        contribution_explanation=(
            f"{series_id} YoY {yoy:+.2%} scaled against a {scale:.0%}-per-period "
            "band into a naive [-1, 1] contribution."
        ),
        evidence=[
            RegimeEvidenceItem(
                key=f"{series_id.lower()}_latest",
                label=f"{series_id} latest observation",
                value=latest.value,
                detail=f"Most recent published value for {latest.observation_date}.",
                observed_at=latest.observed_at,
                available_at=latest.available_at,
            ),
            RegimeEvidenceItem(
                key=f"{series_id.lower()}_year_ago",
                label=f"{series_id} year-ago observation",
                value=year_ago.value,
                detail=f"Closest available observation to one year earlier ({year_ago.observation_date}).",
                observed_at=year_ago.observed_at,
                available_at=year_ago.available_at,
            ),
        ],
    )


def _score_level_factor(
    *,
    key: str,
    name: str,
    series_id: str,
    observations: list[SeriesObservation],
    sign: float,
    center: float,
    scale: float,
    threshold_label: str,
) -> RegimeFactor:
    latest = _latest(series_id, observations)
    contribution = _clamp(sign * (latest.value - center) / scale)
    status = "pass" if contribution >= 0 else "caution"
    return RegimeFactor(
        key=key,
        name=name,
        raw_value=latest.value,
        threshold=center,
        filter_status=status,
        filter_explanation=(
            f"{series_id} latest level is {latest.value:.2f} against a "
            f"{threshold_label} of {center:.2f}."
        ),
        contribution=contribution,
        direction=_direction(contribution),
        contribution_explanation=(
            f"{series_id} level {latest.value:.2f} scaled against a naive "
            f"+/-{scale:.1f}-unit band into a [-1, 1] contribution."
        ),
        evidence=[
            RegimeEvidenceItem(
                key=f"{series_id.lower()}_latest",
                label=f"{series_id} latest observation",
                value=latest.value,
                detail=f"Most recent published value for {latest.observation_date}.",
                observed_at=latest.observed_at,
                available_at=latest.available_at,
            ),
        ],
    )


def compute_regime(
    series: dict[str, list[SeriesObservation]], as_of: date
) -> RegimeResult:
    """Compute a real, naive-by-design regime state from fetched FRED series.

    `series` keys are FRED series IDs (INDPRO, CPIAUCSL, PPIACO, PCEPILFE,
    PAYEMS, NFCI, VIXCLS, DGS10); every value returned traces to an
    observation in one of these lists — there is no hand-typed fallback.
    Raises InsufficientSeriesDataError if a required series has no
    observations, so a caller never silently fabricates state.
    """

    growth = _score_yoy_factor(
        key="growth",
        name="Growth",
        series_id="INDPRO",
        observations=series.get("INDPRO", []),
        as_of=as_of,
        sign=1.0,
        target=0.0,
        scale=0.03,
        threshold_label="zero-growth threshold",
    )
    inflation = _score_yoy_factor(
        key="inflation",
        name="Inflation",
        series_id="CPIAUCSL",
        observations=series.get("CPIAUCSL", []),
        as_of=as_of,
        sign=-1.0,
        target=0.02,
        scale=0.03,
        threshold_label="2% target",
    )
    liquidity = _score_level_factor(
        key="liquidity",
        name="Liquidity",
        series_id="NFCI",
        observations=series.get("NFCI", []),
        sign=-1.0,
        center=0.0,
        scale=1.0,
        threshold_label="neutral (0.0) financial-conditions level",
    )
    volatility = _score_level_factor(
        key="volatility",
        name="Volatility",
        series_id="VIXCLS",
        observations=series.get("VIXCLS", []),
        sign=-1.0,
        center=20.0,
        scale=10.0,
        threshold_label="long-run-ish VIX level",
    )
    ppi = _score_yoy_factor(
        key="ppi",
        name="Producer prices",
        series_id="PPIACO",
        observations=series.get("PPIACO", []),
        as_of=as_of,
        sign=-1.0,
        target=0.02,
        scale=0.05,
        threshold_label="2% target (wide PPI band — noisier than CPI)",
    )
    pce = _score_yoy_factor(
        key="pce",
        name="Core PCE inflation",
        series_id="PCEPILFE",
        observations=series.get("PCEPILFE", []),
        as_of=as_of,
        sign=-1.0,
        target=0.02,
        scale=0.02,
        threshold_label="the Fed's own 2% core PCE target",
    )
    employment = _score_yoy_factor(
        key="employment",
        name="Employment growth",
        series_id="PAYEMS",
        observations=series.get("PAYEMS", []),
        as_of=as_of,
        sign=1.0,
        target=0.0,
        scale=0.02,
        threshold_label="flat-payrolls threshold",
    )
    rates = _score_level_factor(
        key="rates",
        name="Long-term rates",
        series_id="DGS10",
        observations=series.get("DGS10", []),
        sign=-1.0,
        center=4.0,
        scale=2.0,
        threshold_label="naive neutral-ish 10-year yield level",
    )

    factors = [growth, inflation, ppi, pce, employment, liquidity, volatility, rates]
    composite = sum(WEIGHTS[factor.key] * factor.contribution for factor in factors)
    confidence = _clamp(0.5 + composite / 2.0, 0.05, 0.95)
    if composite >= 0.15:
        label = "Risk-on / expansion-leaning"
    elif composite <= -0.15:
        label = "Risk-off / contraction-leaning"
    else:
        label = "Mixed / transition"
    summary = (
        f"Naive weighted composite {composite:+.2f} from growth "
        f"{growth.contribution:+.2f}, inflation {inflation.contribution:+.2f}, "
        f"liquidity {liquidity.contribution:+.2f}, volatility "
        f"{volatility.contribution:+.2f} (weights {WEIGHTS}). First-pass "
        "formula on free FRED series; not yet decay- or collinearity-adjusted."
    )
    return RegimeResult(
        label=label,
        confidence=confidence,
        summary=summary,
        factors=factors,
        weights=dict(WEIGHTS),
    )
