"""
/api/models  — агрегированный взгляд на все локальные LLM.
/ws/models   — WebSocket с live-обновлением каждые 8 секунд.

Структура ответа:

  providers: [
    {
      key: "ollama",
      label: "Ollama",
      online: true,
      base_url: "http://127.0.0.1:11434",
      models: [
        {
          name: "qwen2.5:7b",
          size_gb: 4.4,
          family: "qwen2",
          modified_at: "2024-11-01T...",
          running: true,          # сейчас загружена в VRAM
          used_by_agents: ["boss_id", "vk_watcher_id"],
          quantization: "Q4_K_M",
          parameters: "7B",
          context_length: 32768,
        }
      ]
    },
    {
      key: "qwen_local",
      label: "Qwen local (OpenAI-compat)",
      online: false,
      base_url: "http://127.0.0.1:8000/v1",
      models: ["Qwen2.5-7B-Instruct"]   # простой список когда нет rich метаданных
    },
    ...
  ]
  pull_queue: [                          # активные загрузки
    { name: "llama3.1:8b", status: "downloading", completed: 1234567, total: 9876543, pct: 12 }
  ]
  agents_by_model: {                     # модель → список агентов, которые на ней работают
    "qwen2.5:7b": [{ id: "...", name: "Chief", preset: "boss" }]
  }
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.ws_manager import ws_manager
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_compat import OpenAICompatProvider
from app.llm.registry import _build_registry

router = APIRouter(prefix="/api/models", tags=["models"])
ws_router = APIRouter()

# ── pull-queue state (in-memory, OK for single-process dev server) ──────────

_pull_queue: dict[str, dict] = {}   # name -> progress snapshot


# ── helpers ──────────────────────────────────────────────────────────────────

def _bytes_to_gb(n: int | None) -> float | None:
    if n is None:
        return None
    return round(n / 1024 / 1024 / 1024, 2)


async def _probe_openai_compat(provider: OpenAICompatProvider) -> dict:
    """Check connectivity and fetch model list from an OpenAI-compat endpoint."""
    try:
        models = await provider.list_models()
        return {
            "key": provider.name,
            "label": _label(provider.name),
            "online": True,
            "base_url": provider.base_url,
            "models": [{"name": m} for m in models],
        }
    except Exception as e:  # noqa: BLE001
        return {
            "key": provider.name,
            "label": _label(provider.name),
            "online": False,
            "base_url": provider.base_url,
            "error": str(e),
            "models": [],
        }


async def _probe_ollama(provider: OllamaProvider) -> dict:
    online = await provider.is_online()
    if not online:
        return {
            "key": "ollama",
            "label": "Ollama",
            "online": False,
            "base_url": provider.base_url,
            "error": "Ollama не отвечает. Запущен ли ollama serve?",
            "models": [],
            "running": [],
        }

    models_raw, running_raw = await asyncio.gather(
        provider.list_models_detail(),
        provider.running_models(),
    )

    running_names = {m.get("name") or m.get("model", "") for m in running_raw}

    models_out = []
    for m in models_raw:
        name = m.get("name", "")
        details = m.get("details") or {}
        models_out.append({
            "name": name,
            "size_gb": _bytes_to_gb(m.get("size")),
            "family": details.get("family"),
            "families": details.get("families"),
            "parameters": details.get("parameter_size"),
            "quantization": details.get("quantization_level"),
            "format": details.get("format"),
            "modified_at": m.get("modified_at"),
            "running": name in running_names,
        })

    running_out = []
    for m in running_raw:
        running_out.append({
            "name": m.get("name") or m.get("model", ""),
            "size_gb": _bytes_to_gb(m.get("size")),
            "vram_size_gb": _bytes_to_gb(m.get("size_vram")),
            "expires_at": m.get("expires_at"),
        })

    return {
        "key": "ollama",
        "label": "Ollama",
        "online": True,
        "base_url": provider.base_url,
        "models": models_out,
        "running": running_out,
    }


def _label(key: str) -> str:
    return {
        "ollama": "Ollama",
        "qwen_local": "Qwen local (OpenAI-compat)",
        "qwen_cloud": "Qwen cloud (DashScope)",
    }.get(key, key)


async def _agents_by_model() -> dict[str, list[dict]]:
    """Map model name → list of agents using it."""
    try:
        from app.agents.manager import list_agents  # noqa: PLC0415
        agents = await list_agents()
    except Exception:  # noqa: BLE001
        return {}

    out: dict[str, list[dict]] = {}
    for a in agents:
        model = a.get("llm_model") or ""
        if not model:
            # use provider default label
            model = f"(default {a.get('llm_provider', '')})"
        out.setdefault(model, []).append({
            "id": a["id"],
            "name": a["name"],
            "preset": a["preset"],
            "llm_provider": a["llm_provider"],
        })
    return out


async def _full_snapshot() -> dict:
    """Build the complete models snapshot."""
    reg = _build_registry()
    ollama_prov: OllamaProvider = reg["ollama"]
    qwen_local: OpenAICompatProvider = reg["qwen_local"]
    qwen_cloud: OpenAICompatProvider = reg["qwen_cloud"]

    providers_data, abm = await asyncio.gather(
        asyncio.gather(
            _probe_ollama(ollama_prov),
            _probe_openai_compat(qwen_local),
            _probe_openai_compat(qwen_cloud),
        ),
        _agents_by_model(),
    )

    # Attach agents_using to each model entry
    for prov in providers_data:
        for m in prov.get("models", []):
            name = m.get("name") if isinstance(m, dict) else m
            m["used_by_agents"] = abm.get(name, []) if isinstance(m, dict) else []

    pull_list = [
        {**v, "pct": round(v["completed"] / v["total"] * 100) if v.get("total") else 0}
        for v in _pull_queue.values()
        if v.get("status") not in ("success", "error")
    ]

    return {
        "ts": time.time(),
        "providers": list(providers_data),
        "pull_queue": pull_list,
        "agents_by_model": abm,
    }


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.get("")
async def models_snapshot():
    """Full snapshot of all local LLM providers and their models."""
    return await _full_snapshot()


@router.get("/ollama/info/{model_name:path}")
async def ollama_model_info(model_name: str):
    """Detailed info for one Ollama model (system prompt, modelfile, template, etc.)."""
    reg = _build_registry()
    prov: OllamaProvider = reg["ollama"]
    info = await prov.model_info(model_name)
    if "error" in info:
        raise HTTPException(status_code=502, detail=info["error"])
    return info


class PullRequest(BaseModel):
    name: str


@router.post("/ollama/pull")
async def ollama_pull(body: PullRequest):
    """Start pulling a model in the background. Progress visible via /ws/models."""
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "model name is empty")

    if name in _pull_queue and _pull_queue[name].get("status") not in ("success", "error", None):
        return {"ok": True, "status": "already_pulling", "name": name}

    _pull_queue[name] = {"name": name, "status": "starting", "completed": 0, "total": 0}

    async def _do_pull():
        reg = _build_registry()
        prov: OllamaProvider = reg["ollama"]
        try:
            async for progress in prov.pull_model(name):
                status = progress.get("status", "")
                completed = progress.get("completed", 0)
                total = progress.get("total", 0)
                _pull_queue[name] = {
                    "name": name,
                    "status": status,
                    "completed": completed or 0,
                    "total": total or 0,
                }
                # Broadcast progress immediately so the UI updates in real time
                await ws_manager.broadcast("models", {
                    "type": "pull_progress",
                    "name": name,
                    "status": status,
                    "completed": completed or 0,
                    "total": total or 0,
                    "pct": round(completed / total * 100) if total else 0,
                })
                if status == "success":
                    break
        except Exception as e:  # noqa: BLE001
            _pull_queue[name] = {"name": name, "status": "error", "error": str(e), "completed": 0, "total": 0}
            await ws_manager.broadcast("models", {
                "type": "pull_progress", "name": name, "status": "error", "error": str(e),
            })

    asyncio.create_task(_do_pull())
    return {"ok": True, "status": "started", "name": name}


class DeleteRequest(BaseModel):
    name: str


@router.delete("/ollama/{model_name:path}")
async def ollama_delete(model_name: str):
    """Delete an Ollama model from local storage."""
    reg = _build_registry()
    prov: OllamaProvider = reg["ollama"]
    try:
        return await prov.delete_model(model_name)
    except Exception as e:  # noqa: BLE001 — includes ConnectError when Ollama is offline
        raise HTTPException(status_code=502, detail=str(e))


# ── WebSocket — live updates every 8 s ────────────────────────────────────────

@ws_router.websocket("/ws/models")
async def ws_models(ws: WebSocket):
    await ws_manager.connect("models", ws)
    try:
        # Send initial snapshot immediately
        snap = await _full_snapshot()
        await ws.send_json({"type": "snapshot", **snap})
        while True:
            await asyncio.sleep(8)
            snap = await _full_snapshot()
            await ws.send_json({"type": "snapshot", **snap})
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect("models", ws)
