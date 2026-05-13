"""delegate_to_agent tool — lets one agent (typically the Chief) ask another
agent a question. The callee runs one non-streaming tool-enabled turn and
returns its final text.

Imported lazily by registry.build_default_registry so we avoid an import cycle
with app.agents.manager.
"""
from __future__ import annotations

from typing import Any

from .base import Tool, ToolError


async def _delegate_to_agent(agent_id: str, message: str) -> dict[str, Any]:
    # Local import — manager imports the registry at startup, we can't import
    # it at module top-level.
    from app.agents import manager

    reply = await manager.run_one_turn(agent_id, message, allow_tools=True)
    if not reply:
        raise ToolError("agent produced empty reply")
    return {"agent_id": agent_id, "reply": reply}


delegate_to_agent_tool = Tool(
    name="agents.delegate",
    description=(
        "Ask another agent (by id) to do something. The other agent runs one "
        "turn with its own tools and system prompt and returns its final text. "
        "Use this when a task fits another agent's role better (e.g. the Chief "
        "delegates a VK question to 'vk_watcher')."
    ),
    parameters={
        "type": "object",
        "required": ["agent_id", "message"],
        "properties": {
            "agent_id": {"type": "string", "description": "Target agent id."},
            "message": {"type": "string", "description": "The request in plain text."},
        },
    },
    fn=_delegate_to_agent,
    category="agents",
    tags=["coordination"],
)
