"""Shared connector helpers."""
from __future__ import annotations


class ConnectorError(Exception):
    """Raised by a connector when the call fails for a user-reportable reason
    (missing credentials, HTTP error, invalid response, ...)."""


def require(value: str, name: str) -> str:
    if not value:
        raise ConnectorError(
            f"{name} is not configured. Set it in backend/.env and restart claw."
        )
    return value
