from __future__ import annotations

from datetime import date

import pytest

from backend.engine.regime import InsufficientSeriesDataError, SeriesObservation, compute_regime, compute_regime_v2

AS_OF = date(2026, 8, 24)


def _monthly_dates(count: int, start_year: int = 2024, start_month: int = 1) -> list[str]:
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


def _constant_yoy_series(annual_rate: float, months: int = 20, base: float = 100.0) -> list[SeriesObservation]:
    """A monthly index compounding at a constant implied annual rate, so its
    YoY value is (approximately) the same real number at every point in the
    trailing window -- the concrete "steady, not surprising" case the
    surprise-based engine should score very differently from a fixed-target
    engine."""

    monthly_growth = (1.0 + annual_rate) ** (1.0 / 12.0)
    dates = _monthly_dates(months)
    values = [base * (monthly_growth**i) for i in range(months)]
    return _observations(dates, values)


def _daily_dates(count: int, start: date = date(2024, 1, 1)) -> list[str]:
    return [(start.fromordinal(start.toordinal() + i)).isoformat() for i in range(count)]


def _flat_level_series(value: float, count: int = 70) -> list[SeriesObservation]:
    dates = _daily_dates(count)
    return _observations(dates, [value] * count)


def _full_series(overrides: dict[str, list[SeriesObservation]] | None = None) -> dict[str, list[SeriesObservation]]:
    series = {
        "INDPRO": _constant_yoy_series(0.02),
        "CPIAUCSL": _constant_yoy_series(0.05),  # elevated but STEADY -- the surprise test case
        "PPIACO": _constant_yoy_series(0.02),
        "PCEPILFE": _constant_yoy_series(0.02),
        "PAYEMS": _constant_yoy_series(0.01),
        "NFCI": _flat_level_series(0.0, count=14),
        "VIXCLS": _flat_level_series(16.0, count=65),
        "DGS10": _flat_level_series(4.0, count=65),
    }
    if overrides:
        series.update(overrides)
    return series


def test_every_output_traces_to_a_real_input_value() -> None:
    result = compute_regime_v2(_full_series(), AS_OF)
    assert result.label in {"Risk-on / expansion-leaning", "Risk-off / contraction-leaning", "Mixed / transition"}
    assert 0.05 <= result.confidence <= 0.95
    assert {factor.key for factor in result.factors} == {
        "growth", "inflation", "ppi", "pce", "employment", "liquidity", "volatility", "rates",
    }
    for factor in result.factors:
        assert -1.0 <= factor.contribution <= 1.0
        assert factor.evidence


def test_weights_still_sum_to_one_v2_only_changes_scoring_not_weights() -> None:
    result = compute_regime_v2(_full_series(), AS_OF)
    assert sum(result.weights.values()) == pytest.approx(1.0)


def test_insufficient_history_raises_instead_of_fabricating() -> None:
    series = _full_series()
    series["NFCI"] = _flat_level_series(0.0, count=3)  # below the 12+1 window requirement
    with pytest.raises(InsufficientSeriesDataError):
        compute_regime_v2(series, AS_OF)


def test_a_new_surprise_moves_the_score_but_a_steady_repeat_does_not() -> None:
    """The concrete motivating case: v2 should treat "still 5% YoY, same as
    the recent trend" as close to neutral (no real surprise), and a genuine
    acceleration away from that trend as a real signal -- regardless of how
    far either value sits from any fixed target."""

    steady = compute_regime_v2(_full_series(), AS_OF)
    steady_inflation = next(f for f in steady.factors if f.key == "inflation")
    assert abs(steady_inflation.contribution) < 0.2  # steady trend -> small surprise -> near neutral

    accelerating_series = _full_series()
    dates = _monthly_dates(20)
    monthly_growth = (1.05) ** (1.0 / 12.0)
    values = [100.0 * (monthly_growth**i) for i in range(19)]
    values.append(values[-1] * 1.02)  # a real, sudden jump in the final print only
    accelerating_series["CPIAUCSL"] = _observations(dates, values)
    accelerated = compute_regime_v2(accelerating_series, AS_OF)
    accelerated_inflation = next(f for f in accelerated.factors if f.key == "inflation")

    # A sudden upside inflation surprise is bad news (sign=-1.0 in the engine) -> more negative contribution.
    assert accelerated_inflation.contribution < steady_inflation.contribution


def test_v1_is_unchanged_and_still_importable_for_historical_reproducibility() -> None:
    """v1 stays available and untouched -- naive-v1 snapshots already sealed
    in the database remain honestly reproducible from the exact code that
    produced them."""

    v1_series = {
        "INDPRO": [
            SeriesObservation("2025-08-24", 100.0, "2025-08-24T00:00:00Z", "2025-08-24T00:00:00Z"),
            SeriesObservation("2026-08-24", 102.0, "2026-08-24T00:00:00Z", "2026-08-24T00:00:00Z"),
        ],
        "CPIAUCSL": [
            SeriesObservation("2025-08-24", 300.0, "2025-08-24T00:00:00Z", "2025-08-24T00:00:00Z"),
            SeriesObservation("2026-08-24", 302.0, "2026-08-24T00:00:00Z", "2026-08-24T00:00:00Z"),
        ],
        "PPIACO": [
            SeriesObservation("2025-08-24", 250.0, "2025-08-24T00:00:00Z", "2025-08-24T00:00:00Z"),
            SeriesObservation("2026-08-24", 255.0, "2026-08-24T00:00:00Z", "2026-08-24T00:00:00Z"),
        ],
        "PCEPILFE": [
            SeriesObservation("2025-08-24", 120.0, "2025-08-24T00:00:00Z", "2025-08-24T00:00:00Z"),
            SeriesObservation("2026-08-24", 122.0, "2026-08-24T00:00:00Z", "2026-08-24T00:00:00Z"),
        ],
        "PAYEMS": [
            SeriesObservation("2025-08-24", 158000.0, "2025-08-24T00:00:00Z", "2025-08-24T00:00:00Z"),
            SeriesObservation("2026-08-24", 159000.0, "2026-08-24T00:00:00Z", "2026-08-24T00:00:00Z"),
        ],
        "NFCI": [SeriesObservation("2026-08-24", -0.2, "2026-08-24T00:00:00Z", "2026-08-24T00:00:00Z")],
        "VIXCLS": [SeriesObservation("2026-08-24", 15.0, "2026-08-24T00:00:00Z", "2026-08-24T00:00:00Z")],
        "DGS10": [SeriesObservation("2026-08-24", 4.0, "2026-08-24T00:00:00Z", "2026-08-24T00:00:00Z")],
    }
    result = compute_regime(v1_series, AS_OF)
    assert result.label in {"Risk-on / expansion-leaning", "Risk-off / contraction-leaning", "Mixed / transition"}
