"""Ollama provider. Uses the native /api/chat endpoint with streaming."""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from .base import LLMMessage


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

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model or self.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature},
        }
        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream("POST", f"{self.base_url}/api/chat", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = obj.get("message") or {}
                    piece = msg.get("content")
                    if piece:
                        yield piece
                    if obj.get("done"):
                        return

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
    ) -> str:
        chunks: list[str] = []
        async for delta in self.stream_chat(messages, model, temperature):
            chunks.append(delta)
        return "".join(chunks)
