from __future__ import annotations

from datetime import date

import pytest

from backend.engine.regime import InsufficientSeriesDataError, SeriesObservation, compute_regime_v3

AS_OF = date(2026, 8, 24)


def _monthly_dates(count: int, start_year: int = 2018, start_month: int = 1) -> list[str]:
    dates = []
    year, month = start_year, start_month
    for _ in range(count):
        dates.append(date(year, month, 1).isoformat())
        month += 1
        if month > 12:
            month = 1
            year += 1
    return dates


def _observations(dates: list[str], values: list[float]) -> list[SeriesObservation]:
    return [
        SeriesObservation(observation_date=d, value=v, observed_at=f"{d}T00:00:00Z", available_at=f"{d}T00:00:00Z")
        for d, v in zip(dates, values)
    ]


def _constant_yoy_series(annual_rate: float, months: int = 96, base: float = 100.0) -> list[SeriesObservation]:
    monthly_growth = (1.0 + annual_rate) ** (1.0 / 12.0)
    dates = _monthly_dates(months)
    values = [base * (monthly_growth**i) for i in range(months)]
    return _observations(dates, values)


def _daily_dates(count: int, start: date = date(2018, 1, 1)) -> list[str]:
    return [(start.fromordinal(start.toordinal() + i)).isoformat() for i in range(count)]


def _flat_level_series(value: float, count: int = 300) -> list[SeriesObservation]:
    dates = _daily_dates(count)
    return _observations(dates, [value] * count)


def _full_series(overrides: dict[str, list[SeriesObservation]] | None = None) -> dict[str, list[SeriesObservation]]:
    series = {
        "INDPRO": _constant_yoy_series(0.02),
        "PAYEMS": _constant_yoy_series(0.01),
        "GDPC1": _constant_yoy_series(0.02, months=24),
        "CPIAUCSL": _constant_yoy_series(0.02),
        "PCEPILFE": _constant_yoy_series(0.02),
        "PPIACO": _constant_yoy_series(0.02),
        "DGS10": _flat_level_series(4.0),
        "DGS30": _flat_level_series(4.3),
        "DFII10": _flat_level_series(2.0),
        "NFCI": _flat_level_series(0.0, count=40),
        "VIXCLS": _flat_level_series(16.0),
        "BAMLH0A0HYM2": _flat_level_series(3.0, count=30),
        "BAMLC0A0CM": _flat_level_series(1.0, count=30),
    }
    if overrides:
        series.update(overrides)
    return series


def test_every_output_traces_to_a_real_input_value() -> None:
    result = compute_regime_v3(_full_series(), AS_OF)
    assert result.label in {"Risk-on / expansion-leaning", "Risk-off / contraction-leaning", "Mixed / transition"}
    assert 0.0 <= result.confidence <= 1.0
    expected_keys = {
        "growth", "employment", "gdp", "inflation", "pce", "ppi",
        "rates_10y", "rates_30y", "real_yield_10y",
        "liquidity", "volatility", "credit_hy", "credit_ig",
    }
    assert {factor.key for factor in result.factors} == expected_keys
    for factor in result.factors:
        assert -1.0 <= factor.contribution <= 1.0
        assert factor.evidence


def test_weights_sum_to_one_and_are_cluster_balanced() -> None:
    result = compute_regime_v3(_full_series(), AS_OF)
    assert sum(result.weights.values()) == pytest.approx(1.0)
    # growth_inflation has 6 members -> each gets (1/3)/6; rate_level has 3 -> (1/3)/3;
    # market_stress has 4 -> (1/3)/4. No single member should carry more than
    # a rate_level or market_stress member despite growth_inflation's larger count.
    assert result.weights["growth"] == pytest.approx((1 / 3) / 6)
    assert result.weights["rates_10y"] == pytest.approx((1 / 3) / 3)
    assert result.weights["credit_hy"] == pytest.approx((1 / 3) / 4)


def test_insufficient_history_everywhere_raises_instead_of_fabricating() -> None:
    thin_series = {key: _flat_level_series(1.0, count=2) for key in _full_series()}
    with pytest.raises(InsufficientSeriesDataError):
        compute_regime_v3(thin_series, AS_OF)


def test_null_tolerant_missing_one_cluster_member_does_not_crash() -> None:
    """Real, established macro-composite behavior: a missing series is
    skipped, not a hard failure, as long as something in each cluster
    still has real data."""

    series = _full_series()
    del series["BAMLC0A0CM"]  # one of market_stress's 4 members missing
    result = compute_regime_v3(series, AS_OF)
    assert "credit_ig" not in {f.key for f in result.factors}
    assert "credit_hy" in {f.key for f in result.factors}
    # market_stress's remaining 3 members now split that cluster's 1/3 share evenly.
    assert result.weights["credit_hy"] == pytest.approx((1 / 3) / 3)


def test_null_tolerant_missing_whole_cluster_still_scores() -> None:
    series = _full_series()
    for key in ("NFCI", "VIXCLS", "BAMLH0A0HYM2", "BAMLC0A0CM"):
        del series[key]
    result = compute_regime_v3(series, AS_OF)
    assert "liquidity" not in {f.key for f in result.factors}
    # remaining 2 clusters (growth_inflation, rate_level) split 1/2 each now.
    assert result.weights["growth"] == pytest.approx((1 / 2) / 6)


def test_zscore_near_trailing_mean_is_near_neutral_extreme_reading_is_not() -> None:
    """The concrete motivating case for the z-score fix: a value close to
    its own trailing history should score near-neutral; a genuinely extreme
    reading (many real std devs away) should not. Uses a mildly noisy
    trailing series, not a perfectly flat one -- real data always has some
    real variance, and a perfectly flat trailing window is the one real
    edge case this engine deliberately treats as z=0 (division-by-near-zero
    guard), which would make this test's premise degenerate."""

    dates = _daily_dates(300)
    noisy_values = [16.0 + (0.3 if i % 2 == 0 else -0.3) for i in range(299)]

    near_mean_values = noisy_values + [16.1]  # final print close to the real trailing mean
    near_mean_series = _full_series()
    near_mean_series["VIXCLS"] = _observations(dates, near_mean_values)
    near_mean = compute_regime_v3(near_mean_series, AS_OF)
    near_mean_vix = next(f for f in near_mean.factors if f.key == "volatility")
    assert abs(near_mean_vix.contribution) < 0.15

    spiking_values = noisy_values + [45.0]  # a real, sudden spike in the final print only
    spiking = _full_series()
    spiking["VIXCLS"] = _observations(dates, spiking_values)
    spiked = compute_regime_v3(spiking, AS_OF)
    spiked_vix = next(f for f in spiked.factors if f.key == "volatility")

    # A VIX spike is bad news (sign=-1.0) -> more negative contribution than a near-mean reading.
    assert spiked_vix.contribution < near_mean_vix.contribution
    assert spiked_vix.contribution < -0.3


def test_confidence_is_a_real_historical_hit_rate_not_a_naive_linear_transform() -> None:
    """v3's real fix over v1/v2: confidence is one of exactly 3 disclosed,
    real, backtested historical drawdown-likelihood numbers, not
    0.5 + composite/2."""

    from backend.engine.regime.scoring_v3 import (
        HISTORICAL_DRAWDOWN_RATE_CALM,
        HISTORICAL_DRAWDOWN_RATE_MIDDLE,
        HISTORICAL_DRAWDOWN_RATE_STRESSED,
    )

    result = compute_regime_v3(_full_series(), AS_OF)
    assert result.confidence in {
        HISTORICAL_DRAWDOWN_RATE_STRESSED, HISTORICAL_DRAWDOWN_RATE_MIDDLE, HISTORICAL_DRAWDOWN_RATE_CALM,
    }
