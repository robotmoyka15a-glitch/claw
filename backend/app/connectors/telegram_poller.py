"""Telegram long-poll loop + optional webhook endpoint.

Two modes (auto-detected):
  1. Long-poll (default) — claw polls api.telegram.org/getUpdates
     with timeout=30 in a background coroutine.  Zero config beyond
     TELEGRAM_BOT_TOKEN.

  2. Webhook — if TELEGRAM_WEBHOOK_URL is set, claw registers the URL
     with Telegram on startup.  The FastAPI route POST /webhook/telegram
     receives updates pushed by Telegram's servers.  Requires the URL
     to be publicly reachable (ngrok, cloudflare tunnel, VPS, etc.).

When an update arrives (either way), we:
  a) Store it in memory (ring buffer, max 500) for the REST endpoint.
  b) Publish  "tg_message"  on the EventBus so autonomous tasks can react.
  c) Route the message to any agent whose Telegram watch list includes
     the chat_id (future: configurable per-task).
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

from app.core.config import get_settings
from app.core.http_pool import get_client

logger = logging.getLogger("claw.telegram_poller")

_updates: deque[dict] = deque(maxlen=500)
_offset: int = 0
_running = False
_poll_task: asyncio.Task | None = None


# ── message processing ────────────────────────────────────────────────────────

async def _handle_update(update: dict) -> None:
    """Called for every incoming Telegram update."""
    _updates.appendleft(update)

    msg = (
        update.get("message")
        or update.get("channel_post")
        or update.get("edited_message")
    )
    if not msg:
        return

    chat_id = str((msg.get("chat") or {}).get("id", ""))
    text = msg.get("text") or msg.get("caption") or ""
    from_user = msg.get("from") or {}
    sender = from_user.get("username") or from_user.get("first_name") or "unknown"

    if not text:
        return

    # Publish to event bus
    from app.agents.autonomy import publish  # noqa: PLC0415
    await publish("tg_message", {
        "chat_id": chat_id,
        "from": sender,
        "text": text,
        "update_id": update.get("update_id"),
    })


# ── long-poll loop ────────────────────────────────────────────────────────────

async def _long_poll_loop() -> None:
    global _offset, _running
    s = get_settings()
    if not s.telegram_bot_token:
        logger.info("TELEGRAM_BOT_TOKEN not set — long-poll disabled")
        return

    base = f"https://api.telegram.org/bot{s.telegram_bot_token}"
    logger.info("Telegram long-poll started")

    while _running:
        try:
            c = await get_client()
            r = await c.post(
                f"{base}/getUpdates",
                json={"offset": _offset, "timeout": 30, "limit": 100},
                timeout=40.0,
            )
            if r.status_code != 200:
                await asyncio.sleep(5)
                continue
            data = r.json()
            if not data.get("ok"):
                await asyncio.sleep(5)
                continue
            for upd in data.get("result") or []:
                _offset = upd["update_id"] + 1
                asyncio.create_task(_handle_update(upd))
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            logger.warning("Telegram poll error: %s", e)
            await asyncio.sleep(5)


# ── webhook registration ──────────────────────────────────────────────────────

async def _register_webhook(url: str) -> None:
    s = get_settings()
    if not s.telegram_bot_token:
        return
    base = f"https://api.telegram.org/bot{s.telegram_bot_token}"
    c = await get_client()
    r = await c.post(f"{base}/setWebhook", json={"url": url})
    if r.status_code == 200 and r.json().get("ok"):
        logger.info("Telegram webhook registered: %s", url)
    else:
        logger.warning("Telegram webhook registration failed: %s", r.text)


async def _delete_webhook() -> None:
    s = get_settings()
    if not s.telegram_bot_token:
        return
    c = await get_client()
    await c.post(f"https://api.telegram.org/bot{s.telegram_bot_token}/deleteWebhook")
    logger.info("Telegram webhook deleted (falling back to long-poll)")


# ── public lifecycle ──────────────────────────────────────────────────────────

async def start() -> None:
    global _running, _poll_task
    if _running:
        return
    _running = True
    s = get_settings()

    webhook_url = getattr(s, "telegram_webhook_url", "")
    if webhook_url:
        await _register_webhook(webhook_url)
        logger.info("Running in webhook mode — no long-poll started")
    else:
        _poll_task = asyncio.create_task(_long_poll_loop())


async def stop() -> None:
    global _running, _poll_task
    _running = False
    if _poll_task and not _poll_task.done():
        _poll_task.cancel()


def recent_updates(limit: int = 50) -> list[dict]:
    return list(_updates)[:limit]


# ── webhook ingest (called by the FastAPI route) ──────────────────────────────

async def ingest_webhook_update(update: dict) -> None:
    """Called by POST /webhook/telegram with the parsed JSON body."""
    await _handle_update(update)
