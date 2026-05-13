"""Webhook endpoints.

POST /webhook/telegram  — receives updates pushed by Telegram servers.
                          Protected by a secret token in the URL if
                          TELEGRAM_WEBHOOK_SECRET is configured.

POST /webhook/test      — dev helper: inject a fake tg_message event.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.connectors.telegram_poller import ingest_webhook_update
from app.core.config import get_settings

logger = logging.getLogger("claw.webhook")
router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/telegram")
async def telegram_webhook(request: Request) -> dict:
    """Receive a Telegram update pushed via webhook.

    Optionally validates X-Telegram-Bot-Api-Secret-Token header if
    TELEGRAM_WEBHOOK_SECRET is set in .env.
    """
    s = get_settings()
    secret = getattr(s, "telegram_webhook_secret", "")
    if secret:
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if header_secret != secret:
            raise HTTPException(status_code=403, detail="invalid webhook secret")

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")

    await ingest_webhook_update(body)
    return {"ok": True}


@router.post("/test")
async def test_webhook(request: Request) -> dict:
    """Dev-only: inject a fake Telegram message to test event routing."""
    body = await request.json()
    from app.agents.autonomy import publish  # noqa: PLC0415
    await publish("tg_message", {
        "chat_id": body.get("chat_id", "test"),
        "from": body.get("from", "dev"),
        "text": body.get("text", "test"),
        "update_id": -1,
    })
    return {"ok": True}
