"""Spotify connector — uses the Authorization Code refresh-token flow.

Required .env values:
    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
    SPOTIFY_REFRESH_TOKEN

Scopes the refresh token must have been issued with:
    user-read-currently-playing
    user-read-playback-state
    user-modify-playback-state    (optional, for play/pause/next)
"""
from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.tools.base import Tool, ToolError

from .base import ConnectorError, require


class SpotifyClient:
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API = "https://api.spotify.com/v1"

    _cached_access: str = ""
    _cached_exp: float = 0.0

    def __init__(self) -> None:
        s = get_settings()
        self._cid = s.spotify_client_id
        self._csec = s.spotify_client_secret
        self._rtok = s.spotify_refresh_token
        self._http = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def _access_token(self) -> str:
        now = time.time()
        if SpotifyClient._cached_access and SpotifyClient._cached_exp - now > 30:
            return SpotifyClient._cached_access

        cid = require(self._cid, "SPOTIFY_CLIENT_ID")
        csec = require(self._csec, "SPOTIFY_CLIENT_SECRET")
        rtok = require(self._rtok, "SPOTIFY_REFRESH_TOKEN")
        basic = base64.b64encode(f"{cid}:{csec}".encode()).decode()
        r = await self._http.post(
            self.TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "refresh_token", "refresh_token": rtok},
        )
        if r.status_code >= 400:
            raise ConnectorError(f"spotify token refresh: {r.status_code} {r.text}")
        data = r.json()
        SpotifyClient._cached_access = data["access_token"]
        SpotifyClient._cached_exp = now + float(data.get("expires_in", 3600))
        return SpotifyClient._cached_access

    async def _api(self, method: str, path: str, **kwargs: Any) -> Any:
        tok = await self._access_token()
        headers = {"Authorization": f"Bearer {tok}", **kwargs.pop("headers", {})}
        r = await self._http.request(method, f"{self.API}{path}", headers=headers, **kwargs)
        if r.status_code == 204:
            return None
        if r.status_code >= 400:
            raise ConnectorError(f"spotify {method} {path}: {r.status_code} {r.text}")
        if not r.content:
            return None
        return r.json()

    async def now_playing(self) -> dict | None:
        data = await self._api("GET", "/me/player/currently-playing")
        if not data:
            return None
        item = data.get("item") or {}
        artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
        return {
            "is_playing": data.get("is_playing"),
            "progress_ms": data.get("progress_ms"),
            "title": item.get("name"),
            "artists": artists,
            "album": (item.get("album") or {}).get("name"),
            "duration_ms": item.get("duration_ms"),
            "url": (item.get("external_urls") or {}).get("spotify"),
            "image": _first_image(item),
        }

    async def pause(self) -> None:
        await self._api("PUT", "/me/player/pause")

    async def resume(self) -> None:
        await self._api("PUT", "/me/player/play")

    async def next(self) -> None:  # noqa: A003
        await self._api("POST", "/me/player/next")


def _first_image(item: dict) -> str | None:
    images = ((item.get("album") or {}).get("images")) or []
    return images[0]["url"] if images else None


# ------------------------------- tools ----------------------------------

async def _sp_now_playing() -> dict | None:
    c = SpotifyClient()
    try:
        return await c.now_playing()
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


async def _sp_control(action: str) -> dict:
    c = SpotifyClient()
    try:
        if action == "pause":
            await c.pause()
        elif action == "resume":
            await c.resume()
        elif action == "next":
            await c.next()
        else:
            raise ToolError(f"unknown action: {action}")
        return {"ok": True, "action": action}
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


SPOTIFY_TOOLS = [
    Tool(
        name="spotify.now_playing",
        description="Return the currently playing Spotify track, or null if nothing is playing.",
        parameters={"type": "object", "properties": {}},
        fn=_sp_now_playing,
        category="spotify",
        tags=["media", "read-only"],
    ),
    Tool(
        name="spotify.control",
        description="Control Spotify playback: 'pause', 'resume' or 'next' track.",
        parameters={
            "type": "object",
            "required": ["action"],
            "properties": {
                "action": {"type": "string", "enum": ["pause", "resume", "next"]}
            },
        },
        fn=_sp_control,
        category="spotify",
        tags=["media", "write"],
    ),
]
