from __future__ import annotations

from typing import Any

import httpx
import pytest

from backend.providers.yahoo import PriceFetchError, fetch_daily_bars


class _Response:
    def __init__(self, status_code: int, payload: Any = None, *, raw_text: str | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self._raw_text = raw_text

    def json(self) -> Any:
        if self._raw_text is not None:
            raise ValueError("not json")
        return self._payload


class _Client:
    captured: dict[str, Any] = {}

    def __init__(self, **kwargs: Any) -> None:
        _Client.captured["kwargs"] = kwargs

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def get(self, url: str, *, params: dict[str, Any]) -> _Response:
        _Client.captured["url"] = url
        _Client.captured["params"] = params
        return _Client.next_response  # type: ignore[attr-defined]


def _install(monkeypatch: pytest.MonkeyPatch, response: _Response) -> None:
    _Client.captured = {}
    _Client.next_response = response  # type: ignore[attr-defined]
    monkeypatch.setattr("backend.providers.yahoo.httpx.Client", _Client)


def _chart_payload(
    *,
    timestamps: list[int],
    closes: list[float | None],
    adjcloses: list[float | None] | None = None,
    opens: list[float | None] | None = None,
    highs: list[float | None] | None = None,
    lows: list[float | None] | None = None,
) -> dict[str, Any]:
    quote: dict[str, Any] = {
        "close": closes,
        "open": opens if opens is not None else [None] * len(timestamps),
        "high": highs if highs is not None else [None] * len(timestamps),
        "low": lows if lows is not None else [None] * len(timestamps),
        "volume": [None] * len(timestamps),
    }
    indicators: dict[str, Any] = {"quote": [quote]}
    if adjcloses is not None:
        indicators["adjclose"] = [{"adjclose": adjcloses}]
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "firstTradeDate": timestamps[0] if timestamps else 0,
                        "dataGranularity": "1d",
                        "exchangeTimezoneName": "America/New_York",
                    },
                    "timestamp": timestamps,
                    "indicators": indicators,
                }
            ],
            "error": None,
        }
    }


def test_fetch_uses_adjusted_close_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        _Response(
            200,
            _chart_payload(
                timestamps=[1735689600, 1735776000],
                closes=[100.0, 101.0],
                adjcloses=[95.0, 96.0],
                opens=[90.0, 91.0],
                highs=[110.0, 111.0],
                lows=[80.0, 81.0],
            ),
        ),
    )
    bars = fetch_daily_bars("SPY", range_="1y")
    assert len(bars) == 2
    assert bars[0].close == 95.0
    assert bars[1].close == 96.0
    assert bars[0].raw_close == 100.0
    assert bars[0].adjusted_close == 95.0
    assert bars[0].adjustment_factor == pytest.approx(0.95)
    assert bars[0].adjusted_open == pytest.approx(85.5)
    assert bars[0].adjusted_high == pytest.approx(104.5)
    assert bars[0].adjusted_low == pytest.approx(76.0)
    assert _Client.captured["params"]["range"] == "1y"
    assert _Client.captured["params"]["interval"] == "1d"
    assert "SPY" in _Client.captured["url"]
    assert bars.provider_data_granularity == "1d"
    assert bars.provider_exchange_timezone == "America/New_York"


def test_explicit_end_date_is_sent_as_end_exclusive_period2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        _Response(
            200,
            _chart_payload(
                timestamps=[1735689600],
                closes=[100.0],
                adjcloses=[100.0],
                opens=[99.0],
                highs=[101.0],
                lows=[98.0],
            ),
        ),
    )

    fetch_daily_bars("SPY", start_date="2025-01-01", end_date="2025-01-03")

    assert _Client.captured["params"]["period1"] == 1735689600
    assert _Client.captured["params"]["period2"] == 1735948800
    assert "range" not in _Client.captured["params"]


def test_negative_pre_epoch_first_trade_date_is_portable_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _chart_payload(
        timestamps=[1735689600],
        closes=[100.0],
        adjcloses=[100.0],
        opens=[99.0],
        highs=[101.0],
        lows=[98.0],
    )
    payload["chart"]["result"][0]["meta"]["firstTradeDate"] = -315619200
    _install(monkeypatch, _Response(200, payload))

    bars = fetch_daily_bars("OLD")

    assert bars.provider_first_trade_date == "1960-01-01"


def test_zero_pre_listing_placeholders_are_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        _Response(
            200,
            _chart_payload(
                timestamps=[1735689600, 1735776000],
                closes=[0.0, 10.0],
                adjcloses=[0.0, 10.0],
                opens=[0.0, 9.0],
                highs=[0.0, 11.0],
                lows=[0.0, 8.0],
            ),
        ),
    )

    bars = fetch_daily_bars("NEW")

    assert len(bars) == 1
    assert bars[0].raw_close == 10.0


def test_missing_adjclose_keeps_legacy_close_but_explicit_adjusted_basis_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        _Response(
            200,
            _chart_payload(
                timestamps=[1735689600],
                closes=[100.0],
                opens=[99.0],
                highs=[101.0],
                lows=[98.0],
            ),
        ),
    )
    bars = fetch_daily_bars("AAPL")
    assert bars[0].close == 100.0
    assert bars[0].raw_close == 100.0
    assert bars[0].adjusted_close is None
    assert bars[0].adjustment_factor is None
    assert bars[0].adjusted_open is None
    assert bars[0].adjusted_high is None
    assert bars[0].adjusted_low is None


def test_adjusted_ohlc_is_continuous_across_a_two_for_one_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        _Response(
            200,
            _chart_payload(
                timestamps=[1735689600, 1735776000],
                closes=[100.0, 50.0],
                adjcloses=[50.0, 50.0],
                opens=[98.0, 49.0],
                highs=[102.0, 51.0],
                lows=[96.0, 48.0],
            ),
        ),
    )

    before, after = fetch_daily_bars("SPLIT")

    assert before.adjustment_factor == pytest.approx(0.5)
    assert after.adjustment_factor == pytest.approx(1.0)
    assert before.adjusted_close == after.adjusted_close == 50.0
    assert before.adjusted_open == after.adjusted_open == 49.0


def test_partially_missing_adjusted_close_fails_the_whole_series(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        _Response(
            200,
            _chart_payload(
                timestamps=[1735689600, 1735776000],
                closes=[100.0, 101.0],
                adjcloses=[95.0, None],
                opens=[99.0, 100.0],
                highs=[101.0, 102.0],
                lows=[98.0, 99.0],
            ),
        ),
    )

    with pytest.raises(PriceFetchError, match="partially missing adjusted-close"):
        fetch_daily_bars("SPY")


def test_misaligned_quote_series_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _chart_payload(
        timestamps=[1735689600, 1735776000],
        closes=[100.0, 101.0],
        adjcloses=[100.0, 101.0],
    )
    payload["chart"]["result"][0]["indicators"]["quote"][0]["high"] = [101.0]
    _install(monkeypatch, _Response(200, payload))

    with pytest.raises(PriceFetchError, match="high series is missing or misaligned"):
        fetch_daily_bars("SPY")


def test_misaligned_adjusted_close_series_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        _Response(
            200,
            _chart_payload(
                timestamps=[1735689600, 1735776000],
                closes=[100.0, 101.0],
                adjcloses=[100.0],
            ),
        ),
    )

    with pytest.raises(PriceFetchError, match="adjusted-close series is misaligned"):
        fetch_daily_bars("SPY")


def test_null_close_session_is_skipped_not_fabricated(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        _Response(200, _chart_payload(timestamps=[1735689600, 1735776000], closes=[100.0, None])),
    )
    bars = fetch_daily_bars("XLF")
    assert len(bars) == 1


def test_yahoo_error_payload_raises_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        _Response(200, {"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}}),
    )
    with pytest.raises(PriceFetchError):
        fetch_daily_bars("NOTAREALSYM")


def test_non_200_status_raises_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _Response(503))
    with pytest.raises(PriceFetchError):
        fetch_daily_bars("SPY")


def test_non_json_body_raises_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _Response(200, raw_text="not json"))
    with pytest.raises(PriceFetchError):
        fetch_daily_bars("SPY")


def test_all_null_closes_raises_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _Response(200, _chart_payload(timestamps=[1735689600], closes=[None])))
    with pytest.raises(PriceFetchError):
        fetch_daily_bars("SPY")


def test_network_error_raises_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class RaisingClient:
        def __init__(self, **_: Any) -> None:
            pass

        def __enter__(self) -> "RaisingClient":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get(self, *_: Any, **__: Any) -> Any:
            raise httpx.ConnectError("no route to host")

    monkeypatch.setattr("backend.providers.yahoo.httpx.Client", RaisingClient)
    with pytest.raises(PriceFetchError):
        fetch_daily_bars("SPY")
