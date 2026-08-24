from __future__ import annotations

from datetime import date

import pytest

from backend.engine.regime import (
    InsufficientSeriesDataError,
    SeriesObservation,
    compute_regime,
)

AS_OF = date(2026, 8, 24)


def _series(
    latest_value: float, year_ago_value: float, *, latest_date: str = "2026-08-24", year_ago_date: str = "2025-08-24"
) -> list[SeriesObservation]:
    return [
        SeriesObservation(
            observation_date=year_ago_date,
            value=year_ago_value,
            observed_at=f"{year_ago_date}T00:00:00Z",
            available_at=f"{year_ago_date}T00:00:00Z",
        ),
        SeriesObservation(
            observation_date=latest_date,
            value=latest_value,
            observed_at=f"{latest_date}T00:00:00Z",
            available_at=f"{latest_date}T00:00:00Z",
        ),
    ]


def _level_series(value: float, *, observation_date: str = "2026-08-24") -> list[SeriesObservation]:
    return [
        SeriesObservation(
            observation_date=observation_date,
            value=value,
            observed_at=f"{observation_date}T00:00:00Z",
            available_at=f"{observation_date}T00:00:00Z",
        )
    ]


def _baseline_series() -> dict[str, list[SeriesObservation]]:
    return {
        "INDPRO": _series(102.0, 100.0),  # +2% YoY growth
        "CPIAUCSL": _series(302.0, 300.0),  # ~0.67% YoY inflation, below target
        "PPIACO": _series(255.0, 250.0),  # +2% YoY, near target
        "PCEPILFE": _series(122.0, 120.0),  # ~1.67% YoY core PCE, near target
        "PAYEMS": _series(159000.0, 158000.0),  # ~0.63% YoY payroll growth
        "NFCI": _level_series(-0.2),  # loose conditions
        "VIXCLS": _level_series(15.0),  # calm
        "DGS10": _level_series(4.0),  # at the naive neutral level
    }


def test_every_output_traces_to_a_real_input_value() -> None:
    result = compute_regime(_baseline_series(), AS_OF)
    assert result.label in {
        "Risk-on / expansion-leaning",
        "Risk-off / contraction-leaning",
        "Mixed / transition",
    }
    assert 0.05 <= result.confidence <= 0.95
    assert {factor.key for factor in result.factors} == {
        "growth",
        "inflation",
        "ppi",
        "pce",
        "employment",
        "liquidity",
        "volatility",
        "rates",
    }
    for factor in result.factors:
        assert -1.0 <= factor.contribution <= 1.0
        assert factor.evidence  # every factor cites at least one real observation


def test_different_inputs_produce_different_traceable_outputs() -> None:
    """The core requirement this engine exists to satisfy: this is a real
    function, not a hand-typed value. Changing the input must change the
    output, deterministically and explainably."""

    calm = compute_regime(_baseline_series(), AS_OF)

    stressed_series = _baseline_series()
    stressed_series["VIXCLS"] = _level_series(45.0)  # volatility spike
    stressed_series["NFCI"] = _level_series(1.2)  # tight conditions
    stressed = compute_regime(stressed_series, AS_OF)

    assert stressed.confidence < calm.confidence
    calm_by_key = {factor.key: factor.contribution for factor in calm.factors}
    stressed_by_key = {factor.key: factor.contribution for factor in stressed.factors}
    assert stressed_by_key["volatility"] < calm_by_key["volatility"]
    assert stressed_by_key["liquidity"] < calm_by_key["liquidity"]
    # Growth/inflation inputs were unchanged between the two scenarios.
    assert stressed_by_key["growth"] == calm_by_key["growth"]
    assert stressed_by_key["inflation"] == calm_by_key["inflation"]


def test_weights_sum_to_one() -> None:
    result = compute_regime(_baseline_series(), AS_OF)
    assert sum(result.weights.values()) == pytest.approx(1.0)


def test_missing_series_raises_instead_of_fabricating_a_value() -> None:
    series = _baseline_series()
    del series["NFCI"]
    with pytest.raises(InsufficientSeriesDataError):
        compute_regime(series, AS_OF)


def test_composite_thresholds_produce_expected_labels() -> None:
    strongly_positive = {
        "INDPRO": _series(110.0, 100.0),
        "CPIAUCSL": _series(302.0, 300.0),
        "PPIACO": _series(255.0, 250.0),
        "PCEPILFE": _series(122.0, 120.0),
        "PAYEMS": _series(162000.0, 158000.0),
        "NFCI": _level_series(-1.0),
        "VIXCLS": _level_series(10.0),
        "DGS10": _level_series(2.5),
    }
    assert compute_regime(strongly_positive, AS_OF).label == "Risk-on / expansion-leaning"

    strongly_negative = {
        "INDPRO": _series(90.0, 100.0),
        "CPIAUCSL": _series(312.0, 300.0),
        "PPIACO": _series(270.0, 250.0),
        "PCEPILFE": _series(128.0, 120.0),
        "PAYEMS": _series(155000.0, 158000.0),
        "NFCI": _level_series(1.0),
        "VIXCLS": _level_series(40.0),
        "DGS10": _level_series(6.0),
    }
    assert compute_regime(strongly_negative, AS_OF).label == "Risk-off / contraction-leaning"
