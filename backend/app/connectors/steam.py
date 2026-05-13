"""Steam connector — read-only queries to the Steam Web API.

Shows the player summary, the library (owned games) and recently played titles.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.tools.base import Tool, ToolError

from .base import ConnectorError, require


class SteamClient:
    BASE = "https://api.steampowered.com"

    def __init__(self, api_key: str | None = None, steam_id: str | None = None) -> None:
        s = get_settings()
        self._key = api_key or s.steam_api_key
        self._uid = steam_id or s.steam_user_id
        self._http = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._http.aclose()

    @property
    def key(self) -> str:
        return require(self._key, "STEAM_API_KEY")

    @property
    def uid(self) -> str:
        return require(self._uid, "STEAM_USER_ID")

    async def _get(self, path: str, **params: Any) -> dict:
        params = {"key": self.key, **params}
        r = await self._http.get(f"{self.BASE}/{path}", params=params)
        if r.status_code >= 400:
            raise ConnectorError(f"steam {path}: {r.status_code} {r.text}")
        return r.json()

    async def summary(self) -> dict:
        data = await self._get(
            "ISteamUser/GetPlayerSummaries/v2/", steamids=self.uid
        )
        players = (data.get("response") or {}).get("players") or []
        return players[0] if players else {}

    async def recently_played(self, count: int = 5) -> list[dict]:
        data = await self._get(
            "IPlayerService/GetRecentlyPlayedGames/v1/",
            steamid=self.uid,
            count=count,
        )
        return (data.get("response") or {}).get("games") or []

    async def owned(self, limit: int = 50) -> list[dict]:
        data = await self._get(
            "IPlayerService/GetOwnedGames/v1/",
            steamid=self.uid,
            include_appinfo=1,
            include_played_free_games=1,
        )
        games = (data.get("response") or {}).get("games") or []
        games.sort(key=lambda g: -(g.get("playtime_forever") or 0))
        return games[:limit]


# ------------------------------- tools ----------------------------------

async def _steam_summary() -> dict:
    c = SteamClient()
    try:
        return await c.summary()
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


async def _steam_recent(count: int = 5) -> list[dict]:
    c = SteamClient()
    try:
        return await c.recently_played(count=int(count))
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


async def _steam_owned(limit: int = 50) -> list[dict]:
    c = SteamClient()
    try:
        return await c.owned(limit=int(limit))
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


STEAM_TOOLS = [
    Tool(
        name="steam.summary",
        description="Return Steam player summary (name, avatar, online status).",
        parameters={"type": "object", "properties": {}},
        fn=_steam_summary,
        category="steam",
        tags=["games", "read-only"],
    ),
    Tool(
        name="steam.recently_played",
        description="Return the last N games the user played (default 5).",
        parameters={
            "type": "object",
            "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 20}},
        },
        fn=_steam_recent,
        category="steam",
        tags=["games", "read-only"],
    ),
    Tool(
        name="steam.owned",
        description="List games in the library, sorted by total playtime.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
        },
        fn=_steam_owned,
        category="steam",
        tags=["games", "read-only"],
    ),
]
