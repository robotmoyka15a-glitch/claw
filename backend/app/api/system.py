from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.ws_manager import ws_manager
from app.services import processes, system

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/snapshot")
async def snapshot():
    return system.snapshot()


@router.get("/processes")
async def list_processes(sort_by: str = "cpu", limit: int = 200):
    return processes.list_processes(sort_by=sort_by, limit=limit)


@router.get("/processes/{pid}")
async def process_detail(pid: int):
    return processes.process_detail(pid)


@router.post("/processes/{pid}/kill")
async def kill_process(pid: int, force: bool = False):
    return processes.kill_process(pid, force=force)


# -------- WebSocket channels --------

ws_router = APIRouter()


@ws_router.websocket("/ws/system")
async def ws_system(ws: WebSocket):
    await ws_manager.connect("system", ws)
    try:
        while True:
            await ws.send_json(system.snapshot())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect("system", ws)


@ws_router.websocket("/ws/processes")
async def ws_processes(ws: WebSocket):
    await ws_manager.connect("processes", ws)
    try:
        while True:
            await ws.send_json({"rows": processes.list_processes(limit=100)})
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect("processes", ws)
