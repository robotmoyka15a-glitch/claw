"""Telegram connector — plain HTTP calls to api.telegram.org (Bot API).

Claw does not run a long-poll loop; instead we just fetch updates on demand
(``get_updates``). That keeps things simple and avoids clashing with any
other bot infrastructure the user may have.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.tools.base import Tool, ToolError

from .base import ConnectorError, require


class TelegramClient:
    BASE = "https://api.telegram.org"

    def __init__(self, token: str | None = None) -> None:
        s = get_settings()
        self._token = token or s.telegram_bot_token
        self._http = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._http.aclose()

    @property
    def token(self) -> str:
        return require(self._token, "TELEGRAM_BOT_TOKEN")

    async def _call(self, method: str, **params: Any) -> Any:
        url = f"{self.BASE}/bot{self.token}/{method}"
        r = await self._http.post(url, json=params)
        data = r.json()
        if not data.get("ok"):
            raise ConnectorError(
                f"telegram {method} failed: {data.get('description', r.text)}"
            )
        return data.get("result")

    async def me(self) -> dict:
        return await self._call("getMe")

    async def send_message(self, chat_id: str | int, text: str) -> dict:
        return await self._call("sendMessage", chat_id=chat_id, text=text)

    async def get_updates(self, limit: int = 20, offset: int | None = None) -> list[dict]:
        params: dict[str, Any] = {"limit": limit, "timeout": 0}
        if offset is not None:
            params["offset"] = offset
        return await self._call("getUpdates", **params)


# ------------------------------- tools ----------------------------------

async def _tg_me() -> dict:
    c = TelegramClient()
    try:
        return await c.me()
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


async def _tg_send(text: str, chat_id: str | None = None) -> dict:
    s = get_settings()
    chat = chat_id or s.telegram_default_chat_id
    if not chat:
        raise ToolError(
            "chat_id is missing. Pass chat_id or set TELEGRAM_DEFAULT_CHAT_ID in .env."
        )
    c = TelegramClient()
    try:
        return await c.send_message(chat, text)
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


async def _tg_updates(limit: int = 20) -> list[dict]:
    c = TelegramClient()
    try:
        return await c.get_updates(limit=limit)
    except ConnectorError as e:
        raise ToolError(str(e)) from e
    finally:
        await c.close()


TELEGRAM_TOOLS = [
    Tool(
        name="telegram.me",
        description="Return info about the Telegram bot (name, username, id).",
        parameters={"type": "object", "properties": {}},
        fn=_tg_me,
        category="telegram",
        tags=["messaging", "read-only"],
    ),
    Tool(
        name="telegram.send_message",
        description=(
            "Send a text message via the configured Telegram bot. If chat_id "
            "is omitted the default chat from settings is used."
        ),
        parameters={
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {"type": "string"},
                "chat_id": {"type": "string"},
            },
        },
        fn=_tg_send,
        category="telegram",
        tags=["messaging", "write"],
    ),
    Tool(
        name="telegram.get_updates",
        description="Fetch recent updates (messages) received by the bot.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
        },
        fn=_tg_updates,
        category="telegram",
        tags=["messaging", "read-only"],
    ),
]
