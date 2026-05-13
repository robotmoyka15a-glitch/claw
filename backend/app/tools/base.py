"""Base abstractions for tools usable by agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


class ToolError(Exception):
    """Raised by a tool when execution fails in a user-reportable way."""


ToolFn = Callable[..., Awaitable[Any]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON-schema (object)
    fn: ToolFn
    # Category is used for grouping in the UI and for per-agent allowlists.
    category: str = "misc"
    # Dangerous tools must be explicitly allowed on a per-agent basis.
    dangerous: bool = False
    # Tags surfaced in the UI. Free-form.
    tags: list[str] = field(default_factory=list)

    def to_openai_schema(self) -> dict[str, Any]:
        """OpenAI/Qwen tool-calling wire format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }

    def to_ollama_schema(self) -> dict[str, Any]:
        """Ollama native tool format (same shape as OpenAI)."""
        return self.to_openai_schema()

    async def run(self, args: dict[str, Any]) -> Any:
        try:
            return await self.fn(**(args or {}))
        except ToolError:
            raise
        except TypeError as e:
            raise ToolError(f"bad arguments for {self.name}: {e}") from e
        except Exception as e:  # noqa: BLE001
            raise ToolError(f"{self.name} failed: {e}") from e


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def filter(self, *, allow: list[str] | None = None) -> list[Tool]:
        if allow is None:
            return self.all()
        return [t for t in self.all() if t.name in allow]

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "dangerous": t.dangerous,
                "tags": t.tags,
                "parameters": t.parameters,
            }
            for t in self.all()
        ]
