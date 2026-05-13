"""REST endpoints for third-party connectors.

The dashboard uses these for dedicated panels (Telegram inbox, Steam library,
Spotify now-playing, ...). Agents don't usually call these — they go through
the Tool layer instead — but the endpoints are handy for humans and for
scripting from curl.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.connectors.base import ConnectorError
from app.connectors.discord import DiscordClient
from app.connectors.spotify import SpotifyClient
from app.connectors.steam import SteamClient
from app.connectors.telegram import TelegramClient
from app.connectors.windows_notify import _notify, pending_notifications
from app.core.config import get_settings


router = APIRouter(prefix="/api/connectors", tags=["connectors"])


def _err(e: ConnectorError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


# --------- status ----------

@router.get("/status")
async def connector_status() -> list[dict[str, Any]]:
    """Which connectors have credentials configured. UI uses this to decide
    whether to show a panel.
    """
    s = get_settings()
    return [
        {"key": "telegram", "configured": bool(s.telegram_bot_token)},
        {"key": "discord", "configured": bool(s.discord_bot_token)},
        {"key": "steam", "configured": bool(s.steam_api_key and s.steam_user_id)},
        {
            "key": "spotify",
            "configured": bool(
                s.spotify_client_id and s.spotify_client_secret and s.spotify_refresh_token
            ),
        },
        {"key": "vk", "configured": bool(s.vk_access_token)},
    ]


# --------- Telegram ----------

class TelegramSend(BaseModel):
    text: str
    chat_id: Optional[str] = None


@router.get("/telegram/me")
async def tg_me():
    c = TelegramClient()
    try:
        return await c.me()
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


@router.get("/telegram/updates")
async def tg_updates(limit: int = 20):
    c = TelegramClient()
    try:
        return await c.get_updates(limit=limit)
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


@router.post("/telegram/send")
async def tg_send(body: TelegramSend):
    s = get_settings()
    chat = body.chat_id or s.telegram_default_chat_id
    if not chat:
        raise HTTPException(400, "chat_id is missing")
    c = TelegramClient()
    try:
        return await c.send_message(chat, body.text)
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


# --------- Discord ----------

class DiscordSend(BaseModel):
    content: str
    channel_id: Optional[str] = None


@router.get("/discord/me")
async def dc_me():
    c = DiscordClient()
    try:
        return await c.me()
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


@router.get("/discord/messages")
async def dc_messages(channel_id: Optional[str] = None, limit: int = 20):
    s = get_settings()
    ch = channel_id or s.discord_default_channel_id
    if not ch:
        raise HTTPException(400, "channel_id is missing")
    c = DiscordClient()
    try:
        return await c.recent_messages(ch, limit=limit)
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


@router.post("/discord/send")
async def dc_send(body: DiscordSend):
    s = get_settings()
    ch = body.channel_id or s.discord_default_channel_id
    if not ch:
        raise HTTPException(400, "channel_id is missing")
    c = DiscordClient()
    try:
        return await c.send_message(ch, body.content)
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


# --------- Steam ----------

@router.get("/steam/summary")
async def steam_summary():
    c = SteamClient()
    try:
        return await c.summary()
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


@router.get("/steam/recent")
async def steam_recent(count: int = 5):
    c = SteamClient()
    try:
        return await c.recently_played(count=count)
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


@router.get("/steam/owned")
async def steam_owned(limit: int = 50):
    c = SteamClient()
    try:
        return await c.owned(limit=limit)
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


# --------- Spotify ----------

@router.get("/spotify/now")
async def spotify_now():
    c = SpotifyClient()
    try:
        return await c.now_playing()
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


class SpotifyAction(BaseModel):
    action: str


@router.post("/spotify/control")
async def spotify_control(body: SpotifyAction):
    c = SpotifyClient()
    try:
        if body.action == "pause":
            await c.pause()
        elif body.action == "resume":
            await c.resume()
        elif body.action == "next":
            await c.next()
        else:
            raise HTTPException(400, f"unknown action: {body.action}")
        return {"ok": True}
    except ConnectorError as e:
        raise _err(e)
    finally:
        await c.close()


# --------- Notifications ----------

class NotifyBody(BaseModel):
    title: str
    message: str
    level: str = "info"


@router.post("/notify")
async def send_notification(body: NotifyBody):
    return await _notify(body.title, body.message, body.level)


@router.get("/notify/pending")
async def fetch_notifications():
    """Queued notifications the frontend should surface as toast bubbles."""
    return pending_notifications()
