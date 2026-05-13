"""Standalone launcher — the entry point used when claw is packaged as an EXE.

Responsibilities:
    * Decide which folder is ``writable`` (for claw.sqlite and logs) — for a
      packaged binary we can't write next to the .exe if it lives under
      "C:\\Program Files\\", so we default to %LOCALAPPDATA%\\claw.
    * Create a default .env on first run so the user has something to edit.
    * Start uvicorn on 127.0.0.1:8765 in a background thread.
    * Wait until the server responds, then open the browser.
    * Show a simple Windows tray icon with 'Open claw' and 'Quit' menu items
      (if pystray + pillow are available — they're declared as optional deps).
    * Keep the process alive until the tray 'Quit' is clicked (or Ctrl+C).

On non-Windows or if pystray is missing, we fall back to a plain "press Ctrl+C
to exit" loop so the launcher still works for development.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


LOG = logging.getLogger("claw.launcher")
HOST = os.environ.get("CLAW_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLAW_PORT", "8765"))
BROWSER_URL = f"http://{HOST}:{PORT}/"


# --------------------------------------------------------------------------
# writable data dir
# --------------------------------------------------------------------------

def _writable_data_dir() -> Path:
    """Return a directory where we can freely create claw.sqlite and logs."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "claw"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "claw"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "claw"


def _prepare_env() -> Path:
    data_dir = _writable_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    env_path = data_dir / ".env"
    if not env_path.exists():
        template = _bundled_env_template()
        if template and template.exists():
            env_path.write_bytes(template.read_bytes())
        else:
            env_path.write_text(
                "# claw settings — вставь свои токены сюда и перезапусти claw\n"
                "VK_ACCESS_TOKEN=\n"
                "TELEGRAM_BOT_TOKEN=\n"
                "TELEGRAM_DEFAULT_CHAT_ID=\n"
                "DISCORD_BOT_TOKEN=\n"
                "DISCORD_DEFAULT_CHANNEL_ID=\n"
                "STEAM_API_KEY=\n"
                "STEAM_USER_ID=\n"
                "SPOTIFY_CLIENT_ID=\n"
                "SPOTIFY_CLIENT_SECRET=\n"
                "SPOTIFY_REFRESH_TOKEN=\n"
                "OLLAMA_BASE_URL=http://127.0.0.1:11434\n"
                "OLLAMA_DEFAULT_MODEL=qwen2.5:7b\n"
                "QWEN_LOCAL_BASE_URL=http://127.0.0.1:8000/v1\n"
                "QWEN_LOCAL_DEFAULT_MODEL=Qwen2.5-7B-Instruct\n"
                "QWEN_CLOUD_API_KEY=\n"
                "QWEN_CLOUD_DEFAULT_MODEL=qwen-plus\n",
                encoding="utf-8",
            )

    # Point pydantic-settings at this env file before importing app modules.
    os.environ.setdefault("CLAW_ENV_FILE", str(env_path))
    os.environ.setdefault("CLAW_DB_PATH", str(data_dir / "claw.sqlite"))
    return data_dir


def _bundled_env_template() -> Path | None:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / ".env.example"
    here = Path(__file__).resolve().parent
    return here / ".env.example"


# --------------------------------------------------------------------------
# server + browser
# --------------------------------------------------------------------------

def _run_server() -> None:
    import uvicorn
    from app.main import app  # noqa: PLC0415

    uvicorn.run(app, host=HOST, port=PORT, log_level="warning", access_log=False)


def _wait_for_server(timeout: float = 30.0) -> bool:
    import httpx  # noqa: PLC0415

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BROWSER_URL}api/health", timeout=1.5)
            if r.status_code == 200:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    return False


# --------------------------------------------------------------------------
# tray icon (optional — requires pystray + Pillow in the environment)
# --------------------------------------------------------------------------

def _build_tray_icon():
    """Create and return a pystray.Icon, or None if pystray/Pillow unavailable."""
    try:
        import pystray                              # type: ignore[import-not-found]
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return None

    # Generate icon programmatically — yellow circle with black "C" letter.
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, size - 3, size - 3), fill=(245, 179, 1, 255))
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    d.text((size // 2, size // 2), "C", fill=(10, 13, 20, 255), font=font, anchor="mm")

    stop_event = threading.Event()

    def on_open(_icon, _item):  # noqa: ANN001
        webbrowser.open(BROWSER_URL)

    def on_quit(icon, _item):  # noqa: ANN001
        stop_event.set()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Открыть claw", on_open, default=True),
        pystray.MenuItem("Настройки (открыть .env)", lambda *_: _open_env_file()),
        pystray.MenuItem("Выход", on_quit),
    )
    icon = pystray.Icon("claw", img, "claw — рабочая комната", menu)
    return icon, stop_event


def _open_env_file() -> None:
    env = os.environ.get("CLAW_ENV_FILE")
    if not env:
        return
    if sys.platform == "win32":
        os.startfile(env)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f"open {env!r}")
    else:
        os.system(f"xdg-open {env!r}")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    data_dir = _prepare_env()
    LOG.info("claw data dir: %s", data_dir)
    LOG.info("starting backend on %s:%d …", HOST, PORT)

    server_thread = threading.Thread(target=_run_server, daemon=True, name="claw-api")
    server_thread.start()

    ok = _wait_for_server()
    if ok:
        LOG.info("backend ready — opening %s", BROWSER_URL)
        try:
            webbrowser.open(BROWSER_URL)
        except Exception:  # noqa: BLE001
            pass
    else:
        LOG.error(
            "backend did not start within 30 s. "
            "Check if port %d is already in use.", PORT
        )

    # Try to show a system-tray icon (Windows only in practice).
    result = _build_tray_icon() if sys.platform == "win32" else None
    if result is not None:
        icon, stop_event = result
        icon.run()          # blocks until user clicks "Выход"
    else:
        # Fallback: plain blocking loop so the daemon server thread stays alive.
        LOG.info("running without tray icon — press Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    LOG.info("claw shutting down")


if __name__ == "__main__":
    main()
