from __future__ import annotations

from typing import Any

import httpx
import pytest

from backend.providers.fred import FredFetchError, fetch_series_observations


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
    monkeypatch.setattr("backend.providers.fred.httpx.Client", _Client)


COMMON_KWARGS = dict(
    observation_start="2025-08-25",
    observation_end="2026-08-24",
    realtime_start="2026-08-24",
    realtime_end="2026-08-24",
)


def test_fetch_uses_api_key_query_param_not_url_or_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        _Response(
            200,
            {
                "units": "lin",
                "observations": [
                    {"date": "2026-08-01", "value": "102.3", "realtime_start": "2026-08-24", "realtime_end": "2026-08-24"}
                ],
            },
        ),
    )
    secret = "fred-real-secret"
    results = fetch_series_observations(secret, "INDPRO", **COMMON_KWARGS)
    assert len(results) == 1
    assert results[0] == (
        "INDPRO", "2026-08-01", 102.3, "2026-08-24", "2026-08-24", "lin"
    )
    assert secret not in _Client.captured["url"]
    assert "Authorization" not in _Client.captured["kwargs"]["headers"]
    assert _Client.captured["params"]["api_key"] == secret
    assert _Client.captured["params"]["series_id"] == "INDPRO"
    assert _Client.captured["params"]["file_type"] == "json"
    assert _Client.captured["kwargs"]["follow_redirects"] is False
    assert _Client.captured["kwargs"]["trust_env"] is False


def test_missing_value_marker_becomes_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        _Response(200, {"units": "lin", "observations": [{"date": "2026-08-01", "value": "."}]}),
    )
    results = fetch_series_observations("secret", "NFCI", **COMMON_KWARGS)
    assert results[0].value is None


def test_non_200_status_raises_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _Response(503))
    with pytest.raises(FredFetchError):
        fetch_series_observations("secret", "VIXCLS", **COMMON_KWARGS)


def test_non_json_body_raises_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _Response(200, raw_text="not json"))
    with pytest.raises(FredFetchError):
        fetch_series_observations("secret", "CPIAUCSL", **COMMON_KWARGS)


def test_missing_observations_key_raises_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _Response(200, {"units": "lin"}))
    with pytest.raises(FredFetchError):
        fetch_series_observations("secret", "INDPRO", **COMMON_KWARGS)


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

    monkeypatch.setattr("backend.providers.fred.httpx.Client", RaisingClient)
    with pytest.raises(FredFetchError):
        fetch_series_observations("secret", "INDPRO", **COMMON_KWARGS)
