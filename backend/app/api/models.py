"""REST + WebSocket API for LLM model management.

Endpoints:
  GET  /api/models                       — snapshot of all providers + models
  GET  /api/models/ollama/info/{name}    — detailed Ollama model info
  POST /api/models/ollama/pull           — pull a model via Ollama
  DELETE /api/models/ollama/{name}       — delete an Ollama model
  WS   /ws/models                        — live push of model list changes
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.ws_manager import ws_manager
from app.llm.registry import list_providers, get_provider

logger = logging.getLogger("claw.api.models")

router = APIRouter(prefix="/api/models", tags=["models"])
ws_router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

async def _build_snapshot() -> list[dict]:
    out: list[dict] = []
    for key in list_providers():
        prov = get_provider(key)
        try:
            models = await prov.list_models()
            error = None
        except Exception as exc:  # noqa: BLE001
            models = []
            error = str(exc)
        out.append(
            {
                "key": key,
                "default_model": prov.default_model,
                "models": models,
                "error": error,
            }
        )
    return out


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.get("")
async def models_snapshot():
    """Return a snapshot of all configured LLM providers and their model lists."""
    return await _build_snapshot()


@router.get("/ollama/info/{name:path}")
async def ollama_model_info(name: str):
    """Return detailed info for a named Ollama model."""
    from app.llm.registry import get_provider  # noqa: PLC0415

    prov = get_provider("ollama")
    try:
        # OllamaProvider exposes list_models; detailed info via raw HTTP
        from app.core.http_pool import get_client  # noqa: PLC0415
        from app.core.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        base = settings.ollama_base_url.rstrip("/")
        client = await get_client()
        r = await client.post(f"{base}/api/show", json={"name": name})
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class PullRequest(BaseModel):
    name: str


@router.post("/ollama/pull")
async def ollama_pull(body: PullRequest):
    """Trigger an Ollama model pull (non-streaming, returns when done)."""
    try:
        from app.core.http_pool import get_client  # noqa: PLC0415
        from app.core.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        base = settings.ollama_base_url.rstrip("/")
        client = await get_client()
        r = await client.post(
            f"{base}/api/pull",
            json={"name": body.name, "stream": False},
            timeout=600,
        )
        r.raise_for_status()
        return {"ok": True, "name": body.name}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/ollama/{name:path}")
async def ollama_delete(name: str):
    """Delete an Ollama model."""
    try:
        from app.core.http_pool import get_client  # noqa: PLC0415
        from app.core.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        base = settings.ollama_base_url.rstrip("/")
        client = await get_client()
        r = await client.request("DELETE", f"{base}/api/delete", json={"name": name})
        r.raise_for_status()
        return {"ok": True, "name": name}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── WebSocket ─────────────────────────────────────────────────────────────────

@ws_router.websocket("/ws/models")
async def ws_models(ws: WebSocket):
    """Push model snapshot to frontend on connect, then stay alive for updates."""
    await ws_manager.connect("models", ws)
    try:
        snapshot = await _build_snapshot()
        await ws.send_json({"type": "snapshot", "providers": snapshot})
        while True:
            # Keep connection alive; refreshes are pushed by background tasks
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect("models", ws)
