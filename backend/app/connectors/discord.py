"""Discord connector via the REST API (no gateway / no intents).

Supports what the agents and the dashboard actually need:
  * who am I (the bot)
  * send a message to a channel
  * read the last N messages from a channel
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.tools.base import Tool, ToolError

from .base import ConnectorError, require


class DiscordClient:
    BASE = "https://discord.com/api/v10"

    def __init__(self, token: str | None = None) -> None:
        s = get_settings()
        self._token = token or s.discord_bot_token
        self._http = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        token = require(self._token, "DISCORD_BOT_TOKEN")
        return {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

    async def me(self) -> dict:
        r = await self._http.get(f"{self.BASE}/users/@me", headers=self._headers())
        if r.status_code >= 400:
            raise ConnectorError(f"discord /users/@me: {r.status_code} {r.text}")
        return r.json()

    async def send_message(self, channel_id: str, content: str) -> dict:
        r = await self._http.post(
            f"{self.BASE}/channels/{channel_id}/messages",
            headers=self._headers(),
            json={"content": content},
        )
        if r.status_code >= 400:
            raise ConnectorError(f"discord send: {r.status_code} {r.text}")
        return r.json()

    async def recent_messages(self, channel_id: str, limit: int = 20) -> list[dict]:
        r = await self._http.get(
            f"{self.BASE}/channels/{channel_id}/messages",
            headers=self._headers(),
            params={"limit": limit},
        )
        if r.status_code >= 400:
            raise ConnectorError(f"discord read: {r.status_code} {r.text}")
        msgs = r.json()
        # Reduce payload for LLM consumption.
        return [
            {
                "id": m.get("id"),
                "author": (m.get("author") or {}).get("username"),
                "content": m.get("content"),
                "timestamp": m.get("timestamp"),
            }
            for m in msgs
        ]


# ------------------------------- tools ----------------------------------

async def _dc_me() -> dict:
    c = DiscordClient()
    try:
        return await c.me()
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


async def _dc_send(content: str, channel_id: str | None = None) -> dict:
    s = get_settings()
    ch = channel_id or s.discord_default_channel_id
    if not ch:
        raise ToolError(
            "channel_id is missing. Pass channel_id or set "
            "DISCORD_DEFAULT_CHANNEL_ID in .env."
        )
    c = DiscordClient()
    try:
        return await c.send_message(ch, content)
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


async def _dc_read(channel_id: str | None = None, limit: int = 20) -> list[dict]:
    s = get_settings()
    ch = channel_id or s.discord_default_channel_id
    if not ch:
        raise ToolError("channel_id or DISCORD_DEFAULT_CHANNEL_ID is required")
    c = DiscordClient()
    try:
        return await c.recent_messages(ch, limit=int(limit))
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


DISCORD_TOOLS = [
    Tool(
        name="discord.me",
        description="Get info about the Discord bot account.",
        parameters={"type": "object", "properties": {}},
        fn=_dc_me,
        category="discord",
        tags=["messaging", "read-only"],
    ),
    Tool(
        name="discord.send_message",
        description=(
            "Send a message to a Discord channel. If channel_id is omitted "
            "the default channel from settings is used."
        ),
        parameters={
            "type": "object",
            "required": ["content"],
            "properties": {
                "content": {"type": "string"},
                "channel_id": {"type": "string"},
            },
        },
        fn=_dc_send,
        category="discord",
        tags=["messaging", "write"],
    ),
    Tool(
        name="discord.read",
        description="Read the last N messages of a Discord channel.",
        parameters={
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
        fn=_dc_read,
        category="discord",
        tags=["messaging", "read-only"],
    ),
]
