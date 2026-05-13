"""Ollama provider. Native /api/chat endpoint; streaming + tool-calling.

Notes:
    * Ollama's streaming tool-calling support depends on the model. Models like
      qwen2.5, llama3.1 and mistral-nemo produce proper tool_calls payloads.
      For models that don't support tools, pass tools=[] and use the model as
      a plain chat agent.
    * Ollama returns a full `message.tool_calls` array at the end of the
      streaming response (no incremental accumulation needed).
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from .base import ChatEvent, DoneEvent, LLMMessage, TextDelta, ToolCallEvent, ToolSpec


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, default_model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]

    @staticmethod
    def _render_messages(messages: list[LLMMessage]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            entry: dict = {"role": m.role, "content": m.content or ""}
            if m.role == "assistant" and m.tool_calls:
                # Ollama expects: tool_calls=[{"function":{"name","arguments":{}}}]
                entry["tool_calls"] = [
                    {
                        "function": {
                            "name": tc["name"],
                            "arguments": _safe_json_loads(tc.get("arguments") or "{}"),
                        }
                    }
                    for tc in m.tool_calls
                ]
            if m.role == "tool":
                # Ollama tool-result message
                if m.name:
                    entry["name"] = m.name
            out.append(entry)
        return out

    @staticmethod
    def _render_tools(tools: list[ToolSpec]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters or {"type": "object", "properties": {}},
                },
            }
            for t in tools
        ]

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[ChatEvent]:
        payload: dict = {
            "model": model or self.default_model,
            "messages": self._render_messages(messages),
            "stream": True,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = self._render_tools(tools)

        tool_call_counter = 0

        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream("POST", f"{self.base_url}/api/chat", json=payload) as r:
                r.raise_for_status()
                async for raw in r.aiter_lines():
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    msg = obj.get("message") or {}
                    piece = msg.get("content")
                    if piece:
                        yield TextDelta(text=piece)

                    if obj.get("done"):
                        tool_calls = msg.get("tool_calls") or []
                        for tc in tool_calls:
                            fn = tc.get("function") or {}
                            tool_call_counter += 1
                            yield ToolCallEvent(
                                id=tc.get("id") or f"call_{tool_call_counter}",
                                name=fn.get("name") or "",
                                arguments=json.dumps(fn.get("arguments") or {}),
                            )
                        yield DoneEvent(
                            finish_reason="tool_calls" if tool_calls else "stop"
                        )
                        return


def _safe_json_loads(s: str):
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return {}
