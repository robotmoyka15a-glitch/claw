"""Wire up every built-in and connector tool into one registry instance."""
from __future__ import annotations

from functools import lru_cache

from .base import ToolRegistry
from .builtins import (
    processes_detail_tool,
    processes_kill_tool,
    processes_list_tool,
    system_snapshot_tool,
    terminal_exec_tool,
    vk_friends_online_tool,
    vk_like_tool,
    vk_me_tool,
    vk_newsfeed_tool,
    vk_search_tool,
    vk_send_message_tool,
)
from .delegation import delegate_to_agent_tool


@lru_cache(maxsize=1)
def build_default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    # system + processes
    reg.register(system_snapshot_tool)
    reg.register(processes_list_tool)
    reg.register(processes_detail_tool)
    reg.register(processes_kill_tool)
    # vk
    reg.register(vk_me_tool)
    reg.register(vk_friends_online_tool)
    reg.register(vk_newsfeed_tool)
    reg.register(vk_search_tool)
    reg.register(vk_send_message_tool)
    reg.register(vk_like_tool)
    # shell
    reg.register(terminal_exec_tool)
    # coordination
    reg.register(delegate_to_agent_tool)

    # Connector tools — register lazily to avoid pulling in optional deps for
    # users who don't use them.
    from app.connectors import register_connector_tools

    register_connector_tools(reg)

    return reg
