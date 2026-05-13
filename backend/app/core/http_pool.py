"""Shared persistent httpx client pool.

Every connector and service that makes outbound HTTP requests should use
`get_client()` instead of creating its own AsyncClient.  This gives us:

* Connection reuse (keep-alive) per host — no TCP handshake on every request
* Configurable timeouts and retries
* A single place to add proxy / SSL settings

Usage:
    from app.core.http_pool import get_client

    async def my_func():
        c = await get_client()
        r = await c.get("https://api.vk.com/method/...")
"""
from __future__ import annotations

import asyncio
from typing import Optional

import httpx

_client: Optional[httpx.AsyncClient] = None
_lock = asyncio.Lock()

_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
_DEFAULT_LIMITS  = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=30.0,
)


async def get_client() -> httpx.AsyncClient:
    """Return the shared persistent AsyncClient, creating it on first call."""
    global _client
    if _client is None or _client.is_closed:
        async with _lock:
            if _client is None or _client.is_closed:
                _client = httpx.AsyncClient(
                    timeout=_DEFAULT_TIMEOUT,
                    limits=_DEFAULT_LIMITS,
                    http2=False,          # h2 adds overhead for these short-lived APIs
                    follow_redirects=True,
                )
    return _client


async def close_client() -> None:
    """Call on application shutdown to drain connections cleanly."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
    _client = None
