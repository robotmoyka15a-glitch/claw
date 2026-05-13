from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.agents import manager, presets
from app.core.ws_manager import ws_manager
from app.llm import get_provider, list_providers

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: Optional[str] = None
    preset: str = "researcher"
    desk: Optional[str] = None
    color: Optional[str] = None
    llm_provider: str = "ollama"
    llm_model: str = ""
    system_prompt: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    allowed_tools: Optional[List[str]] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    desk: Optional[str] = None
    color: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    allowed_tools: Optional[List[str]] = None


@router.get("/presets")
async def get_presets():
    return presets.list_presets()


@router.get("/providers")
async def get_providers():
    out: list[dict] = []
    for key in list_providers():
        prov = get_provider(key)
        try:
            models = await prov.list_models()
        except Exception as e:  # noqa: BLE001
            models = []
            error = str(e)
        else:
            error = None
        out.append(
            {
                "key": key,
                "default_model": prov.default_model,
                "models": models,
                "error": error,
            }
        )
    return out


@router.get("")
async def list_agents():
    return await manager.list_agents()


@router.post("")
async def create_agent(data: AgentCreate):
    return await manager.create_agent(data.model_dump())


@router.get("/states")
async def agent_states():
    return manager.current_states()


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    a = await manager.get_agent(agent_id)
    if not a:
        raise HTTPException(status_code=404, detail="agent not found")
    return a


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, patch: AgentUpdate):
    a = await manager.update_agent(agent_id, patch.model_dump(exclude_none=True))
    if not a:
        raise HTTPException(status_code=404, detail="agent not found")
    return a


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    ok = await manager.delete_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="agent not found")
    return {"ok": True}


@router.get("/{agent_id}/messages")
async def messages(agent_id: str, limit: int = 200):
    return await manager.list_messages(agent_id, limit=limit)


# ------- chat via WebSocket (streamed with tool events) -------

ws_router = APIRouter()


@ws_router.websocket("/ws/agents/{agent_id}")
async def ws_agent_chat(ws: WebSocket, agent_id: str):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if payload.get("type") != "user":
                continue
            text = (payload.get("text") or "").strip()
            if not text:
                continue
            await ws.send_json({"type": "start"})
            try:
                async for event in manager.stream_events(agent_id, text):
                    await ws.send_json(event)
            except Exception as e:  # noqa: BLE001
                await ws.send_json({"type": "error", "error": str(e)})
    except WebSocketDisconnect:
        return


@ws_router.websocket("/ws/agents-state")
async def ws_agents_state(ws: WebSocket):
    """Global agent-state stream. Receives status updates for every agent,
    regardless of whether its chat panel is open. Used by the room scene to
    animate avatars.
    """
    await ws_manager.connect("agents-state", ws)
    # Send initial snapshot.
    try:
        await ws.send_json({"type": "snapshot", "agents": manager.current_states()})
        while True:
            # Keep the connection alive; we don't expect client messages.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect("agents-state", ws)
