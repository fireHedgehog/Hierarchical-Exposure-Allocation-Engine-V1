from __future__ import annotations

import time
from typing import Any, NamedTuple

import httpx

from backend.providers import VerificationResult


class FredV2Verifier:
    """Perform one bounded credential smoke test against the FRED v2 API."""

    endpoint = "https://api.stlouisfed.org/fred/v2/release/observations"

    def verify(self, secret: str) -> VerificationResult:
        started = time.perf_counter()
        try:
            with httpx.Client(
                timeout=httpx.Timeout(5.0, connect=3.0),
                follow_redirects=False,
                trust_env=False,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {secret}",
                    "User-Agent": "HEAE-local-operator/0.1",
                },
            ) as client:
                response = client.get(
                    self.endpoint,
                    params={"release_id": 10, "format": "json", "limit": 1},
                )
        except httpx.TimeoutException:
            return self._result(
                started,
                status="unreachable",
                error_code="provider_timeout",
                message="FRED did not respond before the smoke-test timeout.",
            )
        except httpx.NetworkError:
            return self._result(
                started,
                status="unreachable",
                error_code="provider_unreachable",
                message="FRED could not be reached from this machine.",
            )
        except httpx.HTTPError:
            return self._result(
                started,
                status="provider_error",
                error_code="http_client_error",
                message="The FRED smoke test could not complete.",
            )

        status = response.status_code
        if status == 200:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if not isinstance(payload, dict) or not isinstance(payload.get("release"), dict):
                return self._result(
                    started,
                    status="invalid_response",
                    http_status=status,
                    error_code="unexpected_response_shape",
                    message="FRED accepted the request but returned an unexpected response.",
                )
            return self._result(
                started,
                status="healthy",
                http_status=status,
                message="FRED API v2 accepted the credential.",
            )
        if status in {401, 403}:
            return self._result(
                started,
                status="invalid_credentials",
                http_status=status,
                error_code="invalid_credentials",
                message="FRED rejected the credential.",
            )
        if status == 429:
            return self._result(
                started,
                status="rate_limited",
                http_status=status,
                error_code="provider_rate_limited",
                message="FRED rate-limited the smoke test; wait before trying again.",
            )
        if 300 <= status < 400:
            return self._result(
                started,
                status="provider_error",
                http_status=status,
                error_code="unexpected_redirect",
                message="FRED returned a redirect; redirects are disabled for credential safety.",
            )
        return self._result(
            started,
            status="provider_error",
            http_status=status,
            error_code="provider_rejected_request",
            message="FRED rejected the smoke-test request.",
        )

    @staticmethod
    def _result(
        started: float,
        *,
        status: str,
        message: str,
        http_status: int | None = None,
        error_code: str | None = None,
    ) -> VerificationResult:
        return VerificationResult(
            status=status,
            message=message,
            http_status=http_status,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            error_code=error_code,
        )


class FredObservation(NamedTuple):
    series_id: str
    observation_date: str
    value: float | None
    realtime_start: str
    realtime_end: str
    units: str | None


class FredFetchError(RuntimeError):
    """A real FRED series fetch failed. Callers must write no rows on this error."""


# FRED's real, documented data endpoint is unversioned and takes `api_key` as a
# query parameter — there is no header-based auth option here. This differs
# from FredV2Verifier above (a lightweight existing credential smoke test that
# uses an invented "v2"/Bearer convention); that one is out of scope for this
# change and is left as-is. Real ingestion must match the real API, so this
# function intentionally does not reuse FredV2Verifier's endpoint or headers.
SERIES_OBSERVATIONS_ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series_observations(
    secret: str,
    series_id: str,
    *,
    observation_start: str,
    observation_end: str,
    realtime_start: str,
    realtime_end: str,
) -> list[FredObservation]:
    """Fetch one series' observations as of a pinned ALFRED vintage.

    Pinning realtime_start == realtime_end == the pipeline run date asks FRED
    for the values as they were actually published as of that date, not
    today's revised numbers — the point-in-time correctness this project's
    non-negotiable rules require. Raises FredFetchError on any failure; never
    returns a partial list, so callers can safely write nothing on error.
    """

    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            trust_env=False,
            headers={"Accept": "application/json", "User-Agent": "HEAE-local-operator/0.1"},
        ) as client:
            response = client.get(
                SERIES_OBSERVATIONS_ENDPOINT,
                params={
                    "series_id": series_id,
                    "api_key": secret,
                    "file_type": "json",
                    "observation_start": observation_start,
                    "observation_end": observation_end,
                    "realtime_start": realtime_start,
                    "realtime_end": realtime_end,
                },
            )
    except httpx.HTTPError as error:
        raise FredFetchError(
            f"{series_id}: request failed ({error.__class__.__name__})."
        ) from error

    if response.status_code != 200:
        raise FredFetchError(f"{series_id}: FRED returned HTTP {response.status_code}.")
    try:
        payload: Any = response.json()
    except ValueError as error:
        raise FredFetchError(f"{series_id}: FRED returned a non-JSON response.") from error
    observations = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(observations, list):
        raise FredFetchError(f"{series_id}: unexpected response shape from FRED.")

    units = payload.get("units") if isinstance(payload, dict) else None
    results: list[FredObservation] = []
    for row in observations:
        if not isinstance(row, dict) or "date" not in row:
            raise FredFetchError(f"{series_id}: unexpected observation row shape from FRED.")
        raw_value = row.get("value")
        try:
            value = None if raw_value in (None, ".") else float(raw_value)
        except (TypeError, ValueError) as error:
            raise FredFetchError(
                f"{series_id}: non-numeric observation value {raw_value!r}."
            ) from error
        results.append(
            FredObservation(
                series_id=series_id,
                observation_date=row["date"],
                value=value,
                realtime_start=row.get("realtime_start", realtime_start),
                realtime_end=row.get("realtime_end", realtime_end),
                units=units,
            )
        )
    return results
