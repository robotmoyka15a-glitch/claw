"""Third-party service connectors (Telegram, Discord, Steam, Spotify, Windows
notifications, ...).

Every connector is a small class living in its own file and exposing a few
async methods. Connectors read their credentials from the application settings
(via app.core.config.get_settings()); if credentials are missing the connector
is still importable but every call raises ConnectorError("not configured").

Each connector also registers a handful of Tool objects with the global tool
registry so agents can call them through LLM tool-calling. See
app.tools.registry.build_default_registry().
"""
from __future__ import annotations

from .base import ConnectorError  # noqa: F401


def register_connector_tools(reg) -> None:
    """Attach connector-provided tools to the given ToolRegistry instance."""
    # Import lazily so that a missing optional dep (e.g. pywin32 on Linux)
    # does not break startup — the connector itself handles the missing deps.
    from .telegram import TELEGRAM_TOOLS
    from .discord import DISCORD_TOOLS
    from .steam import STEAM_TOOLS
    from .spotify import SPOTIFY_TOOLS
    from .windows_notify import NOTIFY_TOOLS

    for t in (
        *TELEGRAM_TOOLS,
        *DISCORD_TOOLS,
        *STEAM_TOOLS,
        *SPOTIFY_TOOLS,
        *NOTIFY_TOOLS,
    ):
        reg.register(t)
