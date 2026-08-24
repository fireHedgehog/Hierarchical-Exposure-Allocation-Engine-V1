from __future__ import annotations

import ipaddress
from collections.abc import Callable
from urllib.parse import urlsplit

from fastapi import HTTPException, Request


DEFAULT_ADMIN_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
)


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.rstrip(".").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_admin_origins(raw_origins: str | None) -> frozenset[str]:
    values = (
        [value.strip() for value in raw_origins.split(",") if value.strip()]
        if raw_origins is not None
        else list(DEFAULT_ADMIN_ORIGINS)
    )
    normalized: set[str] = set()
    for value in values:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not _is_loopback_host(parsed.hostname)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "HEAE_ADMIN_ALLOWED_ORIGINS must contain exact loopback HTTP(S) origins only."
            )
        normalized.add(f"{parsed.scheme}://{parsed.netloc}")
    if not normalized:
        raise ValueError("At least one loopback admin origin is required.")
    return frozenset(normalized)


def direct_loopback_guard(request: Request) -> None:
    if any(
        header in request.headers
        for header in ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto")
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "operator_proxy_rejected",
                "message": "The operator console cannot be accessed through a forwarding proxy.",
            },
        )
    client_host = request.client.host if request.client else None
    host_header = request.headers.get("host", "")
    try:
        host = urlsplit(f"//{host_header}").hostname
    except ValueError:
        host = None
    if not _is_loopback_host(client_host) or not _is_loopback_host(host):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "operator_loopback_required",
                "message": "The operator console is available only over a direct loopback connection.",
            },
        )


def operator_guard(
    expected_action: str, allowed_origins: frozenset[str]
) -> Callable[[Request], None]:
    def guard(request: Request) -> None:
        direct_loopback_guard(request)
        origin = request.headers.get("origin")
        if origin not in allowed_origins:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "operator_origin_rejected",
                    "message": "The request Origin is not an approved local operator origin.",
                },
            )
        if request.headers.get("x-operator-action") != expected_action:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "operator_action_required",
                    "message": f"Confirm this operation with X-Operator-Action: {expected_action}.",
                },
            )

    return guard
