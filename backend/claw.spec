# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for claw — produces a single Windows EXE.
#
# HOW TO BUILD:
#   cd backend
#   pip install -r requirements.txt      # includes pyinstaller
#   # build the frontend first:
#   cd ../frontend && npm install && npm run build && cd ../backend
#   pyinstaller claw.spec
#   # Output: backend/dist/claw.exe
#
# The EXE bundles:
#   * the entire Python environment (FastAPI, uvicorn, psutil, …)
#   * frontend/dist (the compiled React app, served by the backend on :8765)
#   * .env.example as a template for first-run configuration
#
import os
import sys
from pathlib import Path

HERE = Path(SPECPATH)               # backend/
REPO = HERE.parent                  # repo root
FRONTEND_DIST = REPO / "frontend" / "dist"

# Validate that the frontend was built before running PyInstaller.
if not FRONTEND_DIST.exists():
    raise SystemExit(
        "\n[claw.spec] frontend/dist not found!\n"
        "Run: cd ../frontend && npm run build\n"
        "then re-run pyinstaller from the backend directory.\n"
    )

# Collect all files from frontend/dist preserving directory structure.
def _collect_frontend():
    datas = []
    for root, dirs, files in os.walk(FRONTEND_DIST):
        # Skip hidden dirs like .vite
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(os.path.dirname(src), REPO)
            datas.append((src, rel))
    return datas


a = Analysis(
    ['launcher.py'],
    pathex=[str(HERE)],
    binaries=[],
    datas=[
        # Frontend bundle
        *_collect_frontend(),
        # .env template for first-run
        (str(HERE / '.env.example'), '.'),
    ],
    hiddenimports=[
        # uvicorn internals PyInstaller may miss
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # FastAPI / Starlette
        'starlette.routing',
        'starlette.staticfiles',
        'starlette.responses',
        # aiosqlite uses importlib.metadata
        'aiosqlite',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.aiosqlite',
        # pydantic v2
        'pydantic.deprecated.class_validators',
        'pydantic_settings',
        # psutil
        'psutil._pswindows',
        # pywinpty
        'winpty',
        # app modules (make sure all subpackages are picked up)
        'app',
        'app.main',
        'app.core',
        'app.api',
        'app.agents',
        'app.llm',
        'app.tools',
        'app.connectors',
        'app.services',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # dev / test packages we don't need at runtime
        'pytest', 'hypothesis', 'black', 'mypy', 'ruff',
        'tkinter', 'matplotlib', 'numpy', 'pandas',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='claw',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # compress with UPX if available (smaller EXE)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # no console window; launcher uses the tray icon
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Give it a nice icon if claw.ico exists next to the spec
    icon=str(HERE / 'claw.ico') if (HERE / 'claw.ico').exists() else None,
    version='version_info.txt' if (HERE / 'version_info.txt').exists() else None,
)
