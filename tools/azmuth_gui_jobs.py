"""Job records and bounded local subprocess execution for the Azmuth GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Optional, Sequence


class WindowsProcessTree:
    """Keep a per-job Win32 Job Object, including children outliving their parent."""

    def __init__(self, process: subprocess.Popen[str]):
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t), ("process_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("basic", BasicLimits), ("io", IOCounters),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t),
            ]

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def close(self) -> None:
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise ProcessCleanupError("Unable to close the local process-tree job handle")


class JobCancelled(Exception):
    """The user cancelled a managed operation."""


class ProcessCleanupError(RuntimeError):
    """The local process or its output pipes could not be cleaned up in time."""


@dataclass
class GUIJob:
    job_id: str
    title: str
    outcome: str = "running"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    output: str = ""
    return_code: Optional[int] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    worker_done: threading.Event = field(default_factory=threading.Event)
    process: Optional[subprocess.Popen[str]] = None
    managed: bool = False
    stop_waiting: bool = False
    notice: Optional[str] = None


def terminate_owned_process(process: subprocess.Popen[str], timeout: float = 2.0) -> None:
    """Stop an owned process tree; report cleanup failures instead of hiding them."""
    if process.poll() is not None:
        return
    tree_error = None
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=timeout, check=False,
            )
            if result.returncode and process.poll() is None:
                tree_error = result.stderr.strip() or result.stdout.strip()
        else:
            import signal
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        tree_error = str(exc)
        try:
            process.kill()
            process.wait(timeout=timeout)
        except (OSError, subprocess.SubprocessError) as kill_exc:
            raise ProcessCleanupError(f"Local process {process.pid} is not confirmed stopped: {kill_exc}") from kill_exc
    if tree_error:
        raise ProcessCleanupError(f"Local parent stopped, but process-tree cleanup is unconfirmed: {tree_error}")


def run_managed_process(
    job: GUIJob, command: Sequence[str], *, cwd: Path,
    timeout_seconds: float = 600.0, cleanup_seconds: float = 2.0,
) -> subprocess.CompletedProcess[str]:
    """Poll cancellation and deadline while draining both pipes in the worker thread."""
    if job.cancel_event.is_set():
        raise JobCancelled("Cancelled before local process startup. Remote cleanup is unconfirmed.")
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
    process = subprocess.Popen(
        list(command), cwd=str(cwd), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", creationflags=flags,
        start_new_session=os.name != "nt",
    )
    job.process = process
    tree = None
    deadline = time.monotonic() + timeout_seconds
    terminal_error: Optional[Exception] = None
    try:
        if os.name == "nt":
            tree = WindowsProcessTree(process)
        while True:
            if job.cancel_event.is_set():
                terminal_error = JobCancelled("Local process cancelled. Remote session cleanup is unconfirmed.")
            elif time.monotonic() >= deadline:
                terminal_error = TimeoutError(f"Operation timed out after {timeout_seconds:g} seconds. Remote session cleanup is unconfirmed.")
            if terminal_error is not None:
                if tree is not None:
                    tree.close()
                terminate_owned_process(process, cleanup_seconds)
                break
            try:
                job.stdout, job.stderr = process.communicate(timeout=min(0.1, max(0.001, deadline - time.monotonic())))
                break
            except subprocess.TimeoutExpired as exc:
                # Retain diagnostics even if a later cleanup attempt fails.
                job.stdout = exc.output.decode("utf-8", "replace") if isinstance(exc.output, bytes) else (exc.output or "")
                job.stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                continue
        if terminal_error is not None:
            try:
                job.stdout, job.stderr = process.communicate(timeout=cleanup_seconds)
            except subprocess.TimeoutExpired as exc:
                raise ProcessCleanupError("Local process exited, but its output pipes did not close in time.") from exc
    except Exception as exc:
        if tree is not None:
            tree.close()
        if not isinstance(exc, ProcessCleanupError) and process.poll() is None:
            terminate_owned_process(process, cleanup_seconds)
        raise
    finally:
        if tree is not None:
            tree.close()
        job.return_code = process.poll()
        job.output = job.stdout + job.stderr
    if terminal_error is not None:
        raise terminal_error
    return subprocess.CompletedProcess(list(command), process.returncode, job.stdout, job.stderr)
