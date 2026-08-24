from __future__ import annotations

from datetime import date, timedelta

from backend.engine.factors.types import Bar
from backend.engine.regime.types import SeriesObservation
from backend.engine.research.factor_symbol_correlation import compute_factor_symbol_significance

START = date(2016, 1, 1)
OBSERVATION_SPACING_DAYS = 30  # > the 21-trading-day forward window, so windows never overlap
FORWARD_HORIZON_DAYS = 21


def _observations(count: int, base_value: float = 100.0) -> list[SeriesObservation]:
    dates = [START + timedelta(days=OBSERVATION_SPACING_DAYS * i) for i in range(count)]
    return [
        SeriesObservation(
            observation_date=d.isoformat(),
            value=base_value + i,
            observed_at=f"{d.isoformat()}T00:00:00Z",
            available_at=f"{d.isoformat()}T00:00:00Z",
        )
        for i, d in enumerate(dates)
    ]


def _engineered_correlated_bars(observations: list[SeriesObservation], k: float) -> list[Bar]:
    """Real, densely-dated daily bars engineered so this symbol's forward
    return over each observation's window is EXACTLY k times that
    observation's own real period-over-period change -- proves the
    date-alignment and pairing logic, not just that scipy can correlate two
    arbitrary arrays.
    """

    last_date = date.fromisoformat(observations[-1].observation_date)
    total_days = (last_date - START).days + FORWARD_HORIZON_DAYS + 5
    closes = [100.0] * total_days
    for i in range(1, len(observations)):
        previous, current = observations[i - 1], observations[i]
        change = (current.value - previous.value) / abs(previous.value)
        entry_offset = (date.fromisoformat(current.observation_date) - START).days
        exit_offset = entry_offset + FORWARD_HORIZON_DAYS
        closes[exit_offset] = 100.0 * (1 + k * change)
    return [Bar(time=(START + timedelta(days=d)).isoformat(), close=closes[d]) for d in range(total_days)]


def test_detects_a_real_engineered_correlation_from_paired_dates() -> None:
    observations = _observations(60)
    bars = _engineered_correlated_bars(observations, k=5.0)

    run = compute_factor_symbol_significance(
        {"TEST_FACTOR": observations}, {"TEST_SYMBOL": bars}, min_samples=10
    )

    assert run.factor_count == 1
    assert run.symbol_count == 1
    assert run.test_count == 1
    result = run.results[0]
    assert result.status == "ok"
    assert result.sample_size == 59  # 60 observations -> 59 period-over-period changes
    assert result.correlation is not None and result.correlation > 0.999
    assert result.significant is True
    assert result.direction == "positive"


def test_inverse_relationship_is_reported_as_negative_direction() -> None:
    observations = _observations(60)
    bars = _engineered_correlated_bars(observations, k=-5.0)

    run = compute_factor_symbol_significance(
        {"TEST_FACTOR": observations}, {"TEST_SYMBOL": bars}, min_samples=10
    )
    result = run.results[0]
    assert result.correlation is not None and result.correlation < -0.999
    assert result.significant is True
    assert result.direction == "negative"


def test_too_few_observations_is_reported_as_insufficient_data_not_a_fabricated_correlation() -> None:
    sufficient = _observations(60)
    scarce = _observations(8)  # 7 changes, below the 10-sample floor used in this test
    bars = _engineered_correlated_bars(sufficient, k=3.0)

    run = compute_factor_symbol_significance(
        {"SUFFICIENT_FACTOR": sufficient, "SCARCE_FACTOR": scarce},
        {"TEST_SYMBOL": bars},
        min_samples=10,
    )

    assert run.factor_count == 2
    assert run.test_count == 1  # only the sufficient factor was actually tested
    by_factor = {result.factor_key: result for result in run.results}
    assert by_factor["SUFFICIENT_FACTOR"].status == "ok"
    scarce_result = by_factor["SCARCE_FACTOR"]
    assert scarce_result.status == "insufficient_data"
    assert scarce_result.correlation is None
    assert scarce_result.significant is False
    assert scarce_result.direction == "inconclusive"


def test_run_metadata_reflects_the_actual_grid_shape() -> None:
    observations = _observations(60)
    bars_a = _engineered_correlated_bars(observations, k=2.0)
    bars_b = _engineered_correlated_bars(observations, k=-2.0)

    run = compute_factor_symbol_significance(
        {"FACTOR": observations}, {"SYMBOL_A": bars_a, "SYMBOL_B": bars_b}, min_samples=10, alpha=0.05
    )

    assert run.factor_count == 1
    assert run.symbol_count == 2
    assert run.test_count == 2
    assert run.method == "pearson_forward_return"
    assert run.correction_method == "benjamini_hochberg"
    assert run.forward_horizon_days == FORWARD_HORIZON_DAYS
    assert run.significant_count == 2  # both engineered pairs are strongly correlated
