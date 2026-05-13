"""VK REST API endpoints — exposed at /api/vk/*"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.vk_api import VKClient, VKError

router = APIRouter(prefix="/api/vk", tags=["vk"])


def _vk_err(e: VKError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


# ── profile ───────────────────────────────────────────────────────────────────

@router.get("/me")
async def me():
    async with _ctx() as c:
        return await c.me()


@router.get("/friends/online")
async def friends_online():
    async with _ctx() as c:
        return await c.friends_online()


@router.get("/friends")
async def friends(count: int = 50):
    async with _ctx() as c:
        return await c.friends_list(count=count)


@router.get("/newsfeed")
async def newsfeed(count: int = 25):
    async with _ctx() as c:
        return await c.newsfeed(count=count)


@router.get("/newsfeed/search")
async def newsfeed_search(q: str, count: int = 20):
    """Search public posts by keyword."""
    async with _ctx() as c:
        return await c.newsfeed_search(query=q, count=count)


@router.get("/notifications")
async def notifications(count: int = 20):
    async with _ctx() as c:
        return await c.notifications(count=count)


# ── messages ─────────────────────────────────────────────────────────────────

class MessageSend(BaseModel):
    user_id: int
    message: str


@router.post("/messages/send")
async def messages_send(body: MessageSend):
    """Send a message to a VK user (requires 'messages' scope in token)."""
    async with _ctx() as c:
        msg_id = await c.send_message(body.user_id, body.message)
        return {"ok": True, "message_id": msg_id}


@router.get("/messages/dialogs")
async def messages_dialogs(count: int = 20):
    async with _ctx() as c:
        return await c.get_dialogs(count=count)


@router.get("/messages/history/{peer_id}")
async def messages_history(peer_id: int, count: int = 20):
    async with _ctx() as c:
        return await c.get_history(peer_id=peer_id, count=count)


# ── likes ─────────────────────────────────────────────────────────────────────

class LikeBody(BaseModel):
    owner_id: int
    item_id: int
    item_type: str = "post"


@router.post("/likes/add")
async def like_add(body: LikeBody):
    async with _ctx() as c:
        return await c.like(body.owner_id, body.item_id, body.item_type)


@router.post("/likes/delete")
async def like_delete(body: LikeBody):
    async with _ctx() as c:
        return await c.unlike(body.owner_id, body.item_id, body.item_type)


# ── wall ──────────────────────────────────────────────────────────────────────

class WallPost(BaseModel):
    message: str
    owner_id: Optional[int] = None


@router.post("/wall/post")
async def wall_post(body: WallPost):
    async with _ctx() as c:
        return await c.wall_post(body.message, body.owner_id)


@router.get("/wall")
async def wall_get(owner_id: Optional[int] = None, count: int = 20):
    async with _ctx() as c:
        return await c.wall_get(owner_id=owner_id, count=count)


# ── groups ────────────────────────────────────────────────────────────────────

@router.get("/groups")
async def groups(count: int = 50):
    async with _ctx() as c:
        return await c.groups_get(count=count)


# ── context manager helper ────────────────────────────────────────────────────

from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _ctx():
    client = VKClient()
    try:
        yield client
    except VKError as e:
        raise _vk_err(e)
    finally:
        await client.close()
