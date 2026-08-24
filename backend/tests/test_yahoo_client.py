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
    *, timestamps: list[int], closes: list[float | None], adjcloses: list[float | None] | None = None
) -> dict[str, Any]:
    quote: dict[str, Any] = {"close": closes}
    indicators: dict[str, Any] = {"quote": [quote]}
    if adjcloses is not None:
        indicators["adjclose"] = [{"adjclose": adjcloses}]
    return {"chart": {"result": [{"timestamp": timestamps, "indicators": indicators}], "error": None}}


def test_fetch_uses_adjusted_close_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        _Response(
            200,
            _chart_payload(
                timestamps=[1735689600, 1735776000],
                closes=[100.0, 101.0],
                adjcloses=[95.0, 96.0],
            ),
        ),
    )
    bars = fetch_daily_bars("SPY", range_="1y")
    assert len(bars) == 2
    assert bars[0].close == 95.0
    assert bars[1].close == 96.0
    assert _Client.captured["params"]["range"] == "1y"
    assert _Client.captured["params"]["interval"] == "1d"
    assert "SPY" in _Client.captured["url"]


def test_fetch_falls_back_to_raw_close_without_adjclose(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _Response(200, _chart_payload(timestamps=[1735689600], closes=[100.0])))
    bars = fetch_daily_bars("AAPL")
    assert bars[0].close == 100.0


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
