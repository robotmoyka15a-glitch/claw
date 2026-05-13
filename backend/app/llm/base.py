"""Common LLM provider interface with tool-calling support.

A provider's stream_chat(...) yields a sequence of `ChatEvent` objects:

    TextDelta(text)            — streaming text from the assistant
    ToolCallEvent(id, name,    — the assistant wants to call a tool. All
                  arguments)    arguments are already accumulated.
    DoneEvent(finish_reason)   — end of turn.

If the model chose to call tools, the assistant turn finishes with a DoneEvent
whose finish_reason is 'tool_calls'. The manager is expected to:
    1. persist an assistant message with the raw tool_calls payload,
    2. execute each tool,
    3. feed 'tool' role messages back into stream_chat, and call it again.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, List, Literal, Optional, Protocol, Union


Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class LLMMessage:
    role: Role
    content: str
    # Populated only for role="assistant" messages that triggered tool calls,
    # or for role="tool" messages providing the result of one call.
    tool_calls: Optional[List[dict]] = None  # [{"id","name","arguments"(str)}]
    tool_call_id: Optional[str] = None       # set on role="tool" messages
    name: Optional[str] = None               # tool name for role="tool"


@dataclass
class TextDelta:
    text: str
    type: str = "text"


@dataclass
class ToolCallEvent:
    id: str
    name: str
    arguments: str   # JSON string as produced by the model
    type: str = "tool_call"


@dataclass
class DoneEvent:
    finish_reason: str = "stop"  # 'stop' | 'tool_calls' | 'length' | ...
    type: str = "done"


ChatEvent = Union[TextDelta, ToolCallEvent, DoneEvent]


@dataclass
class ToolSpec:
    """Provider-agnostic description of a tool. Adapters translate it into
    the wire format expected by each provider."""

    name: str
    description: str
    parameters: dict


class LLMProvider(Protocol):
    """
    FIX #4: Protocol исправлен:
      - stream_chat помечен как async def (возвращает AsyncIterator через async generator)
      - tools: List[ToolSpec] с корректным дефолтом пустого списка вместо Ellipsis
    """
    name: str
    default_model: str

    async def list_models(self) -> List[str]: ...

    async def stream_chat(  # type: ignore[override]
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        tools: Optional[List[ToolSpec]] = None,
    ) -> AsyncIterator[ChatEvent]: ...
