"""Settings API — read and write the runtime .env file from the browser UI.

Security model:
  * Binds to 127.0.0.1 only (same as the whole backend).
  * Reads/writes the file pointed to by CLAW_ENV_FILE (defaults to
    backend/.env).  The file is never sent to any third party.
  * Sensitive values (tokens, keys) are masked on GET so they're never
    exposed in full to the browser — only presence is shown.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── helpers ─────────────────────────────────────────────────────────────────

# Keys whose values should be masked (show only first 4 chars + ***).
_SENSITIVE = {
    "VK_ACCESS_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "DISCORD_BOT_TOKEN",
    "STEAM_API_KEY",
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "SPOTIFY_REFRESH_TOKEN",
    "QWEN_CLOUD_API_KEY",
    "QWEN_LOCAL_API_KEY",
}


def _env_path() -> Path:
    """Return the path to the active .env file."""
    explicit = os.environ.get("CLAW_ENV_FILE")
    if explicit:
        return Path(explicit)
    # dev mode: backend/.env next to this file's package root
    return Path(__file__).resolve().parents[2] / ".env"


def _parse_env(text: str) -> dict[str, str]:
    """Parse KEY=VALUE pairs from an env file (comments and blanks ignored)."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        result[key.strip()] = val.strip()
    return result


def _mask(key: str, value: str) -> str:
    if key not in _SENSITIVE or not value:
        return value
    return value[:4] + "***" if len(value) > 4 else "***"


def _write_env(path: Path, updates: dict[str, str]) -> None:
    """Apply updates to the env file, preserving comments and order."""
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    written: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            written.add(key)
        else:
            new_lines.append(line)

    # Append keys that weren't in the file yet.
    for key, val in updates.items():
        if key not in written:
            new_lines.append(f"{key}={val}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# ── schema ───────────────────────────────────────────────────────────────────

class SettingEntry(BaseModel):
    key: str
    value: str          # masked for sensitive keys on GET
    masked: bool        # true means the real value was replaced with ***
    comment: str = ""   # human-readable hint shown in the UI


class SettingUpdate(BaseModel):
    updates: Dict[str, str]


# Metadata for the settings panel: label, description, sensitive flag.
_METADATA: list[dict] = [
    # LLM
    {"key": "OLLAMA_BASE_URL",            "label": "Ollama URL",                 "group": "LLM",      "sensitive": False, "hint": "Адрес локального Ollama, например http://127.0.0.1:11434"},
    {"key": "OLLAMA_DEFAULT_MODEL",       "label": "Ollama модель",              "group": "LLM",      "sensitive": False, "hint": "Модель по умолчанию, например qwen2.5:7b"},
    {"key": "QWEN_LOCAL_BASE_URL",        "label": "Qwen local URL",             "group": "LLM",      "sensitive": False, "hint": "OpenAI-совместимый эндпоинт, например http://127.0.0.1:8000/v1"},
    {"key": "QWEN_LOCAL_DEFAULT_MODEL",   "label": "Qwen local модель",          "group": "LLM",      "sensitive": False, "hint": "Например Qwen2.5-7B-Instruct"},
    {"key": "QWEN_CLOUD_API_KEY",         "label": "Qwen cloud API Key",         "group": "LLM",      "sensitive": True,  "hint": "DashScope API ключ (sk-…)"},
    {"key": "QWEN_CLOUD_DEFAULT_MODEL",   "label": "Qwen cloud модель",          "group": "LLM",      "sensitive": False, "hint": "Например qwen-plus, qwen-max"},
    # VK
    {"key": "VK_ACCESS_TOKEN",            "label": "VK Access Token",            "group": "VK",       "sensitive": True,  "hint": "Токен пользователя ВКонтакте (Implicit Flow, scope=friends,wall,offline)"},
    # Telegram
    {"key": "TELEGRAM_BOT_TOKEN",         "label": "Telegram Bot Token",         "group": "Telegram", "sensitive": True,  "hint": "Токен от @BotFather, вида 123456789:AAA…"},
    {"key": "TELEGRAM_DEFAULT_CHAT_ID",   "label": "Telegram Chat ID",           "group": "Telegram", "sensitive": False, "hint": "Числовой id чата куда бот по умолчанию пишет"},
    # Discord
    {"key": "DISCORD_BOT_TOKEN",          "label": "Discord Bot Token",          "group": "Discord",  "sensitive": True,  "hint": "Токен бота из Discord Developer Portal"},
    {"key": "DISCORD_DEFAULT_CHANNEL_ID", "label": "Discord Channel ID",         "group": "Discord",  "sensitive": False, "hint": "Числовой id канала по умолчанию"},
    # Steam
    {"key": "STEAM_API_KEY",              "label": "Steam API Key",              "group": "Steam",    "sensitive": True,  "hint": "Ключ с https://steamcommunity.com/dev/apikey"},
    {"key": "STEAM_USER_ID",              "label": "Steam User ID (SteamID64)",  "group": "Steam",    "sensitive": False, "hint": "17-значный SteamID64 (например 76561198…)"},
    # Spotify
    {"key": "SPOTIFY_CLIENT_ID",          "label": "Spotify Client ID",          "group": "Spotify",  "sensitive": True,  "hint": "Client ID из Spotify Developer Dashboard"},
    {"key": "SPOTIFY_CLIENT_SECRET",      "label": "Spotify Client Secret",      "group": "Spotify",  "sensitive": True,  "hint": "Client Secret из Spotify Developer Dashboard"},
    {"key": "SPOTIFY_REFRESH_TOKEN",      "label": "Spotify Refresh Token",      "group": "Spotify",  "sensitive": True,  "hint": "Refresh token (Authorization Code flow, scope=user-read-currently-playing…)"},
]

_META_BY_KEY = {m["key"]: m for m in _METADATA}


# ── endpoints ────────────────────────────────────────────────────────────────

@router.get("")
async def get_settings() -> list[dict]:
    """Return all configurable settings with current values (masked where sensitive)."""
    env_path = _env_path()
    current: dict[str, str] = {}
    if env_path.exists():
        current = _parse_env(env_path.read_text(encoding="utf-8"))

    rows = []
    for meta in _METADATA:
        key = meta["key"]
        raw = current.get(key, "")
        is_sensitive: bool = meta["sensitive"]
        rows.append({
            "key": key,
            "value": _mask(key, raw) if is_sensitive else raw,
            "masked": is_sensitive and bool(raw),
            "configured": bool(raw),
            "label": meta["label"],
            "group": meta["group"],
            "hint": meta["hint"],
            "sensitive": is_sensitive,
        })
    return rows


@router.post("")
async def update_settings(body: SettingUpdate) -> dict:
    """Write one or more settings to the .env file.

    Rules:
      * Masked values (containing '***') are silently ignored — we never
        overwrite a real token with a display placeholder.
      * Reloads the application settings cache after writing so changes take
        effect immediately without a restart.
    """
    env_path = _env_path()
    safe_updates: dict[str, str] = {}

    for key, value in body.updates.items():
        # Skip if this looks like a masked placeholder sent back from the UI.
        if "***" in value:
            continue
        # Only allow keys we know about (whitelist).
        if key not in _META_BY_KEY and not key.startswith("CLAW_") and not key.startswith("OLLAMA_") and not key.startswith("QWEN_"):
            continue
        safe_updates[key] = value.strip()

    if not safe_updates:
        return {"ok": True, "updated": 0}

    _write_env(env_path, safe_updates)

    # Invalidate the settings cache so new values are read on next access.
    try:
        from app.core.config import get_settings  # noqa: PLC0415
        get_settings.cache_clear()
    except Exception:  # noqa: BLE001
        pass

    return {"ok": True, "updated": len(safe_updates), "keys": list(safe_updates)}


@router.get("/env-path")
async def env_path_info() -> dict:
    """Return the path to the active .env file (useful for 'open in editor')."""
    p = _env_path()
    return {"path": str(p), "exists": p.exists()}
