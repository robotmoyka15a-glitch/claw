"""Process enumeration and control, built on psutil. Windows-friendly."""
from __future__ import annotations

from typing import Any

import psutil


_PROC_ATTRS = [
    "pid",
    "ppid",
    "name",
    "username",
    "status",
    "cpu_percent",
    "memory_info",
    "create_time",
    "num_threads",
    "exe",
]


def list_processes(sort_by: str = "cpu", limit: int = 200) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # First call to cpu_percent returns 0 — initialize with interval=None
    # but compare against previous sample. We accept this; repeated calls stabilize it.
    for p in psutil.process_iter(_PROC_ATTRS, ad_value=None):
        info = p.info
        mem = info.get("memory_info")
        rows.append(
            {
                "pid": info.get("pid"),
                "ppid": info.get("ppid"),
                "name": info.get("name") or "",
                "user": info.get("username") or "",
                "status": info.get("status") or "",
                "cpu": round(info.get("cpu_percent") or 0.0, 1),
                "rss_mb": round((mem.rss if mem else 0) / 1024 / 1024, 1),
                "threads": info.get("num_threads") or 0,
                "created": info.get("create_time") or 0,
                "exe": info.get("exe") or "",
            }
        )

    key = {
        "cpu": lambda r: -r["cpu"],
        "mem": lambda r: -r["rss_mb"],
        "pid": lambda r: r["pid"],
        "name": lambda r: (r["name"] or "").lower(),
    }.get(sort_by, lambda r: -r["cpu"])

    rows.sort(key=key)
    return rows[:limit]


def kill_process(pid: int, *, force: bool = False) -> dict[str, Any]:
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return {"ok": False, "error": "no-such-process"}
    try:
        if force:
            p.kill()
        else:
            p.terminate()
        return {"ok": True, "pid": pid}
    except psutil.AccessDenied:
        return {"ok": False, "error": "access-denied"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def process_detail(pid: int) -> dict[str, Any]:
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            return {
                "pid": p.pid,
                "ppid": p.ppid(),
                "name": p.name(),
                "exe": p.exe() if _safe(p.exe) else "",
                "cwd": _safe(p.cwd) or "",
                "cmdline": _safe(p.cmdline) or [],
                "status": p.status(),
                "username": _safe(p.username) or "",
                "created": p.create_time(),
                "num_threads": p.num_threads(),
                "cpu_percent": p.cpu_percent(interval=None),
                "memory_mb": round(p.memory_info().rss / 1024 / 1024, 1),
                "open_files": [f.path for f in (_safe(p.open_files) or [])][:50],
                "connections": [
                    {
                        "fd": c.fd,
                        "family": str(c.family),
                        "type": str(c.type),
                        "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
                        "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
                        "status": c.status,
                    }
                    # psutil 6.0: Process.connections() deprecated → net_connections()
                    for c in (_safe(p.net_connections) or [])
                ][:50],
            }
    except psutil.NoSuchProcess:
        return {"error": "no-such-process"}
    except psutil.AccessDenied:
        return {"error": "access-denied", "pid": pid}


def _safe(fn):
    try:
        return fn()
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return None
