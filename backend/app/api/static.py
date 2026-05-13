"""Serve the built frontend (frontend/dist) from the backend process.

When claw runs in dev mode the frontend is served by Vite on port 5173 and
this module is effectively a no-op (no dist folder -> nothing to mount).

When claw runs as a packaged EXE the frontend/dist bundle is included as
a data directory next to the executable (via PyInstaller's --add-data), and
we mount it as the catch-all static root. The user opens http://127.0.0.1:8765
and gets the full UI from the same port as the API.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def _resource_dir() -> Path:
    """Directory containing bundled resources.

    PyInstaller puts data files into a folder pointed to by ``sys._MEIPASS``
    when it's a onefile build, and alongside the exe in onedir builds. If
    neither is set, fall back to the repo layout for ``python -m uvicorn``
    runs.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    # normal dev run: backend/app/api/static.py -> repo root
    return Path(__file__).resolve().parents[3]


def mount_frontend(app: FastAPI) -> bool:
    """Mount the built frontend at '/' if it exists. Returns True if mounted."""
    dist = _resource_dir() / "frontend" / "dist"
    if not dist.exists():
        # Check a second possible location (onedir build next to the exe).
        alt = Path(sys.argv[0]).resolve().parent / "frontend_dist"
        if alt.exists():
            dist = alt
        else:
            return False

    index = dist / "index.html"

    # Serve static files from /assets etc.
    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    # Anything else (including /) falls back to index.html. We register this
    # as a catch-all AFTER all /api and /ws routes, so API calls still win.
    @app.get("/{_full_path:path}", include_in_schema=False)
    async def _spa_index(_full_path: str):  # noqa: ANN001
        # API and WebSocket paths are handled earlier; this function only
        # runs when the request didn't match anything else. We still guard
        # against /api just in case a static mount order changes.
        if _full_path.startswith("api") or _full_path.startswith("ws"):
            return {"detail": "not found"}
        return FileResponse(index)

    return True
