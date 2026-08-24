from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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
