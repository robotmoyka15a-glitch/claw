"""Interactive PTY sessions bridged to WebSocket.

On Windows we use `pywinpty` for a real PTY (so prompts, ANSI colors,
TUI apps work). On Linux/macOS we fall back to `pty` from stdlib.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import uuid
from typing import Awaitable, Callable

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        import winpty  # pywinpty
    except Exception:  # pragma: no cover
        winpty = None  # type: ignore
else:
    winpty = None  # type: ignore


def default_shell() -> list[str]:
    if IS_WINDOWS:
        return [os.environ.get("COMSPEC") or shutil.which("powershell.exe") or "cmd.exe"]
    return [os.environ.get("SHELL") or "/bin/bash"]


class PTYSession:
    """One interactive shell process tied to one websocket."""

    def __init__(self, cols: int = 120, rows: int = 30) -> None:
        self.id = uuid.uuid4().hex
        self.cols = cols
        self.rows = rows
        self._proc = None
        self._reader_task: asyncio.Task | None = None
        self._on_output: Callable[[str], Awaitable[None]] | None = None
        self._closed = False

    # ---------- lifecycle ----------
    def start(self, argv: list[str] | None = None) -> None:
        argv = argv or default_shell()
        if IS_WINDOWS:
            if winpty is None:
                raise RuntimeError("pywinpty is not installed")
            self._proc = winpty.PtyProcess.spawn(
                argv, dimensions=(self.rows, self.cols)
            )
        else:
            import pty
            import subprocess

            master, slave = pty.openpty()
            self._master_fd = master
            self._popen = subprocess.Popen(
                argv,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                close_fds=True,
                preexec_fn=os.setsid,
            )
            os.close(slave)

    async def attach_output(self, cb: Callable[[str], Awaitable[None]]) -> None:
        self._on_output = cb
        loop = asyncio.get_running_loop()
        self._reader_task = loop.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            while not self._closed:
                if IS_WINDOWS:
                    data = await asyncio.to_thread(self._read_windows)
                else:
                    data = await asyncio.to_thread(self._read_posix)
                if not data:
                    await asyncio.sleep(0.02)
                    continue
                if self._on_output:
                    await self._on_output(data)
        except Exception:
            # swallow — the ws layer will notice disconnect
            pass

    def _read_windows(self) -> str:
        try:
            return self._proc.read(1024)  # type: ignore[union-attr]
        except EOFError:
            self._closed = True
            return ""

    def _read_posix(self) -> str:
        import select

        r, _, _ = select.select([self._master_fd], [], [], 0.1)
        if not r:
            return ""
        try:
            chunk = os.read(self._master_fd, 1024)
            return chunk.decode("utf-8", errors="replace")
        except OSError:
            self._closed = True
            return ""

    # ---------- I/O ----------
    def write(self, data: str) -> None:
        if self._closed:
            return
        if IS_WINDOWS:
            self._proc.write(data)  # type: ignore[union-attr]
        else:
            os.write(self._master_fd, data.encode("utf-8"))

    def resize(self, cols: int, rows: int) -> None:
        self.cols, self.rows = cols, rows
        try:
            if IS_WINDOWS:
                self._proc.setwinsize(rows, cols)  # type: ignore[union-attr]
            else:
                import fcntl
                import struct
                import termios

                fcntl.ioctl(
                    self._master_fd,
                    termios.TIOCSWINSZ,
                    struct.pack("HHHH", rows, cols, 0, 0),
                )
        except Exception:
            pass

    def close(self) -> None:
        self._closed = True
        try:
            if IS_WINDOWS and self._proc is not None:
                self._proc.terminate(force=True)
            elif not IS_WINDOWS:
                self._popen.terminate()
                os.close(self._master_fd)
        except Exception:
            pass
