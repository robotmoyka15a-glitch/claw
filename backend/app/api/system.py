"""System REST + WebSocket endpoints.

Optimisations vs the original:
  * /ws/processes now sends a compact delta (added/removed/changed/top) every
    1.5 s instead of the full list every 2 s.  The frontend merges deltas.
  * /ws/system cadence unchanged at 1 s (it's already one small dict).
  * A global asyncio.Semaphore limits concurrent LLM calls so Ollama / the
    local GPU is not overloaded when several agents are active at the same time.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.ws_manager import ws_manager
from app.services import processes, system

router = APIRouter(prefix="/api/system", tags=["system"])

# ── concurrency limiter ────────────────────────────────────────────────────────
# Shared semaphore used by app.agents.manager when launching LLM calls.
# Prevents simultaneous VRAM overcommit on a single-GPU machine.
LLM_SEMAPHORE: asyncio.Semaphore | None = None


def get_llm_semaphore(max_concurrent: int = 3) -> asyncio.Semaphore:
    """Return (creating if needed) the process-wide LLM concurrency gate."""
    global LLM_SEMAPHORE
    if LLM_SEMAPHORE is None:
        LLM_SEMAPHORE = asyncio.Semaphore(max_concurrent)
    return LLM_SEMAPHORE


# ── REST ───────────────────────────────────────────────────────────────────────

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


# ── WebSocket ─────────────────────────────────────────────────────────────────

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
    """Send compact diff packets instead of full list.

    Packet shape:
        { "added": [...], "removed": [pid, ...], "changed": [...], "top": [...] }

    The frontend applies the diff to its local cache and re-renders only the
    changed rows.
    """
    await ws_manager.connect("processes", ws)
    # Send full list on connect so the client has a baseline.
    try:
        await ws.send_json({"type": "full", "rows": processes.list_processes(limit=150)})
        while True:
            await asyncio.sleep(1.5)
            delta = processes.diff_processes(limit=150)
            # Only send if something actually changed.
            if delta["added"] or delta["removed"] or delta["changed"]:
                await ws.send_json({"type": "delta", **delta})
            else:
                # Heartbeat with top list every ~10 s to keep the table fresh.
                await ws.send_json({"type": "heartbeat", "top": delta["top"]})
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect("processes", ws)
