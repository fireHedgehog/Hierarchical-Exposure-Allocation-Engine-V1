from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class VerificationResult:
    status: str
    message: str
    http_status: int | None = None
    latency_ms: int | None = None
    error_code: str | None = None


class ProviderVerifier(Protocol):
    def verify(self, secret: str) -> VerificationResult:
        ...


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
