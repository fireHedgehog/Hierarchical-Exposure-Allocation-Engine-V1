from __future__ import annotations

import statistics
from datetime import date, timedelta

from backend.engine.regime.scoring import WEIGHTS
from backend.engine.regime.types import (
    InsufficientSeriesDataError,
    RegimeEvidenceItem,
    RegimeFactor,
    RegimeResult,
    SeriesObservation,
)

# naive-v2: surprise-based scoring, not level-based.
#
# v1 (scoring.py) scores each factor against a hand-picked FIXED target
# (e.g. "is CPI YoY above or below 2%"). Real markets do not price macro
# releases that way -- they price the SURPRISE relative to an expectation
# that was already priced in. A CPI print of 3.1% is bullish or bearish
# depending on whether the market expected 3.5% or 2.8%, not on its
# distance from an arbitrary 2% target. This is well established in the
# macro-announcement literature (see Literature below) and is exactly what
# CME FedWatch-style tools do for policy-rate expectations.
#
# This project has no free real-time consensus/survey-expectations feed
# (Trading Economics is the planned paid source for that -- see
# roadmap.md phase 1; not purchased, not faked). The honest, disclosed
# proxy used here is a trailing statistical mean of the series' own
# history -- an adaptive-expectations stand-in, not a market consensus.
# Still real math over real fetched data; still hand-picked scale
# constants, still not fit or validated (Milestone 4 tests significance
# before any of this is trusted).
#
# Literature:
#   Andersen, T. G., Bollerslev, T., Diebold, F. X., & Vega, C. (2003).
#     Micro effects of macro announcements: Real-time price discovery in
#     foreign exchange. American Economic Review, 93(1), 38-62.
#   Balduzzi, P., Elton, E. J., & Green, T. C. (2001). Economic news and
#     bond prices: Evidence from the U.S. Treasury market. Journal of
#     Financial and Quantitative Analysis, 36(4), 523-543.
#   Krueger, J. T., & Kuttner, K. N. (1996). The Fed funds futures rate as
#     a predictor of Federal Reserve policy. Journal of Futures Markets,
#     16(8), 865-879.
#   Muth, J. F. (1961). Rational expectations and the theory of price
#     movements. Econometrica, 29(3), 315-335. (motivates why a trailing
#     mean is an adaptive- rather than rational-expectations proxy, and is
#     disclosed as such, not presented as a market consensus.)


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _direction(value: float, *, neutral_band: float = 0.05) -> str:
    if value > neutral_band:
        return "positive"
    if value < -neutral_band:
        return "negative"
    return "neutral"


def _yoy_series(observations: list[SeriesObservation]) -> list[tuple[date, float, SeriesObservation, SeriesObservation]]:
    """Real YoY value at every observation point (not just the latest), each
    paired with the exact two real observations used to compute it -- so a
    trailing average of this series is itself built entirely from real,
    traceable numbers."""

    ordered = sorted(observations, key=lambda item: item.observation_date)
    results: list[tuple[date, float, SeriesObservation, SeriesObservation]] = []
    for index, current in enumerate(ordered):
        current_date = date.fromisoformat(current.observation_date)
        target = current_date - timedelta(days=365)
        candidates = ordered[:index]
        if not candidates:
            continue
        year_ago = min(
            candidates,
            key=lambda item: abs((date.fromisoformat(item.observation_date) - target).days),
        )
        if abs((date.fromisoformat(year_ago.observation_date) - target).days) > 45:
            continue
        if year_ago.value == 0:
            continue
        yoy = (current.value - year_ago.value) / abs(year_ago.value)
        results.append((current_date, yoy, current, year_ago))
    return results


def _score_yoy_surprise_factor(
    *,
    key: str,
    name: str,
    series_id: str,
    observations: list[SeriesObservation],
    sign: float,
    scale: float,
    expectation_window: int,
) -> RegimeFactor:
    yoy_series = _yoy_series(observations)
    if len(yoy_series) < expectation_window + 1:
        raise InsufficientSeriesDataError(
            f"{series_id}: need at least {expectation_window + 1} real YoY points for a "
            f"trailing expectation, have {len(yoy_series)}."
        )
    latest_date, latest_yoy, latest_obs, latest_year_ago = yoy_series[-1]
    trailing = yoy_series[-(expectation_window + 1) : -1]
    expected_yoy = statistics.fmean(item[1] for item in trailing)
    surprise = latest_yoy - expected_yoy
    contribution = _clamp(sign * surprise / scale)
    status = "pass" if contribution >= 0 else "caution"
    return RegimeFactor(
        key=key,
        name=name,
        raw_value=latest_yoy,
        threshold=expected_yoy,
        filter_status=status,
        filter_explanation=(
            f"{series_id} YoY is {latest_yoy:+.2%}, a {surprise:+.2%}pt surprise against its own "
            f"trailing {expectation_window}-period average of {expected_yoy:+.2%}."
        ),
        contribution=contribution,
        direction=_direction(contribution),
        contribution_explanation=(
            f"Surprise {surprise:+.2%} (actual {latest_yoy:+.2%} vs. trailing-mean expectation "
            f"{expected_yoy:+.2%}) scaled by a naive {scale:.1%} band into [-1, 1] -- naive-v2: "
            "surprise-based, not a fixed hand-picked target."
        ),
        evidence=[
            RegimeEvidenceItem(
                key=f"{series_id.lower()}_latest",
                label=f"{series_id} latest observation",
                value=latest_obs.value,
                detail=f"Most recent published value for {latest_obs.observation_date}.",
                observed_at=latest_obs.observed_at,
                available_at=latest_obs.available_at,
            ),
            RegimeEvidenceItem(
                key=f"{series_id.lower()}_year_ago",
                label=f"{series_id} year-ago observation",
                value=latest_year_ago.value,
                detail=f"Closest available observation to one year earlier ({latest_year_ago.observation_date}).",
                observed_at=latest_year_ago.observed_at,
                available_at=latest_year_ago.available_at,
            ),
            RegimeEvidenceItem(
                key=f"{series_id.lower()}_trailing_expectation",
                label=f"{series_id} trailing {expectation_window}-period YoY average",
                value=expected_yoy,
                detail=(
                    f"Naive adaptive-expectations proxy: mean of the {expectation_window} real YoY "
                    "values immediately preceding this one (no real consensus/survey feed exists "
                    "for this project yet -- see roadmap.md)."
                ),
                observed_at=latest_obs.observed_at,
                available_at=latest_obs.available_at,
            ),
        ],
    )


def _score_level_surprise_factor(
    *,
    key: str,
    name: str,
    series_id: str,
    observations: list[SeriesObservation],
    sign: float,
    scale: float,
    expectation_window: int,
) -> RegimeFactor:
    ordered = sorted(observations, key=lambda item: item.observation_date)
    if len(ordered) < expectation_window + 1:
        raise InsufficientSeriesDataError(
            f"{series_id}: need at least {expectation_window + 1} observations for a trailing "
            f"expectation, have {len(ordered)}."
        )
    latest = ordered[-1]
    trailing = ordered[-(expectation_window + 1) : -1]
    expected_level = statistics.fmean(item.value for item in trailing)
    surprise = latest.value - expected_level
    contribution = _clamp(sign * surprise / scale)
    status = "pass" if contribution >= 0 else "caution"
    return RegimeFactor(
        key=key,
        name=name,
        raw_value=latest.value,
        threshold=expected_level,
        filter_status=status,
        filter_explanation=(
            f"{series_id} latest level is {latest.value:.2f}, a {surprise:+.2f} surprise against its "
            f"own trailing {expectation_window}-period average of {expected_level:.2f}."
        ),
        contribution=contribution,
        direction=_direction(contribution),
        contribution_explanation=(
            f"Surprise {surprise:+.2f} (actual {latest.value:.2f} vs. trailing-mean expectation "
            f"{expected_level:.2f}) scaled by a naive +/-{scale:.1f}-unit band into [-1, 1] -- "
            "naive-v2: surprise-based, not a fixed hand-picked center."
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
                key=f"{series_id.lower()}_trailing_expectation",
                label=f"{series_id} trailing {expectation_window}-period average",
                value=expected_level,
                detail=(
                    f"Naive adaptive-expectations proxy: mean of the {expectation_window} real "
                    "observations immediately preceding this one."
                ),
                observed_at=latest.observed_at,
                available_at=latest.available_at,
            ),
        ],
    )


def compute_regime_v2(
    series: dict[str, list[SeriesObservation]], as_of: date
) -> RegimeResult:
    """naive-v2 regime composite: identical weights and aggregation to v1
    (compute_regime), but every per-factor contribution is now a real
    surprise (actual vs. a trailing statistical expectation) instead of a
    deviation from a fixed hand-picked target. See module docstring for the
    literature motivating this change and the honest limits of the
    expectation proxy used.
    """

    growth = _score_yoy_surprise_factor(
        key="growth", name="Growth", series_id="INDPRO",
        observations=series.get("INDPRO", []), sign=1.0, scale=0.015, expectation_window=6,
    )
    inflation = _score_yoy_surprise_factor(
        key="inflation", name="Inflation", series_id="CPIAUCSL",
        observations=series.get("CPIAUCSL", []), sign=-1.0, scale=0.01, expectation_window=6,
    )
    ppi = _score_yoy_surprise_factor(
        key="ppi", name="Producer prices", series_id="PPIACO",
        observations=series.get("PPIACO", []), sign=-1.0, scale=0.02, expectation_window=6,
    )
    pce = _score_yoy_surprise_factor(
        key="pce", name="Core PCE inflation", series_id="PCEPILFE",
        observations=series.get("PCEPILFE", []), sign=-1.0, scale=0.008, expectation_window=6,
    )
    employment = _score_yoy_surprise_factor(
        key="employment", name="Employment growth", series_id="PAYEMS",
        observations=series.get("PAYEMS", []), sign=1.0, scale=0.005, expectation_window=6,
    )
    liquidity = _score_level_surprise_factor(
        key="liquidity", name="Liquidity", series_id="NFCI",
        observations=series.get("NFCI", []), sign=-1.0, scale=0.1, expectation_window=12,
    )
    volatility = _score_level_surprise_factor(
        key="volatility", name="Volatility", series_id="VIXCLS",
        observations=series.get("VIXCLS", []), sign=-1.0, scale=5.0, expectation_window=60,
    )
    rates = _score_level_surprise_factor(
        key="rates", name="Long-term rates", series_id="DGS10",
        observations=series.get("DGS10", []), sign=-1.0, scale=0.2, expectation_window=60,
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
        f"naive-v2 surprise-based composite {composite:+.2f} from growth "
        f"{growth.contribution:+.2f}, inflation {inflation.contribution:+.2f}, "
        f"liquidity {liquidity.contribution:+.2f}, volatility {volatility.contribution:+.2f} "
        f"(weights {WEIGHTS}). Each factor scores its surprise against its own trailing "
        "statistical expectation, not a fixed target -- see engine/regime/scoring_v2.py."
    )
    return RegimeResult(
        label=label,
        confidence=confidence,
        summary=summary,
        factors=factors,
        weights=dict(WEIGHTS),
    )
