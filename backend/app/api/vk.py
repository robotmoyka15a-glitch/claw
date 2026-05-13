from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.vk_api import VKClient, VKError

router = APIRouter(prefix="/api/vk", tags=["vk"])


@router.get("/me")
async def me():
    client = VKClient()
    try:
        return await client.me()
    except VKError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.close()


@router.get("/friends/online")
async def friends_online():
    client = VKClient()
    try:
        return await client.friends_online()
    except VKError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.close()


@router.get("/newsfeed")
async def newsfeed(count: int = 25):
    client = VKClient()
    try:
        return await client.newsfeed(count=count)
    except VKError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.close()


@router.get("/notifications")
async def notifications(count: int = 20):
    client = VKClient()
    try:
        return await client.notifications(count=count)
    except VKError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.close()
