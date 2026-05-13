"""Provider registry. Instantiated lazily from settings."""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings

from .ollama_provider import OllamaProvider
from .openai_compat import OpenAICompatProvider


PROVIDER_KEYS = ("ollama", "qwen_local", "qwen_cloud")


@lru_cache(maxsize=1)
def _build_registry():
    s = get_settings()
    return {
        "ollama": OllamaProvider(
            base_url=s.ollama_base_url,
            default_model=s.ollama_default_model,
        ),
        "qwen_local": OpenAICompatProvider(
            name="qwen_local",
            base_url=s.qwen_local_base_url,
            api_key=s.qwen_local_api_key,
            default_model=s.qwen_local_default_model,
        ),
        "qwen_cloud": OpenAICompatProvider(
            name="qwen_cloud",
            base_url=s.qwen_cloud_base_url,
            api_key=s.qwen_cloud_api_key,
            default_model=s.qwen_cloud_default_model,
        ),
    }


def get_provider(key: str):
    reg = _build_registry()
    if key not in reg:
        raise KeyError(f"Unknown LLM provider: {key}. Known: {list(reg)}")
    return reg[key]


def list_providers() -> list[str]:
    return list(_build_registry().keys())
