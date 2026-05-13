"""Generic OpenAI-compatible chat completions provider.

Used for:
  * Qwen running locally (vLLM, LM Studio, llama.cpp server, Qwen.cpp)
  * Qwen cloud via DashScope compatible endpoint
  * OpenRouter, Together, Groq, etc.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from .base import LLMMessage


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
            except Exception:
                # some endpoints (DashScope) don't expose /models publicly
                return [self.default_model]

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
            "temperature": temperature,
        }
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
                        return
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        yield piece

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
    ) -> str:
        chunks: list[str] = []
        async for d in self.stream_chat(messages, model, temperature):
            chunks.append(d)
        return "".join(chunks)
