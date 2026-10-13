"""Consistent process visibility and optional, argument-free launch diagnostics."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

launch_observer: ContextVar[Any] = ContextVar("fleet_launch_observer", default=None)


def background_options() -> dict[str, Any]:
    if sys.platform != "win32":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": startup}


def _trace(command: Any, phase: str, *, pid: int | None = None, code: int | None = None) -> None:
    target = os.getenv("FLEET_PROCESS_TRACE")
    if not target:
        return
    # Never record arguments, environment values, or provider stderr (OAuth secrets).
    frame = inspect.stack()[2]
    entry = {
        "time": time.time(),
        "parent_pid": os.getpid(),
        "pid": pid,
        "executable": str(command[0]) if isinstance(command, (list, tuple)) and command else "unknown",
        "site": f"{Path(frame.filename).name}:{frame.lineno}",
        "mode": "background",
        "phase": phase,
        "exit_code": code,
    }
    try:
        path = Path(target).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def run_background(command: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    options = {**kwargs, **background_options()}
    _trace(command, "launch")
    try:
        result = subprocess.run(command, **options)
    except Exception:
        _trace(command, "launch_failed")
        raise
    _trace(command, "exit", code=result.returncode)
    return result


def popen_background(command: Any, **kwargs: Any) -> subprocess.Popen:
    proc = subprocess.Popen(command, **{**kwargs, **background_options()})
    _trace(command, "launch", pid=proc.pid)
    return proc


async def spawn_background(*command: str, **kwargs: Any) -> asyncio.subprocess.Process:
    proc = await asyncio.create_subprocess_exec(*command, **{**kwargs, **background_options()})
    observer = launch_observer.get()
    if observer:
        try:
            observer(proc)
        except Exception:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise
    _trace(command, "launch", pid=getattr(proc, "pid", None))
    return proc


async def communicate_background(proc: asyncio.subprocess.Process, timeout: float) -> tuple[bytes, bytes]:
    try:
        result = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        _trace([], "exit", pid=getattr(proc, "pid", None), code=proc.returncode)
        return result
    except BaseException:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        _trace([], "stopped", pid=getattr(proc, "pid", None), code=proc.returncode)
        raise
