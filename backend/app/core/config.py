"""Runtime configuration, loaded from backend/.env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- server ---
    claw_host: str = "127.0.0.1"
    claw_port: int = 8765
    claw_cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # --- VK ---
    vk_access_token: str = ""
    vk_api_version: str = "5.199"

    # --- Ollama ---
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_default_model: str = "qwen2.5:7b"

    # --- Qwen local (OpenAI-compatible) ---
    qwen_local_base_url: str = "http://127.0.0.1:8000/v1"
    qwen_local_api_key: str = "not-needed"
    qwen_local_default_model: str = "Qwen2.5-7B-Instruct"

    # --- Qwen cloud (DashScope OpenAI-compatible) ---
    qwen_cloud_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_cloud_api_key: str = ""
    qwen_cloud_default_model: str = "qwen-plus"

    # --- Telegram (Bot API) ---
    # Create a bot via @BotFather, paste the token. For read-only monitoring of
    # a private chat you can set the numeric chat id to fetch updates from.
    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""

    # --- Discord (Bot) ---
    # Create a bot application, copy the token from "Bot" tab. Claw uses the
    # REST API only — no gateway websocket — so no intents setup is required.
    discord_bot_token: str = ""
    discord_default_channel_id: str = ""

    # --- Steam Web API ---
    # Register a key at https://steamcommunity.com/dev/apikey
    steam_api_key: str = ""
    steam_user_id: str = ""  # SteamID64

    # --- Spotify (Client Credentials + optional Authorization Code) ---
    # For now-playing / playback control you need a user access token obtained
    # via the Authorization Code flow. Store the refresh token here and claw
    # will refresh it automatically.
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_refresh_token: str = ""

    # --- storage ---
    claw_db_path: str = "data/claw.sqlite"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.claw_cors_origins.split(",") if o.strip()]

    @property
    def db_absolute_path(self) -> Path:
        p = Path(self.claw_db_path)
        return p if p.is_absolute() else BACKEND_ROOT / p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
