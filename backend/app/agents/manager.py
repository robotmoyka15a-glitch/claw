"""Agent lifecycle: create, update, delete, chat."""
from __future__ import annotations

import uuid
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.llm import LLMMessage, get_provider

from .models import Agent, AgentMessage
from .presets import PRESETS


DEFAULT_SEATING = {
    "boss":            {"desk": "center",     "color": "#f5b301"},
    "sysadmin":        {"desk": "left",       "color": "#4ade80"},
    "vk_watcher":      {"desk": "right",      "color": "#60a5fa"},
    "terminal_helper": {"desk": "back_left",  "color": "#a78bfa"},
    "researcher":      {"desk": "back_right", "color": "#f472b6"},
}


async def seed_defaults_if_empty() -> None:
    """Populate the room with the five default agents on first launch."""
    async with SessionLocal() as s:
        total = (await s.execute(select(Agent))).scalars().first()
        if total is not None:
            return
        for preset_key, preset in PRESETS.items():
            agent = Agent(
                id=uuid.uuid4().hex,
                name=preset.name,
                preset=preset_key,
                desk=preset.desk,
                color=preset.color,
                llm_provider="ollama",
                llm_model="",
                system_prompt=preset.system_prompt,
                temperature=0.7,
            )
            s.add(agent)
        await s.commit()


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
        "created_at": a.created_at,
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
        return True


async def list_messages(agent_id: str, limit: int = 100) -> list[dict]:
    async with SessionLocal() as s:
        q = (
            select(AgentMessage)
            .where(AgentMessage.agent_id == agent_id)
            .order_by(AgentMessage.ts.asc())
            .limit(limit)
        )
        rows = (await s.execute(q)).scalars().all()
        return [
            {"id": m.id, "role": m.role, "content": m.content, "ts": m.ts}
            for m in rows
        ]


async def _append_message(
    s: AsyncSession, agent_id: str, role: str, content: str
) -> None:
    s.add(AgentMessage(agent_id=agent_id, role=role, content=content))
    await s.commit()


async def stream_reply(
    agent_id: str, user_text: str
) -> AsyncIterator[str]:
    """Yield reply deltas for a user message, persisting both messages."""
    async with SessionLocal() as s:
        agent = await s.get(Agent, agent_id)
        if not agent:
            yield "[error: agent not found]"
            return

        await _append_message(s, agent_id, "user", user_text)

        # Build history.
        history_q = (
            select(AgentMessage)
            .where(AgentMessage.agent_id == agent_id)
            .order_by(AgentMessage.ts.asc())
        )
        msgs = (await s.execute(history_q)).scalars().all()

    provider = get_provider(agent.llm_provider)
    llm_messages: list[LLMMessage] = [LLMMessage("system", agent.system_prompt)]
    for m in msgs[-30:]:
        llm_messages.append(LLMMessage(m.role, m.content))  # type: ignore[arg-type]

    collected: list[str] = []
    try:
        async for delta in provider.stream_chat(
            llm_messages,
            model=agent.llm_model or "",
            temperature=agent.temperature,
        ):
            collected.append(delta)
            yield delta
    except Exception as e:  # noqa: BLE001
        err = f"[LLM error: {e}]"
        collected.append(err)
        yield err

    full_reply = "".join(collected)
    if full_reply:
        async with SessionLocal() as s:
            await _append_message(s, agent_id, "assistant", full_reply)
