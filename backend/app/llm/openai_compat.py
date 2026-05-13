"""OpenAI-compatible chat completions provider with streaming tool-calls.

Used for:
    * Qwen running locally (vLLM / LM Studio / llama.cpp / Qwen.cpp)
    * Qwen cloud via DashScope compatible endpoint
    * OpenRouter, Together, Groq, and anything else that speaks the OpenAI
      /v1/chat/completions dialect.

Tool-call stream handling follows the OpenAI SSE format: deltas arrive with
`choices[0].delta.tool_calls[]` where each entry has an `index` and partial
`function.name` / `function.arguments` strings to accumulate.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from .base import ChatEvent, DoneEvent, LLMMessage, TextDelta, ToolCallEvent, ToolSpec


class OpenAICompatProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        default_model: str,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key or 'not-needed'}",
            "Content-Type": "application/json",
        }

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0, headers=self._headers()) as c:
            try:
                r = await c.get(f"{self.base_url}/models")
                r.raise_for_status()
                data = r.json()
                return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
            except Exception:  # noqa: BLE001
                # some endpoints (DashScope) don't expose /models publicly
                return [self.default_model]

    @staticmethod
    def _render_messages(messages: list[LLMMessage]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            entry: dict = {"role": m.role, "content": m.content or ""}
            if m.role == "assistant" and m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc.get("arguments") or "{}",
                        },
                    }
                    for tc in m.tool_calls
                ]
            if m.role == "tool":
                if m.tool_call_id:
                    entry["tool_call_id"] = m.tool_call_id
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
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = self._render_tools(tools)
            payload["tool_choice"] = "auto"

        # Accumulators for streaming tool-calls: index -> {id, name, arguments}
        tc_buf: dict[int, dict] = {}
        finish_reason: str = "stop"

        async with httpx.AsyncClient(timeout=None, headers=self._headers()) as c:
            async with c.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
            ) as r:
                r.raise_for_status()
                async for raw in r.aiter_lines():
                    if not raw or not raw.startswith("data:"):
                        continue
                    data = raw[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    ch = choices[0]
                    delta = ch.get("delta") or {}
                    if delta.get("content"):
                        yield TextDelta(text=delta["content"])
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        slot = tc_buf.setdefault(
                            idx, {"id": "", "name": "", "arguments": ""}
                        )
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["name"] = fn["name"]
                        if fn.get("arguments"):
                            slot["arguments"] += fn["arguments"]
                    if ch.get("finish_reason"):
                        finish_reason = ch["finish_reason"]

        # Emit accumulated tool calls, if any.
        for _, slot in sorted(tc_buf.items()):
            yield ToolCallEvent(
                id=slot["id"] or f"call_{len(tc_buf)}",
                name=slot["name"],
                arguments=slot["arguments"] or "{}",
            )
        yield DoneEvent(finish_reason=finish_reason)
