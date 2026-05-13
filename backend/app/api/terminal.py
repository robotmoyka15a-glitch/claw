"""WebSocket-backed PTY terminal. Protocol is tiny and xterm.js-friendly:

Client -> server messages (JSON):
    {"type": "input", "data": "ls\\n"}
    {"type": "resize", "cols": 120, "rows": 30}

Server -> client messages (JSON):
    {"type": "output", "data": "..."}
    {"type": "exit"}
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.terminal import PTYSession


ws_router = APIRouter()


@ws_router.websocket("/ws/terminal")
async def ws_terminal(ws: WebSocket):
    await ws.accept()
    session = PTYSession()
    try:
        session.start()
    except Exception as e:  # noqa: BLE001
        await ws.send_json({"type": "output", "data": f"[claw] terminal failed: {e}\r\n"})
        await ws.close()
        return

    async def on_output(data: str) -> None:
        try:
            await ws.send_json({"type": "output", "data": data})
        except Exception:
            pass

    await session.attach_output(on_output)

    try:
        while True:
            msg = await ws.receive_json()
            t = msg.get("type")
            if t == "input":
                session.write(msg.get("data", ""))
            elif t == "resize":
                session.resize(int(msg.get("cols", 120)), int(msg.get("rows", 30)))
    except WebSocketDisconnect:
        pass
    finally:
        session.close()
