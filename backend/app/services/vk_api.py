"""Thin async VK API client. Reads user access token from settings."""
from __future__ import annotations

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

    # --- high-level helpers ---
    async def me(self) -> dict:
        res = await self.call(
            "users.get",
            fields="photo_200,status,last_seen,online,city,counters",
        )
        return res[0] if res else {}

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

    async def newsfeed(self, count: int = 25) -> dict:
        return await self.call("newsfeed.get", filters="post", count=count)

    async def notifications(self, count: int = 20) -> dict:
        return await self.call("notifications.get", count=count)
