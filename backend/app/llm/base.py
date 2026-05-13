"""Common LLM provider interface. Streaming is modeled as an async iterator
of string deltas. Non-streaming calls just concatenate the stream.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Literal, Protocol


Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class LLMMessage:
    role: Role
    content: str


class LLMProvider(Protocol):
    name: str

    async def list_models(self) -> list[str]: ...

    def stream_chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]: ...

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
    ) -> str: ...
