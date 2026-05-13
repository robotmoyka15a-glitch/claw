"""Windows native toast notifications.

Uses the `winrt.windows.ui.notifications` bindings on Windows; on other
platforms the tool falls back to a warning (the UI still works from the
browser's own Notification API, which is why we also expose a "queue" the
frontend can poll).
"""
from __future__ import annotations

import asyncio
import sys
import time
from collections import deque
from typing import Deque

from app.tools.base import Tool, ToolError


_MAX_QUEUE = 50
_queue: Deque[dict] = deque(maxlen=_MAX_QUEUE)


def pending_notifications() -> list[dict]:
    """Consume and return queued notifications (used by the /api/notifications
    endpoint for the frontend to show toast bubbles in the dashboard).
    """
    out = list(_queue)
    _queue.clear()
    return out


async def _native_windows_toast(title: str, message: str) -> bool:
    """Fire a real Windows toast via winrt. Returns True on success."""
    if sys.platform != "win32":
        return False
    try:
        # Runs in a worker thread because winrt APIs are sync.
        def _fire() -> None:
            from winrt.windows.ui.notifications import (  # type: ignore[import-not-found]
                ToastNotificationManager,
                ToastNotification,
            )
            from winrt.windows.data.xml.dom import XmlDocument  # type: ignore[import-not-found]

            template = (
                "<toast><visual><binding template='ToastGeneric'>"
                f"<text>{_xml_escape(title)}</text>"
                f"<text>{_xml_escape(message)}</text>"
                "</binding></visual></toast>"
            )
            xml = XmlDocument()
            xml.load_xml(template)
            notifier = ToastNotificationManager.create_toast_notifier("claw")
            notifier.show(ToastNotification(xml))

        await asyncio.to_thread(_fire)
        return True
    except Exception:  # noqa: BLE001
        return False


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


async def _notify(title: str, message: str, level: str = "info") -> dict:
    if not title and not message:
        raise ToolError("title or message must be non-empty")
    entry = {
        "ts": time.time(),
        "title": title or "claw",
        "message": message or "",
        "level": level,
    }
    _queue.append(entry)
    fired = await _native_windows_toast(entry["title"], entry["message"])
    return {"ok": True, "native_toast": fired, "queued": True}


NOTIFY_TOOLS = [
    Tool(
        name="notify.toast",
        description=(
            "Show a desktop notification on the user's PC. Fires a native "
            "Windows toast when available, and also appears as a bubble in "
            "the claw dashboard."
        ),
        parameters={
            "type": "object",
            "required": ["title", "message"],
            "properties": {
                "title": {"type": "string"},
                "message": {"type": "string"},
                "level": {"type": "string", "enum": ["info", "warn", "error"]},
            },
        },
        fn=_notify,
        category="notifications",
        tags=["desktop", "write"],
    ),
]
