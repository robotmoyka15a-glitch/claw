"""Built-in tools available to every agent (system, processes, terminal, vk, ...).

Every tool returns JSON-serialisable data or raises ToolError.
Dangerous tools (kill process, run shell) are marked with dangerous=True and
are disabled by default for agents except the ones that explicitly opt in.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from app.services import processes as proc_service
from app.services import system as sys_service
from app.services.vk_api import VKClient, VKError

from .base import Tool, ToolError


# ------------------------------- system ----------------------------------

async def _system_snapshot() -> dict[str, Any]:
    return sys_service.snapshot()


system_snapshot_tool = Tool(
    name="system.snapshot",
    description=(
        "Return one sample of system-wide metrics: CPU %, per-core CPU, RAM, "
        "swap, disk usage of the system drive, network throughput MB/s, "
        "uptime in seconds."
    ),
    parameters={"type": "object", "properties": {}},
    fn=_system_snapshot,
    category="system",
    tags=["system", "read-only"],
)


# ------------------------------- processes --------------------------------

async def _processes_list(sort_by: str = "cpu", limit: int = 50) -> list[dict]:
    return proc_service.list_processes(sort_by=sort_by, limit=limit)


async def _processes_detail(pid: int) -> dict:
    return proc_service.process_detail(int(pid))


async def _processes_kill(pid: int, force: bool = False) -> dict:
    res = proc_service.kill_process(int(pid), force=bool(force))
    if not res.get("ok"):
        raise ToolError(res.get("error") or "kill failed")
    return res


processes_list_tool = Tool(
    name="processes.list",
    description="List running processes. Sort by 'cpu', 'mem', 'pid' or 'name'.",
    parameters={
        "type": "object",
        "properties": {
            "sort_by": {"type": "string", "enum": ["cpu", "mem", "pid", "name"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
        },
    },
    fn=_processes_list,
    category="processes",
    tags=["system", "read-only"],
)

processes_detail_tool = Tool(
    name="processes.detail",
    description="Return detailed info for one process (cmdline, cwd, open files, connections).",
    parameters={
        "type": "object",
        "required": ["pid"],
        "properties": {"pid": {"type": "integer"}},
    },
    fn=_processes_detail,
    category="processes",
    tags=["system", "read-only"],
)

processes_kill_tool = Tool(
    name="processes.kill",
    description=(
        "Terminate a process by PID. Use force=true to send SIGKILL/TerminateProcess. "
        "Ask the user for confirmation before calling this."
    ),
    parameters={
        "type": "object",
        "required": ["pid"],
        "properties": {
            "pid": {"type": "integer"},
            "force": {"type": "boolean"},
        },
    },
    fn=_processes_kill,
    category="processes",
    dangerous=True,
    tags=["system", "destructive"],
)


# ------------------------------- VK --------------------------------------

async def _vk_me() -> dict:
    client = VKClient()
    try:
        return await client.me()
    except VKError as e:
        raise ToolError(str(e)) from e
    finally:
        await client.close()


async def _vk_friends_online() -> dict:
    client = VKClient()
    try:
        return await client.friends_online()
    except VKError as e:
        raise ToolError(str(e)) from e
    finally:
        await client.close()


async def _vk_newsfeed(count: int = 20) -> dict:
    client = VKClient()
    try:
        return await client.newsfeed(count=int(count))
    except VKError as e:
        raise ToolError(str(e)) from e
    finally:
        await client.close()


vk_me_tool = Tool(
    name="vk.me",
    description="Get the current VK user's profile (photo, city, status, counters).",
    parameters={"type": "object", "properties": {}},
    fn=_vk_me,
    category="vk",
    tags=["social", "read-only"],
)

vk_friends_online_tool = Tool(
    name="vk.friends_online",
    description="List VK friends that are currently online.",
    parameters={"type": "object", "properties": {}},
    fn=_vk_friends_online,
    category="vk",
    tags=["social", "read-only"],
)

vk_newsfeed_tool = Tool(
    name="vk.newsfeed",
    description="Return the latest VK newsfeed posts (default 20).",
    parameters={
        "type": "object",
        "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 100}},
    },
    fn=_vk_newsfeed,
    category="vk",
    tags=["social", "read-only"],
)


async def _vk_search(query: str, count: int = 20) -> dict:
    client = VKClient()
    try:
        return await client.newsfeed_search(query=query, count=int(count))
    except VKError as e:
        raise ToolError(str(e)) from e
    finally:
        await client.close()


async def _vk_send_message(user_id: int, message: str) -> dict:
    client = VKClient()
    try:
        msg_id = await client.send_message(int(user_id), message)
        return {"ok": True, "message_id": msg_id}
    except VKError as e:
        raise ToolError(str(e)) from e
    finally:
        await client.close()


async def _vk_like(owner_id: int, item_id: int, item_type: str = "post") -> dict:
    client = VKClient()
    try:
        return await client.like(int(owner_id), int(item_id), item_type)
    except VKError as e:
        raise ToolError(str(e)) from e
    finally:
        await client.close()


vk_search_tool = Tool(
    name="vk.search",
    description="Search public VK posts by keyword. Returns posts matching the query.",
    parameters={
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "count": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    },
    fn=_vk_search,
    category="vk",
    tags=["social", "read-only"],
)

vk_send_message_tool = Tool(
    name="vk.send_message",
    description=(
        "Send a private message to a VK user by their numeric user_id. "
        "Requires the token to have 'messages' scope. Always confirm with the user first."
    ),
    parameters={
        "type": "object",
        "required": ["user_id", "message"],
        "properties": {
            "user_id": {"type": "integer", "description": "Numeric VK user id"},
            "message": {"type": "string"},
        },
    },
    fn=_vk_send_message,
    category="vk",
    dangerous=True,
    tags=["social", "write"],
)

vk_like_tool = Tool(
    name="vk.like",
    description="Add a like to a VK post/photo/video. item_type: post | photo | video.",
    parameters={
        "type": "object",
        "required": ["owner_id", "item_id"],
        "properties": {
            "owner_id": {"type": "integer"},
            "item_id": {"type": "integer"},
            "item_type": {"type": "string", "enum": ["post", "photo", "video", "comment"]},
        },
    },
    fn=_vk_like,
    category="vk",
    tags=["social", "write"],
)


# ------------------------------- terminal.exec ---------------------------
#
# Safe one-shot shell execution. Not to be confused with the interactive PTY
# terminal (that one is used by the human via xterm.js). This tool lets an
# agent run a command, capture stdout/stderr, and optionally time out.

# Commands/paths that look obviously destructive. Refusal is advisory: the
# user can always run the command themselves from the interactive terminal.
_DENYLIST_TOKENS = (
    "rm -rf /",
    "mkfs",
    "format c:",
    "del /f /s /q c:\\",
    ":(){:|:&};:",
    "shutdown",
    "reboot",
    "diskpart",
)


async def _terminal_exec(command: str, timeout: float = 20.0) -> dict:
    cmd = (command or "").strip()
    if not cmd:
        raise ToolError("command is empty")
    low = cmd.lower()
    for bad in _DENYLIST_TOKENS:
        if bad in low:
            raise ToolError(f"refused: command looks destructive ({bad!r})")

    # FIX #3: не оборачивать команду в двойную оболочку на Linux.
    # create_subprocess_shell уже использует /bin/sh -c, поэтому
    # передаём команду как есть на всех платформах.
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=float(timeout)
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise ToolError(f"timed out after {timeout}s")
    except FileNotFoundError as e:
        raise ToolError(str(e)) from e

    stdout = (stdout_b or b"").decode("utf-8", errors="replace")
    stderr = (stderr_b or b"").decode("utf-8", errors="replace")

    # Truncate very long output so the LLM doesn't drown.
    def _trim(s: str, limit: int = 4000) -> str:
        return s if len(s) <= limit else s[:limit] + f"\n…[truncated {len(s) - limit} chars]"

    return {
        "exit_code": proc.returncode,
        "stdout": _trim(stdout),
        "stderr": _trim(stderr),
        "cwd": os.getcwd(),
    }


terminal_exec_tool = Tool(
    name="terminal.exec",
    description=(
        "Execute a single shell command and return stdout, stderr and exit code. "
        "Commands time out after the given number of seconds. "
        "Blocks a handful of obviously destructive patterns, but still — think "
        "before running and ask the user for confirmation when in doubt."
    ),
    parameters={
        "type": "object",
        "required": ["command"],
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "number", "minimum": 1, "maximum": 120},
        },
    },
    fn=_terminal_exec,
    category="terminal",
    dangerous=True,
    tags=["shell", "destructive"],
)
