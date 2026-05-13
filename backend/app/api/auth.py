"""Minimal auth surface for claw.

GET /api/auth/token   — return the CSRF session token (same-origin only;
                        the browser frontend fetches it on startup and
                        includes it as X-Claw-Token on every mutating request).
GET /api/auth/ping    — health check that doesn't hit the DB.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.security import get_session_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/token")
def session_token() -> dict:
    """Return the CSRF token for this server session.

    This endpoint intentionally does NOT require auth — it's equivalent to
    a CSRF cookie. Security comes from same-origin policy: a page on a
    different origin cannot read this response, so it cannot include the
    correct X-Claw-Token header on mutating requests.
    """
    return {"token": get_session_token()}


@router.get("/ping")
def ping() -> dict:
    return {"ok": True}
