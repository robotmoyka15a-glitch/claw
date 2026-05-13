"""REST + WebSocket API for autonomous agent tasks.

Endpoints:
  GET    /api/autonomy/tasks                — list all tasks
  POST   /api/autonomy/tasks                — create task
  GET    /api/autonomy/tasks/{id}           — get task
  PATCH  /api/autonomy/tasks/{id}           — update task
  DELETE /api/autonomy/tasks/{id}           — delete task
  POST   /api/autonomy/tasks/{id}/run       — trigger task immediately
  GET    /api/autonomy/tasks/{id}/runs      — last N execution logs
  GET    /api/autonomy/events               — recent event log (in-memory)
  WS     /ws/events                        — live event stream
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.autonomy import publish, run_autonomous_task
from app.core.db import SessionLocal
from app.core.ws_manager import ws_manager
from app.agents.models import ScheduledTask, TaskRun

router = APIRouter(prefix="/api/autonomy", tags=["autonomy"])
ws_router = APIRouter()

# ── in-memory event ring buffer (last 200 events) ─────────────────────────────
_event_log: deque[dict] = deque(maxlen=200)


def _log_event(ev: dict) -> None:
    _event_log.appendleft(ev)


# Subscribe to all events for logging
from app.agents.autonomy import subscribe  # noqa: E402

subscribe("*", lambda ev: _log_event(ev) or __import__("asyncio").sleep(0))  # type: ignore[arg-type]


# ── helpers ───────────────────────────────────────────────────────────────────

def _serialize_task(t: ScheduledTask) -> dict:
    return {
        "id": t.id,
        "agent_id": t.agent_id,
        "name": t.name,
        "objective": t.objective,
        "trigger_type": t.trigger_type,
        "trigger_value": t.trigger_value,
        "enabled": t.enabled,
        "max_iterations": t.max_iterations,
        "created_at": t.created_at,
        "last_run_at": t.last_run_at,
    }


def _serialize_run(r: TaskRun) -> dict:
    return {
        "id": r.id,
        "task_id": r.task_id,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
        "trigger": r.trigger,
        "status": r.status,
        "summary": r.summary,
        "error": r.error,
    }


# ── schemas ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    agent_id: str
    name: str
    objective: str
    trigger_type: str = "manual"     # manual|interval|cron|event
    trigger_value: str = ""
    enabled: bool = True
    max_iterations: int = 6


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    objective: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_value: Optional[str] = None
    enabled: Optional[bool] = None
    max_iterations: Optional[int] = None


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(agent_id: Optional[str] = None):
    async with SessionLocal() as db:
        q = select(ScheduledTask)
        if agent_id:
            q = q.where(ScheduledTask.agent_id == agent_id)
        q = q.order_by(ScheduledTask.created_at.desc())
        tasks = (await db.execute(q)).scalars().all()
    return [_serialize_task(t) for t in tasks]


@router.post("/tasks")
async def create_task(body: TaskCreate):
    async with SessionLocal() as db:
        t = ScheduledTask(
            id=uuid.uuid4().hex,
            agent_id=body.agent_id,
            name=body.name,
            objective=body.objective,
            trigger_type=body.trigger_type,
            trigger_value=body.trigger_value,
            enabled=body.enabled,
            max_iterations=body.max_iterations,
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)
    return _serialize_task(t)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    async with SessionLocal() as db:
        t = await db.get(ScheduledTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    return _serialize_task(t)


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, patch: TaskUpdate):
    async with SessionLocal() as db:
        t = await db.get(ScheduledTask, task_id)
        if not t:
            raise HTTPException(404, "task not found")
        for field in ("name", "objective", "trigger_type", "trigger_value", "enabled", "max_iterations"):
            v = getattr(patch, field)
            if v is not None:
                setattr(t, field, v)
        await db.commit()
        await db.refresh(t)
    return _serialize_task(t)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    async with SessionLocal() as db:
        t = await db.get(ScheduledTask, task_id)
        if not t:
            raise HTTPException(404, "task not found")
        await db.delete(t)
        await db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/run")
async def run_task_now(task_id: str):
    """Trigger a task immediately (regardless of schedule)."""
    async with SessionLocal() as db:
        t = await db.get(ScheduledTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    import asyncio  # noqa: PLC0415
    asyncio.create_task(
        run_autonomous_task(
            t.agent_id,
            t.objective,
            task_id=t.id,
            trigger="manual",
            max_iterations=t.max_iterations,
        )
    )
    return {"ok": True, "task_id": task_id, "status": "launched"}


@router.get("/tasks/{task_id}/runs")
async def task_runs(task_id: str, limit: int = 20):
    async with SessionLocal() as db:
        q = (
            select(TaskRun)
            .where(TaskRun.task_id == task_id)
            .order_by(TaskRun.started_at.desc())
            .limit(limit)
        )
        runs = (await db.execute(q)).scalars().all()
    return [_serialize_run(r) for r in runs]


@router.get("/events")
async def recent_events(limit: int = 50):
    return list(_event_log)[:limit]


# ── event WebSocket ───────────────────────────────────────────────────────────

@ws_router.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    """Live event stream for the frontend event log panel."""
    await ws_manager.connect("events", ws)
    try:
        # Send recent history so the panel populates immediately
        await ws.send_json({"type": "history", "events": list(_event_log)[:50]})
        while True:
            # Keep alive; events are pushed via ws_manager.broadcast("events", ...)
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect("events", ws)
