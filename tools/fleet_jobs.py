"""Local/private background Copilot jobs; state is intentionally kept out of Git."""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from client.process_runtime import run_background, popen_background
STATE_ROOT = PROJECT_ROOT / "orchestrator-state" / "jobs"
WORKTREE_ROOT = PROJECT_ROOT / ".worktrees"
JOB_ID_RE = re.compile(r"^job-[0-9a-f]{32}$")
MAX_DEADLINE_SECONDS = 7200
MAX_TIMEOUT_SECONDS = 1800
def configured_worker_limit() -> int:
    """Bound local concurrency while allowing the account pool to be used."""
    try:
        limit = int(os.environ.get("FLEET_JOB_MAX_WORKERS", "3"))
    except ValueError as exc:
        raise ValueError("FLEET_JOB_MAX_WORKERS must be an integer from 1 to 27") from exc
    if not 1 <= limit <= 27:
        raise ValueError("FLEET_JOB_MAX_WORKERS must be an integer from 1 to 27")
    return limit


MAX_ACTIVE_JOBS = configured_worker_limit()
TERMINAL = {"completed", "failed", "cancelled", "timed_out"}
SECRET_KEY_RE = re.compile(r"(token|secret|password|credential|api[_-]?key|private[_-]?key)", re.I)
SECRET_VALUE_RE = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AIza[0-9A-Za-z_-]{30,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{24,}|ya29\.[A-Za-z0-9_-]{20,})"
)


def _is_finite_number(value: int | float) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


class JobError(ValueError):
    """Invalid job request or unavailable job state."""


class JobTimeoutError(JobError):
    """A bounded job execution phase exhausted its allocated time."""


class FileLock:
    """Small cross-platform advisory lock held for this object's lifetime."""

    def __init__(self, path: Path, blocking: bool = True):
        self.path = path
        self.blocking = blocking
        self.handle: Any = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"\0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                mode = msvcrt.LK_LOCK if self.blocking else msvcrt.LK_NBLCK
                msvcrt.locking(self.handle.fileno(), mode, 1)
            else:
                import fcntl
                flags = fcntl.LOCK_EX | (0 if self.blocking else fcntl.LOCK_NB)
                fcntl.flock(self.handle.fileno(), flags)
        except (OSError, BlockingIOError):
            self.handle.close()
            self.handle = None
            raise
        return self

    def __exit__(self, *_: object) -> None:
        if self.handle is None:
            return
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None


@contextlib.contextmanager
def state_lock(job_id: str, root: Path = STATE_ROOT) -> Iterator[None]:
    validate_job_id(job_id)
    with FileLock(root / job_id / "state.lock"):
        yield


def validate_job_id(job_id: str) -> str:
    if not JOB_ID_RE.fullmatch(job_id):
        raise JobError("Invalid job ID")
    return job_id


def job_dir(job_id: str, root: Path = STATE_ROOT) -> Path:
    return root / validate_job_id(job_id)


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            temp.chmod(0o600)
        os.replace(temp, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()


def read_state(job_id: str, root: Path = STATE_ROOT) -> dict[str, Any]:
    path = job_dir(job_id, root) / "state.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise JobError(f"Unknown job: {job_id}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise JobError(f"Job state is unavailable: {job_id}") from exc
    return state


def update_state(job_id: str, root: Path = STATE_ROOT, **changes: Any) -> dict[str, Any]:
    with state_lock(job_id, root):
        state = read_state(job_id, root)
        if state.get("status") in TERMINAL:
            return state
        state.update(changes)
        state["updated_at"] = time.time()
        atomic_json(job_dir(job_id, root) / "state.json", state)
        return state


def validate_spec(spec: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    if not isinstance(spec, dict):
        raise JobError("Spec must be a JSON object")
    for key in spec:
        if SECRET_KEY_RE.search(key):
            raise JobError(f"Credential-like spec field is forbidden: {key}")
    if set(spec) - {
        "specification", "allowed_files", "repo_path", "timeout_seconds",
        "overall_deadline", "worker_id", "test_commands",
    }:
        raise JobError("Spec contains unsupported fields")
    text = spec.get("specification")
    if not isinstance(text, str) or not text.strip() or SECRET_VALUE_RE.search(text):
        raise JobError("specification must be non-empty text and contain no credentials")
    for value in spec.values():
        if isinstance(value, str) and SECRET_VALUE_RE.search(value):
            raise JobError("Spec contains a credential-like value")
    allowed = spec.get("allowed_files")
    if not isinstance(allowed, list) or not allowed:
        raise JobError("allowed_files must be a non-empty list of relative paths")
    clean_allowed: list[str] = []
    for item in allowed:
        if not isinstance(item, str) or not item or "\\" in item or "\0" in item or ":" in item:
            raise JobError("allowed_files entries must be safe relative POSIX paths")
        path = PurePosixPath(item)
        if path.is_absolute() or any(part in {"", ".", "..", ".git"} for part in path.parts):
            raise JobError(f"Unsafe allowed_files path: {item}")
        if re.match(r"^[A-Za-z]:", item):
            raise JobError(f"Unsafe allowed_files path: {item}")
        clean_allowed.append(path.as_posix())
    repo_path = spec.get("repo_path")
    if not isinstance(repo_path, str) or not Path(repo_path).is_absolute():
        raise JobError("repo_path must be an absolute path to an existing Git repository")
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise JobError("repo_path must be an existing directory")
    check = run_background(
        ["git", "rev-parse", "--show-toplevel"], cwd=repo,
        capture_output=True, text=True, check=False,
    )
    if check.returncode or not check.stdout.strip():
        raise JobError("repo_path must be an existing Git repository")
    if Path(check.stdout.strip()).resolve() != repo:
        raise JobError("repo_path must identify the Git repository root")
    timeout = spec.get("timeout_seconds")
    if (
        isinstance(timeout, bool) or not isinstance(timeout, (int, float))
        or not _is_finite_number(timeout) or not 0 < timeout <= MAX_TIMEOUT_SECONDS
    ):
        raise JobError(f"timeout_seconds must be greater than 0 and at most {MAX_TIMEOUT_SECONDS}")
    deadline = spec.get("overall_deadline")
    if (
        isinstance(deadline, bool) or not isinstance(deadline, (int, float))
        or not _is_finite_number(deadline) or deadline <= now or deadline > now + MAX_DEADLINE_SECONDS
    ):
        raise JobError("overall_deadline must be a future UNIX time no more than 2 hours away")
    worker_id = spec.get("worker_id")
    if worker_id is not None and (not isinstance(worker_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", worker_id)):
        raise JobError("worker_id must be a simple worker name")
    tests = spec.get("test_commands", [])
    if (
        not isinstance(tests, list)
        or any(
            not isinstance(command, list)
            or not command
            or any(not isinstance(arg, str) or not arg for arg in command)
            for command in tests
        )
    ):
        raise JobError("test_commands must be a list of non-empty argv arrays")
    normalized = dict(spec)
    normalized.update(repo_path=str(repo), allowed_files=clean_allowed, timeout_seconds=float(timeout))
    normalized["overall_deadline"] = float(deadline)
    normalized["test_commands"] = tests
    return normalized


def _process_identity(
    pid: int,
    job_id: str,
    *,
    allow_unmarked: bool = False,
) -> dict[str, Any]:
    import psutil
    proc = psutil.Process(pid)
    cmd = proc.cmdline()
    if not cmd or (not allow_unmarked and job_id not in " ".join(cmd)):
        raise JobError("Process command does not identify this job")
    return {
        "pid": pid, "create_time": proc.create_time(), "command": cmd,
        "job_id": job_id, "direct_launch": allow_unmarked,
    }


def _process_matches(proc: Any, identity: dict[str, Any], job_id: str) -> bool:
    import psutil
    try:
        return (
            identity.get("job_id") == job_id
            and abs(proc.create_time() - float(identity["create_time"])) < 0.01
            and proc.cmdline() == identity.get("command")
            and (identity.get("direct_launch") or job_id in " ".join(proc.cmdline()))
        )
    except (KeyError, ValueError, OSError, TypeError, psutil.Error):
        return False


def _identity_alive(identity: dict[str, Any] | None, job_id: str) -> bool:
    if not identity or identity.get("job_id") != job_id:
        return False
    try:
        import psutil
        proc = psutil.Process(int(identity["pid"]))
        return _process_matches(proc, identity, job_id)
    except (KeyError, ValueError, OSError, TypeError, psutil.Error):
        return False


def _snapshot_process_tree(identity: dict[str, Any] | None, job_id: str) -> list[dict[str, Any]]:
    if not _identity_alive(identity, job_id):
        return []
    import psutil
    try:
        root = psutil.Process(int(identity["pid"]))
        if not _process_matches(root, identity, job_id):
            return []
        descendants = root.children(recursive=True)
    except psutil.NoSuchProcess:
        return []
    except psutil.Error as exc:
        raise JobError("Unable to inspect the verified job process tree") from exc
    captured: list[dict[str, Any]] = []
    for child in descendants:
        try:
            parent_pid = child.ppid()
            parent = psutil.Process(parent_pid)
            captured.append({
                "pid": child.pid, "create_time": child.create_time(),
                "command": child.cmdline(), "parent_pid": parent_pid,
                "parent_create_time": parent.create_time(), "job_id": job_id,
            })
        except psutil.NoSuchProcess:
            continue
        except psutil.Error as exc:
            raise JobError("Unable to verify a child in the job process tree") from exc
    return captured


def kill_verified_tree(
    identity: dict[str, Any] | None,
    job_id: str,
    tree: list[dict[str, Any]] | None = None,
) -> bool:
    """Kill only an identity-verified root or descendants previously observed beneath it."""
    if not identity or identity.get("job_id") != job_id:
        return False
    import psutil
    root_alive = _identity_alive(identity, job_id)
    if root_alive:
        tree = [*(tree or []), *_snapshot_process_tree(identity, job_id)]
    try:
        known_creation = {
            (int(identity["pid"]), float(identity["create_time"])),
        }
    except (KeyError, ValueError, TypeError):
        return False
    captured: list[dict[str, Any]] = []
    for item in tree or []:
        if not isinstance(item, dict) or item.get("job_id") != job_id:
            continue
        try:
            known_creation.add((int(item["pid"]), float(item["create_time"])))
            int(item["parent_pid"])
            float(item["parent_create_time"])
            list(item["command"])
        except (KeyError, ValueError, TypeError):
            continue
        captured.append(item)
    terminated = False
    for item in reversed(captured):
        try:
            pid = int(item["pid"])
            parent_pid = int(item["parent_pid"])
            process = psutil.Process(pid)
            if (
                item.get("job_id") != job_id
                or abs(process.create_time() - float(item["create_time"])) >= 0.01
                or process.cmdline() != item.get("command")
                or not any(
                    known_pid == parent_pid
                    and abs(float(item["parent_create_time"]) - known_created) < 0.01
                    for known_pid, known_created in known_creation
                )
            ):
                continue
            process.kill()
            terminated = True
        except (psutil.NoSuchProcess, KeyError, ValueError, TypeError):
            continue
        except psutil.Error as exc:
            raise JobError("Unable to signal a verified process-tree child") from exc
    if not root_alive or not _identity_alive(identity, job_id):
        return terminated
    try:
        root = psutil.Process(int(identity["pid"]))
        if _process_matches(root, identity, job_id):
            root.kill()
            return True
    except psutil.NoSuchProcess:
        return terminated
    except psutil.Error as exc:
        raise JobError("Unable to terminate the verified job process") from exc
    return terminated


def _redact(text: str, secrets: list[str] | None = None) -> str:
    for secret in secrets or []:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return SECRET_VALUE_RE.sub("[REDACTED]", text)


def _snapshot_process_alive(item: dict[str, Any] | None, job_id: str) -> bool:
    if not item or item.get("job_id") != job_id:
        return False
    try:
        import psutil
    except ImportError:
        return False
    try:
        proc = psutil.Process(int(item["pid"]))
        return (
            abs(proc.create_time() - float(item["create_time"])) < 0.01
            and proc.cmdline() == item.get("command")
        )
    except (KeyError, ValueError, OSError, TypeError, psutil.Error):
        return False


def _recorded_worker_alive(state: dict[str, Any], job_id: str) -> bool:
    if _identity_alive(state.get("worker"), job_id):
        return True
    return any(
        _snapshot_process_alive(item, job_id)
        for item in state.get("worker_tree", [])
        if isinstance(item, dict)
    )


def _recorded_tree_alive(state: dict[str, Any], key: str, job_id: str) -> bool:
    return any(
        _snapshot_process_alive(item, job_id)
        for item in state.get(key, [])
        if isinstance(item, dict)
    )


def _terminate_recorded_processes(state: dict[str, Any], job_id: str, grace: float = 10) -> bool:
    for identity_key, tree_key in (
        ("supervisor", "supervisor_tree"),
        ("worker", "worker_tree"),
    ):
        identity = state.get(identity_key)
        if identity:
            kill_verified_tree(identity, job_id, state.get(tree_key))
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if not (
            _identity_alive(state.get("supervisor"), job_id)
            or _recorded_tree_alive(state, "supervisor_tree", job_id)
            or _recorded_worker_alive(state, job_id)
        ):
            return True
        time.sleep(0.1)
    return not (
        _identity_alive(state.get("supervisor"), job_id)
        or _recorded_tree_alive(state, "supervisor_tree", job_id)
        or _recorded_worker_alive(state, job_id)
    )


def _git_inspection(repo: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Retry bounded read-only Git queries and retain a redacted failure reason."""
    detail = "Git query failed"
    for attempt in range(3):
        try:
            proc = run_background(
                ["git", *args], cwd=repo, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, check=False, timeout=10,
            )
            if proc.returncode == 0:
                return proc
            detail = _redact(proc.stderr.decode("utf-8", errors="replace"))[:500]
        except subprocess.TimeoutExpired:
            detail = "Git query timed out"
        if attempt < 2:
            time.sleep(0.1 * (attempt + 1))
    raise JobError(f"Unable to inspect worktree changes: {detail}")


def _repo_changes(repo: Path, base_commit: str | None = None) -> list[str]:
    proc = _git_inspection(repo, ["status", "--porcelain", "-z", "--untracked-files=all"])
    raw = proc.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    changed: set[str] = set()
    idx = 0
    while idx < len(raw) and raw[idx]:
        entry = raw[idx]
        path = entry[3:]
        if entry[:2].find("R") >= 0 or entry[:2].find("C") >= 0:
            changed.add(path.replace("\\", "/"))
            idx += 1
            if idx >= len(raw):
                break
            path = raw[idx]
        changed.add(path.replace("\\", "/"))
        idx += 1
    if base_commit:
        diff = _git_inspection(repo, ["diff", "--name-only", "-z", "--no-renames", base_commit])
        changed.update(
            path.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            for path in diff.stdout.split(b"\0") if path
        )
    return sorted(changed)


def _within_allowed(path: str, allowed: list[str]) -> bool:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts or ".git" in candidate.parts:
        return False
    return candidate.as_posix() in allowed


def _capture_patch(worktree: Path, directory: Path, base_commit: str | None = None) -> dict[str, Any]:
    if base_commit is None:
        try:
            head = _git_inspection(worktree, ["rev-parse", "--verify", "HEAD"])
            base_commit = head.stdout.decode("ascii").strip()
        except JobError:
            # An unborn repository still has recoverable untracked artifacts.
            base_commit = None
    if base_commit:
        diff = _git_inspection(worktree, ["diff", "--binary", base_commit])
        diff_data = diff.stdout
    else:
        diff_data = b""
    untracked: dict[str, str] = {}
    unsafe: list[str] = []
    for name in _repo_changes(worktree, base_commit):
        file_path = worktree.joinpath(*PurePosixPath(name).parts)
        tracked = _is_tracked(worktree, name)
        if file_path.is_symlink():
            if not tracked:
                untracked[name] = base64.b64encode(os.readlink(file_path).encode("utf-8")).decode("ascii")
            continue
        if not file_path.resolve().is_relative_to(worktree.resolve()):
            unsafe.append(name)
            continue
        if file_path.is_file() and not tracked:
            untracked[name] = base64.b64encode(file_path.read_bytes()).decode("ascii")
    payload = {
        "format": "fleet-job-patch-v1",
        "diff_binary_base64": base64.b64encode(diff_data).decode("ascii"),
        "untracked_files_base64": untracked,
        "unsafe_untracked_paths": unsafe,
    }
    atomic_json(directory / "patch.json", payload)
    return payload


def _is_tracked(repo: Path, path: str) -> bool:
    return run_background(
        ["git", "ls-files", "--error-unmatch", "--", path],
        cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def _manifest(job_id: str, status: str, verification: str, summary: str, files: list[str]) -> str:
    lines = [
        f"Job: {job_id}", f"Status: {status}", f"Verification: {verification}",
        f"Summary: {_redact(summary)[:500]}", "Changed files:",
    ]
    lines.extend(f"- {name}" for name in files[:40])
    bounded: list[str] = []
    remaining = 300
    for line in lines:
        words = line.split()
        if not words or remaining <= 0:
            break
        bounded.append(" ".join(words[:remaining]))
        remaining -= min(len(words), remaining)
    return "\n".join(bounded)


def finish_job(
    job_id: str,
    root: Path,
    status: str,
    summary: str,
    verification: str | None = None,
    test_evidence: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically preserve artifacts and apply one terminal transition."""
    validate_job_id(job_id)
    directory = job_dir(job_id, root)
    with state_lock(job_id, root):
        state = read_state(job_id, root)
        if state["status"] in TERMINAL:
            return state
        try:
            spec = json.loads((directory / "spec.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            spec = {}
        if not isinstance(spec, dict):
            spec = {}
        if state.get("worktree"):
            worktree: Path | None = Path(state["worktree"])
        elif isinstance(spec.get("repo_path"), str) and Path(spec["repo_path"]).is_absolute():
            worktree = Path(spec["repo_path"]) / ".worktrees" / job_id
        else:
            worktree = None
        base_commit = state.get("base_commit")
        artifact_error = None
        changed = []
        patch = {
            "format": "fleet-job-patch-v1", "diff_binary_base64": "",
            "untracked_files_base64": {}, "unsafe_untracked_paths": [],
        }
        if worktree and worktree.is_dir():
            try:
                changed = _repo_changes(worktree, base_commit)
                patch = _capture_patch(worktree, directory, base_commit)
            except JobError as exc:
                artifact_error = _redact(str(exc))
                recovery = {}
                for name in spec.get("allowed_files", []):
                    candidate = worktree / name
                    if (
                        candidate.is_file() and not candidate.is_symlink()
                        and candidate.resolve().is_relative_to(worktree.resolve())
                    ):
                        recovery[name] = base64.b64encode(candidate.read_bytes()).decode("ascii")
                patch["recovery_files_base64"] = recovery
                patch["artifact_error"] = artifact_error
                if status not in {"cancelled", "timed_out"}:
                    status = "failed"
                verification = "failed"
                summary = f"{summary}; patch capture failed: {artifact_error}"
        if not (directory / "patch.json").exists():
            atomic_json(directory / "patch.json", patch)
        evidence = state.get("test_evidence", []) if test_evidence is None else test_evidence
        atomic_json(directory / "test_evidence.json", {"commands": evidence})
        verification = verification or ("failed" if status == "failed" else "unverified")
        manifest = _manifest(job_id, status, verification, summary, changed)
        atomic_text(directory / "manifest.txt", manifest)
        atomic_json(directory / "manifest.json", {
            "manifest": manifest, "word_count": len(manifest.split()),
        })
        state.update(
            status=status, verification=verification, summary=_redact(summary),
            changed_files=changed, patch_present=bool(patch), test_evidence=evidence,
            phase=status, heartbeat=time.time(), updated_at=time.time(),
        )
        if artifact_error:
            state["artifact_error"] = artifact_error
        state.setdefault("usage", {"model": None, "tokens": None, "credits": None})
        if extra:
            state.update(extra)
        atomic_json(directory / "state.json", state)
        return state


def start_job(spec_file: str | Path, auto_tier: str = "intelligence", state_root: Path = STATE_ROOT) -> str:
    if auto_tier != "intelligence":
        raise JobError("Only --auto-tier intelligence is supported")
    raw = Path(spec_file).read_text(encoding="utf-8")
    spec = validate_spec(json.loads(raw))
    job_id = f"job-{uuid.uuid4().hex}"
    directory = job_dir(job_id, state_root)
    directory.mkdir(parents=True, exist_ok=False)
    if os.name != "nt":
        directory.chmod(0o700)
    spec_text = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    atomic_text(directory / "spec.json", spec_text)
    state = {
        "job_id": job_id, "spec_sha256": hashlib.sha256(spec_text.encode()).hexdigest(),
        "status": "queued", "verification": "unverified", "created_at": time.time(),
        "updated_at": time.time(), "heartbeat": time.time(), "attempt": 1,
        "overall_deadline": spec["overall_deadline"],
        "cancel_requested": False, "supervisor": None, "worker": None,
        "unresponsive": False, "worktree": None, "summary": "", "test_evidence": [],
        "phase": "queued", "worker_tree": [], "supervisor_tree": [],
        "usage": {"model": None, "tokens": None, "credits": None},
    }
    atomic_json(directory / "state.json", state)
    try:
        return _launch_supervisor(job_id, state_root)
    except Exception as exc:
        finish_job(job_id, state_root, "failed", f"Unable to launch supervisor: {type(exc).__name__}")
        raise


def _launch_supervisor(job_id: str, state_root: Path) -> str:
    directory = job_dir(job_id, state_root)
    spec = json.loads((directory / "spec.json").read_text(encoding="utf-8"))
    from tools.fleet_job_supervisor import _configured_accounts
    bridge_accounts = os.environ.pop("FLEET_JOB_ACCOUNTS", None)
    try:
        accounts = _configured_accounts()
    finally:
        if bridge_accounts is not None:
            os.environ["FLEET_JOB_ACCOUNTS"] = bridge_accounts
    if spec.get("worker_id"):
        accounts = [a for a in accounts if a.get("worker_id") == spec["worker_id"]]
    args = [sys.executable, "-m", "tools.fleet_job_supervisor", "--job-id", job_id]
    if state_root != STATE_ROOT:
        args.extend(["--state-root", str(state_root)])
    kwargs: dict[str, Any] = {
        "cwd": str(PROJECT_ROOT), "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    env = os.environ.copy()
    for key in list(env):
        if (
            SECRET_KEY_RE.search(key)
            or key.startswith(("COPILOT_ACCOUNT_", "GIT_CONFIG_"))
        ):
            env.pop(key, None)
    env.pop("COPILOT_GITHUB_TOKEN", None)
    env.pop("FLEET_JOB_WORKER_ID", None)
    env["FLEET_JOB_ACCOUNTS"] = json.dumps(accounts)
    kwargs["env"] = env
    if os.name != "nt":
        kwargs["start_new_session"] = True
    proc = popen_background(args, **kwargs)
    identity = _process_identity(proc.pid, job_id)
    with state_lock(job_id, state_root):
        state = read_state(job_id, state_root)
        if state["status"] not in TERMINAL:
            state["supervisor"] = identity
            state["supervisor_tree"] = []
            state["updated_at"] = time.time()
            atomic_json(directory / "state.json", state)
    return job_id


def status_job(job_id: str, state_root: Path = STATE_ROOT) -> dict[str, Any]:
    validate_job_id(job_id)
    state = read_state(job_id, state_root)
    state["unresponsive"] = (
        state.get("status") == "running"
        and time.time() - float(state.get("heartbeat", 0)) > 120
        and _identity_alive(state.get("supervisor"), job_id)
    )
    state["interrupted"] = (
        state.get("status") in {"queued", "running"}
        and not _identity_alive(state.get("supervisor"), job_id)
    )
    state["heartbeat_age"] = max(0.0, time.time() - float(state.get("heartbeat", 0)))
    directory = job_dir(job_id, state_root)
    state["artifact_paths"] = {
        name: str(directory / name)
        for name in ("manifest.txt", "patch.json", "test_evidence.json", "supervisor.log")
    }
    return state


def list_jobs(state_root: Path = STATE_ROOT) -> list[dict[str, Any]]:
    if not state_root.is_dir():
        return []
    result = []
    for path in sorted(state_root.iterdir()):
        if path.is_dir() and JOB_ID_RE.fullmatch(path.name) and (path / "state.json").is_file():
            result.append(status_job(path.name, state_root))
    return result


def cancel_job(job_id: str, state_root: Path = STATE_ROOT) -> dict[str, Any]:
    validate_job_id(job_id)
    update_state(job_id, state_root, cancel_requested=True)
    state = read_state(job_id, state_root)
    if state["status"] in TERMINAL:
        if not _identity_alive(state.get("supervisor"), job_id):
            if not _terminate_recorded_processes(state, job_id):
                raise JobError("Cancellation requested but a verified worker process remains alive")
        return state
    identity = state.get("supervisor")
    if not _identity_alive(identity, job_id):
        if not _terminate_recorded_processes(state, job_id):
            raise JobError("Cancellation requested but a verified worker process remains alive")
        return finish_job(job_id, state_root, "cancelled", "Cancelled before or after supervisor execution")
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline and _identity_alive(identity, job_id):
        time.sleep(0.1)
        latest = read_state(job_id, state_root)
        if latest["status"] in TERMINAL:
            return latest
    latest = read_state(job_id, state_root)
    if not _terminate_recorded_processes(latest, job_id):
        raise JobError("Cancellation was requested but a verified job process is still running")
    return finish_job(job_id, state_root, "cancelled", "Cancelled after cooperative grace period")


def resume_job(job_id: str, state_root: Path = STATE_ROOT) -> str:
    validate_job_id(job_id)
    directory = job_dir(job_id, state_root)
    with state_lock(job_id, state_root):
        state = read_state(job_id, state_root)
        spec_text = (directory / "spec.json").read_text(encoding="utf-8")
        digest = hashlib.sha256(spec_text.encode()).hexdigest()
        if digest != state.get("spec_sha256"):
            raise JobError("Immutable job spec integrity check failed")
        if state["status"] not in {"queued", "running", "failed", "timed_out"}:
            raise JobError("Resume requires an interrupted, non-live supervisor")
        if (
            _identity_alive(state.get("supervisor"), job_id)
            or _recorded_worker_alive(state, job_id)
            or any(
                _snapshot_process_alive(item, job_id)
                for item in state.get("supervisor_tree", [])
                if isinstance(item, dict)
            )
        ):
            raise JobError("Resume requires an interrupted job with no live supervisor or worker")
        if int(state.get("attempt", 1)) >= 2:
            raise JobError("Job retry limit reached")
        raw_spec = json.loads(spec_text)
        raw_deadline = raw_spec.get("overall_deadline") if isinstance(raw_spec, dict) else None
        if isinstance(raw_deadline, (int, float)) and not isinstance(raw_deadline, bool) and time.time() >= raw_deadline:
            raise JobError("Original overall deadline has expired")
        spec = validate_spec(raw_spec)
        if state.get("overall_deadline") != spec["overall_deadline"]:
            raise JobError("Original overall deadline integrity check failed")
        state.update(
            status="queued", verification="unverified", attempt=2,
            supervisor=None, worker=None, worker_tree=[], supervisor_tree=[],
            test_evidence=[],
            retry_feedback={
                "status": state.get("status"),
                "summary": state.get("summary", ""),
                "test_evidence": state.get("test_evidence", []),
            },
            phase="queued", heartbeat=time.time(), cancel_requested=False,
            updated_at=time.time(), unresponsive=False,
        )
        atomic_json(directory / "state.json", state)
    try:
        return _launch_supervisor(job_id, state_root)
    except Exception as exc:
        finish_job(job_id, state_root, "failed", f"Unable to resume supervisor: {type(exc).__name__}")
        raise


def result_job(job_id: str, state_root: Path = STATE_ROOT) -> dict[str, Any]:
    validate_job_id(job_id)
    directory = job_dir(job_id, state_root)
    state = status_job(job_id, state_root)
    files = {}
    for name in ("manifest.txt", "patch.json", "test_evidence.json", "supervisor.log"):
        path = directory / name
        if path.is_file():
            if name == "patch.json":
                files[name] = json.loads(path.read_text(encoding="utf-8"))
            elif name == "test_evidence.json":
                files[name] = json.loads(path.read_text(encoding="utf-8"))
            else:
                files[name] = path.read_text(encoding="utf-8")
    return {"job_id": job_id, "state": state, "result": files}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fleet job")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--spec-file", required=True)
    start.add_argument("--auto-tier", required=True, choices=["intelligence"])
    status = sub.add_parser("status")
    status.add_argument("job_id")
    status.add_argument("--json", action="store_true", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--json", action="store_true", required=True)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("job_id")
    result = sub.add_parser("result")
    result.add_argument("job_id")
    result.add_argument("--json", action="store_true", required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("job_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "start":
            data: Any = {"job_id": start_job(args.spec_file, args.auto_tier)}
        elif args.command == "status":
            data = status_job(args.job_id)
        elif args.command == "list":
            data = list_jobs()
        elif args.command == "cancel":
            data = cancel_job(args.job_id)
        elif args.command == "result":
            data = result_job(args.job_id)
        else:
            data = {"job_id": resume_job(args.job_id)}
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    except (JobError, OSError, json.JSONDecodeError) as exc:
        print(f"fleet job: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
