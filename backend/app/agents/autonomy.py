"""Autonomous agent runtime.

Architecture:

  EventBus       — in-process pub/sub for system events
  AgentLoop      — Plan-and-Execute loop for one agent turn
  Scheduler      — background task that fires ScheduledTasks on time / on event

──────────────────────────────────────────────────────────────────────────────
Event types (published to EventBus)
──────────────────────────────────────────────────────────────────────────────
  cpu_high          {"cpu": 92.1}
  mem_high          {"ram": 87.0}
  process_new       {"pid": 1234, "name": "chrome.exe"}
  process_died      {"pid": 5678, "name": "python.exe"}
  vk_message        {"from_id": ..., "text": "...", "chat_id": ...}
  tg_message        {"chat_id": ..., "from": "...", "text": "..."}
  spotify_track     {"title": "...", "artists": "..."}
  agent_finished    {"agent_id": "...", "task_id": "...", "summary": "..."}

──────────────────────────────────────────────────────────────────────────────
Plan-and-Execute loop
──────────────────────────────────────────────────────────────────────────────
1. The agent is given an objective as a user message.
2. LLM produces a plan as a numbered list (or just acts directly).
3. The existing stream_events() function handles tool calling automatically.
4. After MAX_ITERATIONS the loop stops regardless of plan completion.
5. A summary is extracted from the final assistant message.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from typing import Any, Callable, Coroutine

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.ws_manager import ws_manager

from .models import ScheduledTask, TaskRun

logger = logging.getLogger("claw.autonomy")

# ── 1. Event Bus ──────────────────────────────────────────────────────────────

_subscribers: dict[str, list[Callable[[dict], Coroutine[Any, Any, None]]]] = defaultdict(list)


def subscribe(event_type: str, handler: Callable[[dict], Coroutine[Any, Any, None]]) -> None:
    """Register an async handler for `event_type` (or '*' for all events)."""
    _subscribers[event_type].append(handler)


async def publish(event_type: str, payload: dict) -> None:
    """Publish an event; all registered handlers are called concurrently."""
    handlers = _subscribers.get(event_type, []) + _subscribers.get("*", [])
    if handlers:
        await asyncio.gather(*[h({**payload, "event": event_type}) for h in handlers], return_exceptions=True)
    # Forward to WebSocket so the frontend can show event log
    await ws_manager.broadcast("events", {"event": event_type, "ts": time.time(), **payload})


# ── 2. System monitor — publishes cpu_high / mem_high / process events ────────

_prev_pids: set[int] = set()


async def _monitor_system() -> None:
    """Run every 5 s and publish events when thresholds are crossed."""
    import psutil
    from app.services import system as sys_svc

    while True:
        try:
            snap = sys_svc.snapshot()
            if snap["cpu_percent"] > 85:
                await publish("cpu_high", {"cpu": snap["cpu_percent"]})
            if snap["ram_percent"] > 85:
                await publish("mem_high", {"ram": snap["ram_percent"]})

            # Process diff
            cur = {p.pid: p.name() for p in psutil.process_iter(["pid", "name"], ad_value="")}
            new_pids = set(cur) - _prev_pids
            dead_pids = _prev_pids - set(cur)
            for pid in new_pids:
                await publish("process_new", {"pid": pid, "name": cur[pid]})
            for pid in dead_pids:
                await publish("process_died", {"pid": pid, "name": ""})
            _prev_pids.clear()
            _prev_pids.update(cur)
        except Exception as e:  # noqa: BLE001
            logger.debug("monitor_system error: %s", e)
        await asyncio.sleep(5.0)


# ── 3. AgentLoop — Plan-and-Execute ──────────────────────────────────────────

async def run_autonomous_task(
    agent_id: str,
    objective: str,
    *,
    task_id: str | None = None,
    trigger: str = "scheduler",
    max_iterations: int = 6,
) -> str:
    """Run an autonomous task for agent_id and return a summary string.

    This wraps stream_events() with a task-run record and returns the
    last assistant message as a summary.
    """
    from app.agents.manager import stream_events  # noqa: PLC0415

    run_id: int | None = None
    started = time.time()

    # Create TaskRun record
    if task_id:
        async with SessionLocal() as db:
            run = TaskRun(
                task_id=task_id,
                trigger=trigger,
                status="running",
                started_at=started,
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            run_id = run.id

    # Notify frontend
    await ws_manager.broadcast("events", {
        "event": "task_started",
        "agent_id": agent_id,
        "task_id": task_id,
        "objective": objective[:120],
        "ts": started,
    })

    summary_parts: list[str] = []
    error_text = ""

    try:
        async for ev in stream_events(agent_id, objective):
            if ev.get("type") == "delta":
                summary_parts.append(ev.get("text", ""))
    except Exception as e:  # noqa: BLE001
        error_text = str(e)
        logger.warning("autonomous task %s error: %s", task_id, e)

    summary = "".join(summary_parts).strip()
    if not summary:
        summary = error_text or "(no output)"

    finished = time.time()

    # Update TaskRun
    if run_id and task_id:
        async with SessionLocal() as db:
            run = await db.get(TaskRun, run_id)
            if run:
                run.finished_at = finished
                run.status = "error" if error_text else "ok"
                run.summary = summary[:2000]
                run.error = error_text[:500]
                await db.commit()

        # Update last_run_at on the task itself
        async with SessionLocal() as db:
            task = await db.get(ScheduledTask, task_id)
            if task:
                task.last_run_at = finished
                await db.commit()

    await ws_manager.broadcast("events", {
        "event": "task_finished",
        "agent_id": agent_id,
        "task_id": task_id,
        "summary": summary[:200],
        "status": "error" if error_text else "ok",
        "ts": finished,
    })

    logger.info("autonomous task %s (%s) finished in %.1fs", task_id, trigger, finished - started)
    return summary


# ── 4. Scheduler ─────────────────────────────────────────────────────────────

_scheduler_task: asyncio.Task | None = None
_running = False


def _next_interval_ts(interval_secs: float, last_run: float) -> float:
    now = time.time()
    if last_run == 0:
        return now  # run immediately on first schedule
    return last_run + interval_secs


def _parse_cron_next(expr: str, after: float) -> float:
    """Minimal cron parser.  Supports '*/N' for minutes, hours and '@every Xs'.
    Falls back to hourly if unparseable.
    """
    expr = expr.strip()
    # @every <N>s / @every <N>m / @every <N>h shorthand
    if expr.startswith("@every"):
        parts = expr.split()
        if len(parts) == 2:
            s = parts[1]
            mult = {"s": 1, "m": 60, "h": 3600}.get(s[-1], 60)
            try:
                n = int(s[:-1]) * mult
                return after + n
            except ValueError:
                pass
    # Standard cron: '*/N * * * *'  (only minute interval supported for now)
    fields = expr.split()
    if len(fields) >= 1:
        minute_field = fields[0]
        if minute_field.startswith("*/"):
            try:
                every_n = int(minute_field[2:])
                interval = every_n * 60
                return after + interval
            except ValueError:
                pass
    # Fallback: every hour
    return after + 3600


async def _scheduler_loop() -> None:
    global _running
    _running = True
    logger.info("Autonomous scheduler started")

    # Subscribe to events so we can trigger event-based tasks
    subscribe("cpu_high",    _make_event_handler("cpu_high"))
    subscribe("mem_high",    _make_event_handler("mem_high"))
    subscribe("vk_message",  _make_event_handler("vk_message"))
    subscribe("tg_message",  _make_event_handler("tg_message"))
    subscribe("process_new", _make_event_handler("process_new"))

    while _running:
        try:
            await _tick_scheduler()
        except Exception as e:  # noqa: BLE001
            logger.warning("Scheduler tick error: %s", e)
        await asyncio.sleep(10.0)


def _make_event_handler(event_type: str):
    async def _handler(payload: dict) -> None:
        await _fire_event_tasks(event_type, payload)
    return _handler


async def _fire_event_tasks(event_type: str, payload: dict) -> None:
    """Find enabled tasks matching this event and run them."""
    async with SessionLocal() as db:
        q = (
            select(ScheduledTask)
            .where(ScheduledTask.trigger_type == "event")
            .where(ScheduledTask.trigger_value == event_type)
            .where(ScheduledTask.enabled.is_(True))
        )
        tasks = (await db.execute(q)).scalars().all()

    for task in tasks:
        context_line = f"\n\n[Context] Event '{event_type}': {payload}"
        asyncio.create_task(
            run_autonomous_task(
                task.agent_id,
                task.objective + context_line,
                task_id=task.id,
                trigger=f"event:{event_type}",
                max_iterations=task.max_iterations,
            )
        )


async def _tick_scheduler() -> None:
    """Check all interval/cron tasks and launch overdue ones."""
    now = time.time()
    async with SessionLocal() as db:
        q = (
            select(ScheduledTask)
            .where(ScheduledTask.enabled.is_(True))
            .where(ScheduledTask.trigger_type.in_(["interval", "cron"]))
        )
        tasks = (await db.execute(q)).scalars().all()

    for task in tasks:
        try:
            if task.trigger_type == "interval":
                interval = float(task.trigger_value or "300")
                due = _next_interval_ts(interval, task.last_run_at)
            else:
                due = _parse_cron_next(task.trigger_value, task.last_run_at)

            if now >= due:
                asyncio.create_task(
                    run_autonomous_task(
                        task.agent_id,
                        task.objective,
                        task_id=task.id,
                        trigger="scheduler",
                        max_iterations=task.max_iterations,
                    )
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("Task %s scheduling error: %s", task.id, e)


async def start_scheduler() -> None:
    global _scheduler_task, _running
    if _scheduler_task and not _scheduler_task.done():
        return
    _running = True
    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(_scheduler_loop())
    loop.create_task(_monitor_system())
    logger.info("Autonomy subsystem started")


async def stop_scheduler() -> None:
    global _running, _scheduler_task
    _running = False
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
    logger.info("Autonomy subsystem stopped")
