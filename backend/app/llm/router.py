"""ModelRouter — intelligent LLM provider and model selection.

Instead of every agent hardcoding a provider key, the router picks the
best available provider based on task requirements:

  • needs_tools       — model must support function/tool calling
  • needs_long_ctx    — context exceeds 32 k tokens
  • needs_vision      — user sent an image
  • needs_speed       — latency-sensitive (quick status check, short reply)
  • needs_reasoning   — complex multi-step reasoning / code generation
  • offline_only      — never use cloud providers (privacy)

The router also implements a FALLBACK CHAIN: if the preferred provider is
offline or errors, the next one in the chain is tried automatically.

Usage (in agent manager):
    from app.llm.router import ModelRouter
    router = ModelRouter()
    provider, model = await router.route(agent, task_hint)
    async for event in provider.stream_chat(messages, model, ...):
        ...
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from .base import LLMProvider
from .ollama_provider import OllamaProvider
from .openai_compat import OpenAICompatProvider
from .registry import _build_registry

logger = logging.getLogger("claw.llm.router")


# ── Capability registry ───────────────────────────────────────────────────────

@dataclass
class ModelCapability:
    """What a specific model can do."""
    provider: str
    model: str                         # empty string = provider default
    # Task suitability scores (0-10)
    tool_calling: int = 5              # supports function/tool calling
    long_context: int = 5              # handles long context well (>32k)
    reasoning: int = 5                 # multi-step / CoT quality
    speed: int = 5                     # lower latency (smaller models score higher)
    vision: int = 0                    # can process images
    offline: bool = True               # runs locally (no cloud)
    max_context_tokens: int = 32_768
    tags: list[str] = field(default_factory=list)


# Built-in capability table. Extended at runtime by Ollama model discovery.
_BUILTIN_CAPABILITIES: list[ModelCapability] = [
    # ── Ollama models ──
    ModelCapability(
        provider="ollama", model="qwen2.5:7b",
        tool_calling=9, reasoning=8, speed=7, long_context=6,
        max_context_tokens=32_768, tags=["chat", "code", "tools"],
    ),
    ModelCapability(
        provider="ollama", model="qwen2.5:14b",
        tool_calling=9, reasoning=9, speed=5, long_context=7,
        max_context_tokens=32_768, tags=["chat", "code", "tools"],
    ),
    ModelCapability(
        provider="ollama", model="qwen2.5:3b",
        tool_calling=7, reasoning=6, speed=9, long_context=4,
        max_context_tokens=32_768, tags=["fast", "chat"],
    ),
    ModelCapability(
        provider="ollama", model="llama3.1:8b",
        tool_calling=8, reasoning=8, speed=7, long_context=5,
        max_context_tokens=131_072, tags=["chat", "tools"],
    ),
    ModelCapability(
        provider="ollama", model="mistral:7b",
        tool_calling=7, reasoning=7, speed=8, long_context=4,
        max_context_tokens=32_768, tags=["chat", "fast"],
    ),
    # ── Qwen local (OpenAI-compat) ──
    ModelCapability(
        provider="qwen_local", model="",
        tool_calling=9, reasoning=9, speed=8, long_context=7,
        max_context_tokens=131_072, tags=["chat", "code", "tools"],
    ),
    # ── Qwen cloud ──
    ModelCapability(
        provider="qwen_cloud", model="qwen-plus",
        tool_calling=9, reasoning=9, speed=6, long_context=9,
        offline=False, max_context_tokens=131_072,
        tags=["chat", "tools", "cloud"],
    ),
    ModelCapability(
        provider="qwen_cloud", model="qwen-max",
        tool_calling=10, reasoning=10, speed=5, long_context=9,
        offline=False, max_context_tokens=131_072,
        tags=["chat", "tools", "cloud", "premium"],
    ),
    ModelCapability(
        provider="qwen_cloud", model="qwen-long",
        tool_calling=8, reasoning=7, speed=5, long_context=10,
        offline=False, max_context_tokens=10_000_000,
        tags=["cloud", "long-context"],
    ),
    ModelCapability(
        provider="qwen_cloud", model="qwen-vl-plus",
        tool_calling=7, reasoning=8, speed=5, vision=10, long_context=6,
        offline=False, max_context_tokens=32_768,
        tags=["vision", "cloud"],
    ),
]


@dataclass
class TaskHint:
    """Hints from the agent manager about what the current task needs."""
    needs_tools: bool = False
    needs_long_ctx: bool = False
    needs_vision: bool = False
    needs_speed: bool = False
    needs_reasoning: bool = False
    offline_only: bool = False
    estimated_tokens: int = 0


def _score(cap: ModelCapability, hint: TaskHint) -> float:
    """Compute a suitability score for a capability given hints."""
    s = 0.0
    if hint.needs_tools:
        s += cap.tool_calling * 3
    if hint.needs_long_ctx:
        s += cap.long_context * 2
        if hint.estimated_tokens > cap.max_context_tokens:
            return -1000   # hard disqualify
    if hint.needs_vision:
        if cap.vision == 0:
            return -1000   # hard disqualify
        s += cap.vision * 4
    if hint.needs_speed:
        s += cap.speed * 2
    if hint.needs_reasoning:
        s += cap.reasoning * 2
    if hint.offline_only and not cap.offline:
        return -1000       # hard disqualify
    # small bonus for local models (privacy, latency)
    if cap.offline:
        s += 1
    return s


# ── Router class ──────────────────────────────────────────────────────────────

class ModelRouter:
    """Select the best provider+model for a task, with automatic fallback."""

    def __init__(self) -> None:
        self._caps = list(_BUILTIN_CAPABILITIES)

    async def _probe(self, provider: LLMProvider) -> bool:
        """Quick liveness check. Returns True if provider is reachable."""
        try:
            await provider.list_models()
            return True
        except Exception:  # noqa: BLE001
            return False

    async def route(
        self,
        agent_provider: str,
        agent_model: str,
        hint: Optional[TaskHint] = None,
        *,
        respect_agent_choice: bool = True,
    ) -> tuple[LLMProvider, str]:
        """Return (provider, model_name) for this task.

        If respect_agent_choice=True (default) and the agent's configured
        provider/model can handle the task, use it.  Only route to a
        different provider if the agent's choice is unqualified or offline.
        """
        hint = hint or TaskHint()
        reg = _build_registry()

        # 1. Try the agent's own choice first.
        if respect_agent_choice and agent_provider in reg:
            prov = reg[agent_provider]
            if await self._probe(prov):
                # Check if the chosen model handles the task requirements
                cap = self._find_cap(agent_provider, agent_model)
                if cap is None or _score(cap, hint) >= 0:
                    logger.debug(
                        "router: using agent choice %s/%s", agent_provider, agent_model
                    )
                    return prov, agent_model

        # 2. Score all capabilities and try in descending order.
        candidates = sorted(
            [(cap, _score(cap, hint)) for cap in self._caps],
            key=lambda x: -x[1],
        )
        for cap, score in candidates:
            if score < 0:
                continue
            if cap.provider not in reg:
                continue
            prov = reg[cap.provider]
            try:
                alive = await self._probe(prov)
            except Exception:  # noqa: BLE001
                alive = False
            if alive:
                logger.info(
                    "router: selected %s/%s (score=%.1f, hint=%s)",
                    cap.provider, cap.model or "default", score, hint,
                )
                return prov, cap.model

        # 3. Last resort: return the first provider without checking
        first_key = next(iter(reg))
        logger.warning("router: all providers failed probe, using %s as last resort", first_key)
        return reg[first_key], ""

    def _find_cap(self, provider: str, model: str) -> Optional[ModelCapability]:
        for c in self._caps:
            if c.provider == provider and (c.model == model or c.model == ""):
                return c
        return None

    async def add_ollama_models(self) -> None:
        """Discover models from the local Ollama instance and add them if missing."""
        reg = _build_registry()
        prov: OllamaProvider = reg.get("ollama")  # type: ignore[assignment]
        if prov is None:
            return
        try:
            models = await prov.list_models()
        except Exception:  # noqa: BLE001
            return
        existing = {(c.provider, c.model) for c in self._caps}
        for name in models:
            if ("ollama", name) not in existing:
                # Infer rough capabilities from name
                is_large = any(x in name for x in ("70b", "34b", "30b", "22b"))
                is_small = any(x in name for x in ("1b", "3b", "0.5b"))
                self._caps.append(ModelCapability(
                    provider="ollama", model=name,
                    tool_calling=8 if "qwen" in name or "llama" in name else 6,
                    reasoning=9 if is_large else (5 if is_small else 7),
                    speed=3 if is_large else (9 if is_small else 7),
                    long_context=7,
                    tags=["ollama", "local"],
                ))
                logger.debug("router: discovered ollama model %s", name)


# Module-level singleton
_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
