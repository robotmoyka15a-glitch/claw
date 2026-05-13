"""Process enumeration and control, built on psutil. Windows-friendly.

Changes vs original:
  * diff_processes() — returns only added/removed/changed rows compared to
    the previous scan, so the WebSocket can send small delta packets instead
    of the full list every 2 s.
  * Cached scan with configurable interval (default 1.5 s).
  * net_connections() instead of deprecated connections().
"""
from __future__ import annotations

import time
from typing import Any

import psutil


_PROC_ATTRS = [
    "pid", "ppid", "name", "username", "status",
    "cpu_percent", "memory_info", "create_time", "num_threads", "exe",
]

# ── internal scan cache ───────────────────────────────────────────────────────

_last_scan: dict[int, dict[str, Any]] = {}    # pid → row
_last_scan_ts: float = 0.0
_SCAN_TTL: float = 1.5   # seconds


def _row(info: dict) -> dict[str, Any]:
    mem = info.get("memory_info")
    return {
        "pid":     info.get("pid"),
        "ppid":    info.get("ppid"),
        "name":    info.get("name") or "",
        "user":    info.get("username") or "",
        "status":  info.get("status") or "",
        "cpu":     round(info.get("cpu_percent") or 0.0, 1),
        "rss_mb":  round((mem.rss if mem else 0) / 1024 / 1024, 1),
        "threads": info.get("num_threads") or 0,
        "created": info.get("create_time") or 0,
        "exe":     info.get("exe") or "",
    }


def _full_scan() -> dict[int, dict[str, Any]]:
    global _last_scan, _last_scan_ts
    now = time.monotonic()
    if now - _last_scan_ts < _SCAN_TTL and _last_scan:
        return _last_scan
    rows: dict[int, dict[str, Any]] = {}
    for p in psutil.process_iter(_PROC_ATTRS, ad_value=None):
        r = _row(p.info)
        if r["pid"] is not None:
            rows[r["pid"]] = r
    _last_scan = rows
    _last_scan_ts = now
    return rows


# ── public API ─────────────────────────────────────────────────────────────────

def list_processes(sort_by: str = "cpu", limit: int = 200) -> list[dict[str, Any]]:
    rows = list(_full_scan().values())
    key = {
        "cpu":  lambda r: -r["cpu"],
        "mem":  lambda r: -r["rss_mb"],
        "pid":  lambda r: r["pid"],
        "name": lambda r: (r["name"] or "").lower(),
    }.get(sort_by, lambda r: -r["cpu"])
    rows.sort(key=key)
    return rows[:limit]


_prev_pids: set[int] = set()


def diff_processes(limit: int = 150) -> dict[str, Any]:
    """Return a compact delta suitable for WebSocket streaming.

    Returns:
        {
          "added":   [row, ...],    # new PIDs since last call
          "removed": [pid, ...],    # PIDs that exited
          "changed": [row, ...],    # rows where cpu or rss changed notably
          "top":     [row, ...],    # top-N by CPU for the full table refresh
        }
    """
    global _prev_pids
    current = _full_scan()
    cur_pids = set(current)

    added   = [current[p] for p in cur_pids - _prev_pids]
    removed = list(_prev_pids - cur_pids)
    changed = [
        r for pid, r in current.items()
        if pid in _prev_pids and r["cpu"] > 0.5
    ]

    _prev_pids = cur_pids

    top = sorted(current.values(), key=lambda r: -r["cpu"])[:limit]
    return {"added": added, "removed": removed, "changed": changed, "top": top}


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
                "pid":        p.pid,
                "ppid":       p.ppid(),
                "name":       p.name(),
                "exe":        p.exe() if _safe(p.exe) else "",
                "cwd":        _safe(p.cwd) or "",
                "cmdline":    _safe(p.cmdline) or [],
                "status":     p.status(),
                "username":   _safe(p.username) or "",
                "created":    p.create_time(),
                "num_threads":p.num_threads(),
                "cpu_percent":p.cpu_percent(interval=None),
                "memory_mb":  round(p.memory_info().rss / 1024 / 1024, 1),
                "open_files": [f.path for f in (_safe(p.open_files) or [])][:50],
                "connections":[
                    {
                        "fd":     c.fd,
                        "family": str(c.family),
                        "type":   str(c.type),
                        "laddr":  f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
                        "raddr":  f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
                        "status": c.status,
                    }
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
