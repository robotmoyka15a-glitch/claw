"""Agent lifecycle + streaming conversation with tool-calling.

stream_events(agent_id, user_text) yields a sequence of dict events that the
WebSocket layer can forward verbatim to the frontend:

    {"type": "status",      "status": "thinking"}
    {"type": "delta",       "text": "..."}
    {"type": "tool_call",   "id": "...", "name": "processes.list",
                             "arguments": { ... }}
    {"type": "tool_result", "id": "...", "name": "processes.list",
                             "ok": true, "value": {...}}
    {"type": "tool_error",  "id": "...", "name": "processes.list",
                             "error": "..."}
    {"type": "status",      "status": "idle"}
    {"type": "end"}

The same events are also broadcast on the global /ws/agents-state channel so
the frontend can keep the in-room avatars animated even when their chat panel
is closed.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.ws_manager import ws_manager
from app.llm import (
    DoneEvent,
    LLMMessage,
    TextDelta,
    ToolCallEvent,
    ToolSpec,
    get_provider,
)
from app.tools import build_default_registry

from .models import Agent, AgentMessage
from .presets import PRESETS


DEFAULT_SEATING = {
    "boss":            {"desk": "center",     "color": "#f5b301"},
    "sysadmin":        {"desk": "left",       "color": "#4ade80"},
    "vk_watcher":      {"desk": "right",      "color": "#60a5fa"},
    "terminal_helper": {"desk": "back_left",  "color": "#a78bfa"},
    "researcher":      {"desk": "back_right", "color": "#f472b6"},
}

MAX_TOOL_ITERATIONS = 4
MAX_MESSAGES_IN_CONTEXT = 30

# Per-agent live status kept in-memory for the agent-state websocket.
_AGENT_STATE: dict[str, dict] = {}


# -------------------------- CRUD -----------------------------------------

async def seed_defaults_if_empty() -> None:
    async with SessionLocal() as s:
        any_agent = (await s.execute(select(Agent))).scalars().first()
        if any_agent is not None:
            return
        for preset_key, preset in PRESETS.items():
            s.add(
                Agent(
                    id=uuid.uuid4().hex,
                    name=preset.name,
                    preset=preset_key,
                    desk=preset.desk,
                    color=preset.color,
                    llm_provider="ollama",
                    llm_model="",
                    system_prompt=preset.system_prompt,
                    temperature=0.7,
                    allowed_tools=",".join(preset.default_tools),
                )
            )
        await s.commit()


def _parse_tools(csv: str) -> list[str]:
    return [t for t in (csv or "").split(",") if t.strip()]


def _serialize(a: Agent) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "preset": a.preset,
        "title": PRESETS[a.preset].title if a.preset in PRESETS else a.preset,
        "desk": a.desk,
        "color": a.color,
        "llm_provider": a.llm_provider,
        "llm_model": a.llm_model,
        "system_prompt": a.system_prompt,
        "temperature": a.temperature,
        "allowed_tools": _parse_tools(a.allowed_tools),
        "created_at": a.created_at,
        "state": _AGENT_STATE.get(a.id, {"status": "idle", "last_tool": None}),
    }


async def list_agents() -> list[dict]:
    async with SessionLocal() as s:
        rows = (await s.execute(select(Agent))).scalars().all()
        return [_serialize(a) for a in rows]


async def get_agent(agent_id: str) -> dict | None:
    async with SessionLocal() as s:
        a = await s.get(Agent, agent_id)
        return _serialize(a) if a else None


async def create_agent(data: dict) -> dict:
    preset_key = data.get("preset") or "researcher"
    preset = PRESETS.get(preset_key)
    seat = DEFAULT_SEATING.get(preset_key, {"desk": "spare", "color": "#94a3b8"})
    allowed = data.get("allowed_tools")
    if isinstance(allowed, list):
        allowed_csv = ",".join(allowed)
    elif isinstance(allowed, str):
        allowed_csv = allowed
    else:
        allowed_csv = ",".join(preset.default_tools) if preset else ""

    async with SessionLocal() as s:
        a = Agent(
            id=uuid.uuid4().hex,
            name=data.get("name") or (preset.name if preset else "Agent"),
            preset=preset_key,
            desk=data.get("desk") or seat["desk"],
            color=data.get("color") or seat["color"],
            llm_provider=data.get("llm_provider") or "ollama",
            llm_model=data.get("llm_model") or "",
            system_prompt=data.get("system_prompt")
            or (preset.system_prompt if preset else ""),
            temperature=float(data.get("temperature", 0.7)),
            allowed_tools=allowed_csv,
        )
        s.add(a)
        await s.commit()
        await s.refresh(a)
        return _serialize(a)


async def update_agent(agent_id: str, patch: dict) -> dict | None:
    async with SessionLocal() as s:
        a = await s.get(Agent, agent_id)
        if not a:
            return None
        for k in (
            "name",
            "desk",
            "color",
            "llm_provider",
            "llm_model",
            "system_prompt",
            "temperature",
        ):
            if k in patch and patch[k] is not None:
                setattr(a, k, patch[k])
        # allowed_tools can arrive as list or string
        if "allowed_tools" in patch and patch["allowed_tools"] is not None:
            v = patch["allowed_tools"]
            a.allowed_tools = ",".join(v) if isinstance(v, list) else str(v)
        await s.commit()
        await s.refresh(a)
        return _serialize(a)


async def delete_agent(agent_id: str) -> bool:
    async with SessionLocal() as s:
        a = await s.get(Agent, agent_id)
        if not a:
            return False
        await s.delete(a)
        await s.commit()
        _AGENT_STATE.pop(agent_id, None)
        return True


async def list_messages(agent_id: str, limit: int = 200) -> list[dict]:
    async with SessionLocal() as s:
        q = (
            select(AgentMessage)
            .where(AgentMessage.agent_id == agent_id)
            .order_by(AgentMessage.ts.asc())
            .limit(limit)
        )
        rows = (await s.execute(q)).scalars().all()
        # Parse tool_calls JSON back out of 'content' when role is assistant
        # and tool_calls were stored there (we use a simple prefix).
        return [
            {"id": m.id, "role": m.role, "content": m.content, "ts": m.ts}
            for m in rows
        ]


# -------------------------- chat --------------------------------------

def _build_tool_specs(agent: Agent) -> list[ToolSpec]:
    reg = build_default_registry()
    names = _parse_tools(agent.allowed_tools)
    return [
        ToolSpec(name=t.name, description=t.description, parameters=t.parameters)
        for t in reg.filter(allow=names)
    ]


async def _append_message(
    s: AsyncSession,
    agent_id: str,
    role: str,
    content: str,
) -> None:
    s.add(AgentMessage(agent_id=agent_id, role=role, content=content))
    await s.commit()


async def _set_state(agent_id: str, **patch: Any) -> dict:
    state = _AGENT_STATE.setdefault(
        agent_id, {"status": "idle", "last_tool": None}
    )
    state.update(patch)
    # Broadcast globally so room avatars can react.
    await ws_manager.broadcast(
        "agents-state",
        {"agent_id": agent_id, "state": state, "ts": time.time()},
    )
    return state


async def stream_events(
    agent_id: str,
    user_text: str,
) -> AsyncIterator[dict]:
    """Main conversation loop with tool-calling."""
    async with SessionLocal() as s:
        agent = await s.get(Agent, agent_id)
    if not agent:
        yield {"type": "error", "error": "agent not found"}
        return

    async with SessionLocal() as s:
        await _append_message(s, agent_id, "user", user_text)

    # Build the LLM-visible message list from stored history.
    llm_messages: list[LLMMessage] = [LLMMessage("system", agent.system_prompt)]
    async with SessionLocal() as s:
        q = (
            select(AgentMessage)
            .where(AgentMessage.agent_id == agent_id)
            .order_by(AgentMessage.ts.asc())
        )
        history = (await s.execute(q)).scalars().all()
    for m in history[-MAX_MESSAGES_IN_CONTEXT:]:
        # Persisted tool-call records encode their payload in content with
        # a prefix so we can rehydrate them. See _persist_assistant_turn.
        if m.role == "assistant" and m.content.startswith("::tool_calls::"):
            try:
                payload = json.loads(m.content[len("::tool_calls::"):])
                llm_messages.append(
                    LLMMessage(
                        role="assistant",
                        content=payload.get("text", ""),
                        tool_calls=payload.get("tool_calls") or [],
                    )
                )
                continue
            except Exception:  # noqa: BLE001
                pass
        if m.role == "tool" and m.content.startswith("::tool_result::"):
            try:
                payload = json.loads(m.content[len("::tool_result::"):])
                llm_messages.append(
                    LLMMessage(
                        role="tool",
                        content=payload.get("content", ""),
                        tool_call_id=payload.get("tool_call_id"),
                        name=payload.get("name"),
                    )
                )
                continue
            except Exception:  # noqa: BLE001
                pass
        llm_messages.append(LLMMessage(role=m.role, content=m.content))  # type: ignore[arg-type]

    provider = get_provider(agent.llm_provider)
    tools = _build_tool_specs(agent)
    registry = build_default_registry()

    await _set_state(agent_id, status="thinking", last_tool=None)
    yield {"type": "status", "status": "thinking"}

    for iteration in range(MAX_TOOL_ITERATIONS):
        # Collect streaming output for this LLM turn.
        assistant_text: list[str] = []
        tool_calls_emitted: list[dict] = []
        finish_reason = "stop"

        try:
            async for event in provider.stream_chat(
                llm_messages,
                model=agent.llm_model or "",
                temperature=agent.temperature,
                tools=tools,
            ):
                if isinstance(event, TextDelta):
                    assistant_text.append(event.text)
                    yield {"type": "delta", "text": event.text}
                elif isinstance(event, ToolCallEvent):
                    tool_calls_emitted.append(
                        {"id": event.id, "name": event.name, "arguments": event.arguments}
                    )
                elif isinstance(event, DoneEvent):
                    finish_reason = event.finish_reason
        except Exception as e:  # noqa: BLE001
            err = f"[LLM error: {e}]"
            yield {"type": "delta", "text": err}
            assistant_text.append(err)
            finish_reason = "error"

        full_text = "".join(assistant_text)

        # Persist the assistant turn.
        if tool_calls_emitted:
            payload = {"text": full_text, "tool_calls": tool_calls_emitted}
            async with SessionLocal() as s:
                await _append_message(
                    s, agent_id, "assistant", "::tool_calls::" + json.dumps(payload)
                )
        elif full_text:
            async with SessionLocal() as s:
                await _append_message(s, agent_id, "assistant", full_text)

        # Append to LLM context too, so subsequent iterations see this turn.
        llm_messages.append(
            LLMMessage(
                role="assistant",
                content=full_text,
                tool_calls=tool_calls_emitted or None,
            )
        )

        if not tool_calls_emitted or finish_reason == "error":
            break

        # Execute each tool call.
        for tc in tool_calls_emitted:
            tool = registry.get(tc["name"])
            yield {
                "type": "tool_call",
                "id": tc["id"],
                "name": tc["name"],
                "arguments": tc["arguments"],
            }
            await _set_state(agent_id, status="tool", last_tool=tc["name"])

            if tool is None:
                err = f"tool not registered: {tc['name']}"
                yield {"type": "tool_error", "id": tc["id"], "name": tc["name"], "error": err}
                result_text = json.dumps({"error": err})
            else:
                # Is this tool allowed for this agent?
                if tc["name"] not in _parse_tools(agent.allowed_tools):
                    err = f"tool {tc['name']!r} is not allowed for this agent"
                    yield {"type": "tool_error", "id": tc["id"], "name": tc["name"], "error": err}
                    result_text = json.dumps({"error": err})
                else:
                    try:
                        args = json.loads(tc["arguments"] or "{}")
                    except json.JSONDecodeError as e:
                        err = f"bad tool arguments JSON: {e}"
                        yield {"type": "tool_error", "id": tc["id"], "name": tc["name"], "error": err}
                        result_text = json.dumps({"error": err})
                    else:
                        try:
                            value = await tool.run(args)
                            yield {
                                "type": "tool_result",
                                "id": tc["id"],
                                "name": tc["name"],
                                "ok": True,
                                "value": value,
                            }
                            result_text = json.dumps(value, default=str)
                        except Exception as e:  # noqa: BLE001
                            yield {
                                "type": "tool_error",
                                "id": tc["id"],
                                "name": tc["name"],
                                "error": str(e),
                            }
                            result_text = json.dumps({"error": str(e)})

            # Persist and append as a 'tool' role message for the next LLM turn.
            tool_payload = {
                "tool_call_id": tc["id"],
                "name": tc["name"],
                "content": result_text,
            }
            async with SessionLocal() as s:
                await _append_message(
                    s,
                    agent_id,
                    "tool",
                    "::tool_result::" + json.dumps(tool_payload),
                )
            llm_messages.append(
                LLMMessage(
                    role="tool",
                    content=result_text,
                    tool_call_id=tc["id"],
                    name=tc["name"],
                )
            )

        await _set_state(agent_id, status="thinking", last_tool=None)
        yield {"type": "status", "status": "thinking"}
        # Loop again; the LLM will now see the tool results.

    await _set_state(agent_id, status="idle", last_tool=None)
    yield {"type": "status", "status": "idle"}
    yield {"type": "end"}


# -------------------- Helper: non-streaming one-shot ---------------------
# Used by the agents.delegate tool so one agent can synchronously ask another.

async def run_one_turn(
    agent_id: str,
    user_text: str,
    *,
    allow_tools: bool = True,
) -> str:
    """Run one full streaming turn and return only the final assistant text."""
    parts: list[str] = []
    async for ev in stream_events(agent_id, user_text):
        if ev.get("type") == "delta":
            parts.append(ev.get("text", ""))
    return "".join(parts)


# -------------------- Public state helpers -------------------------------

def current_states() -> list[dict]:
    return [
        {"agent_id": aid, "state": st} for aid, st in _AGENT_STATE.items()
    ]
