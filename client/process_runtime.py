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

# Windows Job Object Singleton for Subprocess Tree Auto-Teardown
_JOB_OBJECT_HANDLE = None
_JOB_OBJECT_INITIALIZED = False


def get_process_job_object():
    """Returns or initializes the Win32 Job Object configured to kill child processes on parent exit."""
    global _JOB_OBJECT_HANDLE, _JOB_OBJECT_INITIALIZED
    if sys.platform != "win32":
        return None
    if _JOB_OBJECT_INITIALIZED:
        return _JOB_OBJECT_HANDLE

    _JOB_OBJECT_INITIALIZED = True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        h_job = kernel32.CreateJobObjectW(None, None)
        if not h_job:
            return None

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        JobObjectExtendedLimitInformation = 9

        ok = kernel32.SetInformationJobObject(
            h_job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            kernel32.CloseHandle(h_job)
            return None

        _JOB_OBJECT_HANDLE = h_job
        return _JOB_OBJECT_HANDLE
    except Exception:
        return None


def bind_process_to_job(proc_handle_or_pid: Any) -> bool:
    """Assigns a subprocess or process handle to the parent Job Object."""
    if sys.platform != "win32":
        return False
    h_job = get_process_job_object()
    if not h_job:
        return False

    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32

        # If it's a subprocess object with _handle
        if hasattr(proc_handle_or_pid, "_handle") and proc_handle_or_pid._handle:
            raw_handle = int(proc_handle_or_pid._handle)
            return bool(kernel32.AssignProcessToJobObject(h_job, raw_handle))
        
        # If it's a numeric PID
        if isinstance(proc_handle_or_pid, int):
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001
            h_proc = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, proc_handle_or_pid)
            if h_proc:
                try:
                    return bool(kernel32.AssignProcessToJobObject(h_job, h_proc))
                finally:
                    kernel32.CloseHandle(h_proc)

        # If it's an asyncio Process with pid
        pid = getattr(proc_handle_or_pid, "pid", None)
        if isinstance(pid, int):
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001
            h_proc = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
            if h_proc:
                try:
                    return bool(kernel32.AssignProcessToJobObject(h_job, h_proc))
                finally:
                    kernel32.CloseHandle(h_proc)

    except Exception:
        pass
    return False


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
    bind_process_to_job(proc)
    _trace(command, "launch", pid=proc.pid)
    return proc


async def spawn_background(*command: str, **kwargs: Any) -> asyncio.subprocess.Process:
    proc = await asyncio.create_subprocess_exec(*command, **{**kwargs, **background_options()})
    bind_process_to_job(proc)
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
