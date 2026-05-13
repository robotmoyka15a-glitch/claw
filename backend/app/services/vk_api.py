"""Thin async VK API client. Reads user access token from settings."""
from __future__ import annotations

import random
from typing import Any

import httpx

from app.core.config import get_settings


class VKError(Exception):
    pass


class VKClient:
    BASE = "https://api.vk.com/method"

    def __init__(self, token: str | None = None, version: str | None = None) -> None:
        s = get_settings()
        self.token = token or s.vk_access_token
        self.version = version or s.vk_api_version
        self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def call(self, method: str, **params: Any) -> Any:
        if not self.token:
            raise VKError("VK access token is not configured")
        payload = {"access_token": self.token, "v": self.version, **params}
        r = await self._client.post(f"{self.BASE}/{method}", data=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            err = data["error"]
            raise VKError(f"{err.get('error_code')}: {err.get('error_msg')}")
        return data.get("response")

    # ── profile ──────────────────────────────────────────────────────────────

    async def me(self) -> dict:
        res = await self.call(
            "users.get",
            fields="photo_200,status,last_seen,online,city,counters",
        )
        return res[0] if res else {}

    # ── friends ───────────────────────────────────────────────────────────────

    async def friends_online(self) -> dict:
        ids = await self.call("friends.getOnline")
        if not ids:
            return {"count": 0, "items": []}
        users = await self.call(
            "users.get",
            user_ids=",".join(str(i) for i in ids[:100]),
            fields="photo_100,online,status",
        )
        return {"count": len(ids), "items": users}

    async def friends_list(self, count: int = 50) -> dict:
        """Return the full friends list (not just online), sorted by name."""
        return await self.call(
            "friends.get",
            fields="photo_100,online,status,last_seen",
            order="name",
            count=count,
        )

    # ── newsfeed ──────────────────────────────────────────────────────────────

    async def newsfeed(self, count: int = 25) -> dict:
        return await self.call("newsfeed.get", filters="post", count=count)

    async def newsfeed_search(self, query: str, count: int = 20) -> dict:
        """Search public posts in the newsfeed by keyword."""
        return await self.call(
            "newsfeed.search",
            q=query,
            count=count,
            extended=1,
        )

    # ── notifications ─────────────────────────────────────────────────────────

    async def notifications(self, count: int = 20) -> dict:
        return await self.call("notifications.get", count=count)

    # ── messages (requires messages scope in the token) ───────────────────────

    async def send_message(self, user_id: int, message: str) -> int:
        """Send a message to a VK user. Returns message_id.

        Note: the access token must have been issued with scope=messages.
        """
        random_id = random.randint(1, 2 ** 31 - 1)
        return await self.call(
            "messages.send",
            user_id=user_id,
            message=message,
            random_id=random_id,
        )

    async def get_dialogs(self, count: int = 20) -> dict:
        """Return the most recent conversations."""
        return await self.call(
            "messages.getConversations",
            count=count,
            extended=1,
            fields="photo_100,online",
        )

    async def get_history(self, peer_id: int, count: int = 20) -> dict:
        """Return message history for a conversation."""
        return await self.call(
            "messages.getHistory",
            peer_id=peer_id,
            count=count,
        )

    # ── likes ─────────────────────────────────────────────────────────────────

    async def like(self, owner_id: int, item_id: int, item_type: str = "post") -> dict:
        """Add a like to a post/photo/video. Returns {"likes": N}."""
        return await self.call(
            "likes.add",
            type=item_type,
            owner_id=owner_id,
            item_id=item_id,
        )

    async def unlike(self, owner_id: int, item_id: int, item_type: str = "post") -> dict:
        """Remove a like. Returns {"likes": N}."""
        return await self.call(
            "likes.delete",
            type=item_type,
            owner_id=owner_id,
            item_id=item_id,
        )

    # ── wall ──────────────────────────────────────────────────────────────────

    async def wall_post(self, message: str, owner_id: int | None = None) -> dict:
        """Post to own wall (or another wall if owner_id is set)."""
        kwargs: dict[str, Any] = {"message": message}
        if owner_id:
            kwargs["owner_id"] = owner_id
        return await self.call("wall.post", **kwargs)

    async def wall_get(self, owner_id: int | None = None, count: int = 20) -> dict:
        """Get wall posts for a user (defaults to own wall)."""
        kwargs: dict[str, Any] = {"count": count, "extended": 1, "fields": "photo_100"}
        if owner_id:
            kwargs["owner_id"] = owner_id
        return await self.call("wall.get", **kwargs)

    # ── groups / communities ──────────────────────────────────────────────────

    async def groups_get(self, count: int = 50) -> dict:
        """Return the user's communities."""
        return await self.call(
            "groups.get",
            extended=1,
            fields="description,members_count,photo_100",
            count=count,
        )
