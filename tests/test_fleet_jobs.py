"""Regression coverage for the local/private background-job bridge.

Every Git fixture and job-state directory is temporary; supervisor and provider
execution are mocked so the suite can never dispatch a live Copilot job.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tools import fleet_jobs as jobs


def test_worker_limit_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLEET_JOB_MAX_WORKERS", raising=False)
    assert jobs.configured_worker_limit() == 3
    for value in ("1", "4", "27"):
        monkeypatch.setenv("FLEET_JOB_MAX_WORKERS", value)
        assert jobs.configured_worker_limit() == int(value)
    for value in ("0", "28", "invalid"):
        monkeypatch.setenv("FLEET_JOB_MAX_WORKERS", value)
        with pytest.raises(ValueError, match="FLEET_JOB_MAX_WORKERS"):
            jobs.configured_worker_limit()
from tools import fleet_job_supervisor as supervisor


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("value = 1\n", encoding="utf-8")
    return repo


def make_spec(repo: Path, **updates: object) -> dict[str, object]:
    data: dict[str, object] = {
        "specification": "Change the implementation safely.",
        "allowed_files": ["src/main.py", "src/new.py"],
        "repo_path": str(repo.resolve()),
        "timeout_seconds": 120,
        "overall_deadline": time.time() + 3600,
        "test_commands": [],
    }
    data.update(updates)
    return data


def write_spec(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_validate_spec_and_rejects_unsafe_paths(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    spec = jobs.validate_spec(make_spec(repo))
    assert spec["repo_path"] == str(repo.resolve())
    for path in ("../outside", "/absolute", "C:/outside", "src/../outside", ".git/config", "src\\file.py"):
        with pytest.raises(jobs.JobError):
            jobs.validate_spec(make_spec(repo, allowed_files=[path]))
    with pytest.raises(jobs.JobError, match="timeout_seconds"):
        jobs.validate_spec(make_spec(repo, timeout_seconds=1801))
    with pytest.raises(jobs.JobError, match="overall_deadline"):
        jobs.validate_spec(make_spec(repo, overall_deadline=time.time() + 7201))
    with pytest.raises(jobs.JobError, match="overall_deadline"):
        jobs.validate_spec(make_spec(repo, overall_deadline=float("nan")))
    with pytest.raises(jobs.JobError, match="safe relative"):
        jobs.validate_spec(make_spec(repo, allowed_files=["src/file.py:stream"]))
    with pytest.raises(jobs.JobError, match="credential"):
        jobs.validate_spec(make_spec(repo, specification="Use " + "github_pat_" + "a" * 32))
    with pytest.raises(jobs.JobError, match="Credential-like"):
        jobs.validate_spec(make_spec(repo, **{"access_token": "rejected"}))


def test_start_persists_immutable_spec_before_supervisor_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    spec_path = write_spec(tmp_path / "spec.json", make_spec(repo))
    seen: list[str] = []

    def launch(job_id: str, root: Path) -> str:
        state = jobs.read_state(job_id, root)
        original = (jobs.job_dir(job_id, root) / "spec.json").read_text(encoding="utf-8")
        assert state["status"] == "queued"
        assert state["supervisor"] is None
        assert state["spec_sha256"] == hashlib.sha256(original.encode()).hexdigest()
        seen.append(job_id)
        return job_id

    monkeypatch.setattr(jobs, "_launch_supervisor", launch)
    result = jobs.start_job(spec_path, state_root=state_root)
    assert result == seen[0]
    assert jobs.read_state(result, state_root)["attempt"] == 1


def test_status_and_list_do_not_restart_or_mutate_interrupted_jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    spec_path = write_spec(tmp_path / "spec.json", make_spec(repo))
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(spec_path, state_root=state_root)
    jobs.update_state(job_id, state_root, status="running", heartbeat=time.time() - 200)
    before = jobs.read_state(job_id, state_root)
    monkeypatch.setattr(jobs, "_identity_alive", lambda identity, jid: False)
    one = jobs.status_job(job_id, state_root)
    many = jobs.list_jobs(state_root)
    after = jobs.read_state(job_id, state_root)
    assert one["interrupted"] is True
    assert one["unresponsive"] is False
    assert many[0]["job_id"] == job_id
    assert before == after


def test_git_capture_failure_preserves_files_and_terminal_state(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", make_spec(repo)), state_root=state_root)
    jobs.update_state(job_id, state_root, worktree=str(repo), status="running")
    monkeypatch.setattr(jobs, "_repo_changes", lambda *args: (_ for _ in ()).throw(jobs.JobError("metadata unavailable")))
    state = jobs.finish_job(job_id, state_root, "completed", "Worker exited", "passed")
    assert state["status"] == "failed"
    assert state["verification"] == "failed"
    assert "metadata unavailable" in state["artifact_error"]
    patch = json.loads((jobs.job_dir(job_id, state_root) / "patch.json").read_text())
    assert base64.b64decode(patch["recovery_files_base64"]["src/main.py"]).decode().strip() == "value = 1"
    assert jobs.read_state(job_id, state_root)["status"] == "failed"


def test_stale_live_heartbeat_is_unresponsive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", make_spec(repo)), state_root=state_root)
    jobs.update_state(job_id, state_root, status="running", heartbeat=time.time() - 121)
    monkeypatch.setattr(jobs, "_identity_alive", lambda identity, jid: True)
    state = jobs.status_job(job_id, state_root)
    assert state["unresponsive"] is True
    assert state["interrupted"] is False
    assert state["phase"] == "queued"
    assert state["heartbeat_age"] >= 121
    assert state["artifact_paths"]["manifest.txt"].endswith("manifest.txt")


def test_os_locks_enforce_three_active_slots(tmp_path: Path) -> None:
    locks = [jobs.FileLock(tmp_path / "slots" / f"slot-{i}.lock", blocking=False) for i in range(1, 4)]
    for lock in locks:
        lock.__enter__()
    try:
        for number in range(1, 4):
            script = "\n".join([
                "import sys",
                "from pathlib import Path",
                "from tools.fleet_jobs import FileLock",
                "try:",
                "    lock = FileLock(Path(sys.argv[1]), blocking=False)",
                "    lock.__enter__()",
                "    lock.__exit__(None, None, None)",
                "except OSError:",
                "    sys.exit(0)",
                "sys.exit(1)",
            ])
            result = subprocess.run(
                [sys.executable, "-c", script, str(tmp_path / "slots" / f"slot-{number}.lock")],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, check=False,
            )
            assert result.returncode == 0, result.stderr.decode(errors="replace")
    finally:
        for lock in reversed(locks):
            lock.__exit__(None, None, None)
    # The same three OS locks represent the supervisor's bounded slot pool.


def test_git_inspection_retries_once_and_retains_failure_reason(tmp_path, monkeypatch) -> None:
    calls = []

    def transient(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1 if len(calls) == 1 else 0, b"", b"temporary read failure")

    monkeypatch.setattr(jobs.subprocess, "run", transient)
    monkeypatch.setattr(jobs.time, "sleep", lambda _: None)
    assert jobs._git_inspection(tmp_path, ["status"]).returncode == 0
    assert len(calls) == 2
    calls.clear()
    monkeypatch.setattr(jobs.subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1, b"", b"persistent read failure"))
    with pytest.raises(jobs.JobError, match="persistent read failure"):
        jobs._git_inspection(tmp_path, ["status"])


def test_scope_check_is_exact_and_patch_contains_untracked_files(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "src" / "main.py").write_text("value = 2\n", encoding="utf-8")
    (repo / "src" / "new.py").write_text("new_value = 3\n", encoding="utf-8")
    changes = jobs._repo_changes(repo)
    assert set(changes) == {"src/main.py", "src/new.py"}
    assert all(jobs._within_allowed(name, ["src/main.py", "src/new.py"]) for name in changes)
    assert not jobs._within_allowed("src/main.py/extra.py", ["src/main.py"])
    payload = jobs._capture_patch(repo, tmp_path / "job")
    encoded = payload["untracked_files_base64"]["src/new.py"]
    assert base64.b64decode(encoded).decode().replace("\r\n", "\n") == "new_value = 3\n"
    assert base64.b64decode(payload["diff_binary_base64"]) == b""


def test_binary_diff_and_scope_capture_use_original_base_without_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = make_repo(tmp_path)
    original_run = subprocess.run

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if args[:3] == ["git", "diff", "--binary"]:
            return subprocess.CompletedProcess(args, 0, b"binary-diff-from-base", b"")
        if args[:3] == ["git", "diff", "--name-only"]:
            return subprocess.CompletedProcess(args, 0, b"src/main.py\0", b"")
        if args[:2] == ["git", "ls-files"]:
            return subprocess.CompletedProcess(args, 0, b"src/main.py", b"")
        return original_run(args, **kwargs)

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)
    changes = jobs._repo_changes(repo, "immutable-base")
    assert changes == ["src/main.py"]
    assert supervisor._out_of_scope(repo, ["src/main.py"], changes) == []
    patch = jobs._capture_patch(repo, tmp_path / "binary-job", "immutable-base")
    assert base64.b64decode(patch["diff_binary_base64"]) == b"binary-diff-from-base"


def test_resume_requires_interruption_and_allows_only_one_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", make_spec(repo)), state_root=state_root)
    jobs.update_state(job_id, state_root, status="running")
    monkeypatch.setattr(jobs, "_identity_alive", lambda identity, jid: False)
    assert jobs.resume_job(job_id, state_root) == job_id
    assert jobs.read_state(job_id, state_root)["attempt"] == 2
    with pytest.raises(jobs.JobError, match="retry limit"):
        jobs.resume_job(job_id, state_root)


def test_cancel_without_supervisor_kills_verified_orphan_worker_before_finalizing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", make_spec(repo)), state_root=state_root)
    worker = {"pid": 92, "create_time": 1, "command": ["python"], "job_id": job_id}
    jobs.update_state(job_id, state_root, status="running", worker=worker)
    monkeypatch.setattr(jobs, "_identity_alive", lambda identity, jid: identity == worker)
    killed: list[object] = []

    def kill_tree(identity: object, jid: str, tree: object = None) -> bool:
        killed.append(identity)
        return True

    monkeypatch.setattr(jobs, "kill_verified_tree", kill_tree)
    monkeypatch.setattr(jobs, "_recorded_worker_alive", lambda state, jid: False)
    result = jobs.cancel_job(job_id, state_root)
    assert killed == [worker]
    assert result["status"] == "cancelled"


@pytest.mark.parametrize("status", ["failed", "timed_out"])
def test_resume_allows_one_retry_after_terminal_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", make_spec(repo)), state_root=state_root)
    initial = jobs.read_state(job_id, state_root)
    worktree = str(repo / ".worktrees" / "preserved")
    jobs.update_state(
        job_id, state_root, status=status, summary="prior failure",
        worktree=worktree, test_evidence=[{"exit_code": 7}],
    )
    assert jobs.resume_job(job_id, state_root) == job_id
    state = jobs.read_state(job_id, state_root)
    assert state["attempt"] == 2
    assert state["summary"] == "prior failure"
    assert state["worktree"] == worktree
    assert state["overall_deadline"] == initial["overall_deadline"]
    assert state["retry_feedback"]["test_evidence"] == [{"exit_code": 7}]
    with pytest.raises(jobs.JobError, match="retry limit"):
        jobs.resume_job(job_id, state_root)


@pytest.mark.parametrize("status", ["completed", "cancelled"])
def test_resume_rejects_completed_or_cancelled_jobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", make_spec(repo)), state_root=state_root)
    jobs.update_state(job_id, state_root, status=status)
    with pytest.raises(jobs.JobError, match="interrupted"):
        jobs.resume_job(job_id, state_root)


def test_resume_rejects_live_process_and_mutated_spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", make_spec(repo)), state_root=state_root)
    jobs.update_state(job_id, state_root, status="running", supervisor={"job_id": job_id, "pid": 12})
    monkeypatch.setattr(jobs, "_identity_alive", lambda identity, jid: True)
    with pytest.raises(jobs.JobError, match="interrupted"):
        jobs.resume_job(job_id, state_root)
    monkeypatch.setattr(jobs, "_identity_alive", lambda identity, jid: False)
    (jobs.job_dir(job_id, state_root) / "spec.json").write_text("{}")
    with pytest.raises(jobs.JobError, match="integrity"):
        jobs.resume_job(job_id, state_root)


def test_result_correlates_exact_job_and_rejects_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    first = jobs.start_job(write_spec(tmp_path / "one.json", make_spec(repo)), state_root=state_root)
    second = jobs.start_job(write_spec(tmp_path / "two.json", make_spec(repo)), state_root=state_root)
    (jobs.job_dir(first, state_root) / "manifest.txt").write_text("first", encoding="utf-8")
    (jobs.job_dir(second, state_root) / "manifest.txt").write_text("second", encoding="utf-8")
    assert jobs.result_job(first, state_root)["result"]["manifest.txt"] == "first"
    with pytest.raises(jobs.JobError, match="Invalid job ID"):
        jobs.result_job("../latest", state_root)


def test_cancel_is_cooperative_and_pid_reuse_is_not_signalled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", make_spec(repo)), state_root=state_root)
    jobs.update_state(job_id, state_root, status="running", supervisor={"pid": 4321, "create_time": 1, "command": [], "job_id": job_id})
    monkeypatch.setattr(jobs, "_identity_alive", lambda identity, jid: False)
    state = jobs.cancel_job(job_id, state_root)
    assert state["status"] == "cancelled"
    assert state["cancel_requested"] is True


def test_resume_rejects_live_worker_when_supervisor_is_dead(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", make_spec(repo)), state_root=state_root)
    worker = {"pid": 90, "create_time": 1, "command": ["python"], "job_id": job_id}
    jobs.update_state(
        job_id, state_root, status="failed",
        supervisor={"pid": 91, "create_time": 1, "command": ["supervisor", job_id], "job_id": job_id},
        worker=worker,
    )
    monkeypatch.setattr(jobs, "_identity_alive", lambda identity, jid: identity == worker)
    with pytest.raises(jobs.JobError, match="worker"):
        jobs.resume_job(job_id, state_root)


def test_pid_reuse_fails_creation_time_and_command_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    class ReusedProcess:
        def create_time(self) -> float:
            return 200.0

        def cmdline(self) -> list[str]:
            return ["unrelated-process"]

    class PsutilStub:
        @staticmethod
        def Process(pid: int) -> ReusedProcess:
            assert pid == 4321
            return ReusedProcess()

    monkeypatch.setitem(sys.modules, "psutil", PsutilStub)
    identity = {"pid": 4321, "create_time": 100.0, "command": ["job"], "job_id": "job-" + "a" * 32}
    assert jobs._identity_alive(identity, identity["job_id"]) is False
    assert jobs.kill_verified_tree(identity, identity["job_id"]) is False


def test_directly_launched_process_identity_requires_exact_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DirectProcess:
        def create_time(self) -> float:
            return 50.0

        def cmdline(self) -> list[str]:
            return ["python.exe", "-c", "pass"]

    class PsutilStub:
        @staticmethod
        def Process(pid: int) -> DirectProcess:
            assert pid == 4455
            return DirectProcess()

    monkeypatch.setitem(sys.modules, "psutil", PsutilStub)
    job_id = "job-" + "7" * 32
    identity = {
        "pid": 4455, "create_time": 50.0, "command": ["python.exe", "-c", "pass"],
        "job_id": job_id, "direct_launch": True,
    }
    assert jobs._identity_alive(identity, job_id) is True
    identity["command"] = ["python.exe", "-c", "other"]
    assert jobs._identity_alive(identity, job_id) is False


def test_orphan_descendant_is_killed_only_after_exact_identity_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    killed: list[int] = []

    class PsutilError(Exception):
        pass

    class NoSuchProcess(PsutilError):
        pass

    class Child:
        pid = 4333

        def create_time(self) -> float:
            return 30.0

        def cmdline(self) -> list[str]:
            return ["python", "-c", "child"]

        def kill(self) -> None:
            killed.append(self.pid)

    child = Child()
    psutil_error = PsutilError
    no_such_process = NoSuchProcess

    class PsutilStub:
        Error = psutil_error
        NoSuchProcess = no_such_process

        @staticmethod
        def Process(pid: int):
            if pid == 4321:
                raise NoSuchProcess()
            assert pid == child.pid
            return child

    monkeypatch.setitem(sys.modules, "psutil", PsutilStub)
    job_id = "job-" + "a" * 32
    supervisor_id = {
        "pid": 4321, "create_time": 20.0, "command": ["supervisor", job_id],
        "job_id": job_id,
    }
    descendant = {
        "pid": child.pid, "create_time": 30.0, "command": child.cmdline(),
        "parent_pid": 4321, "parent_create_time": 20.0, "job_id": job_id,
    }
    assert jobs.kill_verified_tree(supervisor_id, job_id, [descendant]) is True
    assert killed == [child.pid]

    killed.clear()
    reused = {**descendant, "create_time": 29.0}
    assert jobs.kill_verified_tree(supervisor_id, job_id, [reused]) is False
    assert killed == []


def test_redaction_covers_known_tokens_and_provider_patterns() -> None:
    token = "".join(("github_pat_", "a" * 32))
    text = f"bad {token} and " + "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
    redacted = jobs._redact(text, [token])
    assert token not in redacted
    assert "abcdefghijklmnopqrstuvwxyz123456" not in redacted
    assert redacted.count("[REDACTED]") == 2


def test_finish_job_preserves_artifacts_and_keeps_verification_separate(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    job_id = "job-" + "b" * 32
    directory = jobs.job_dir(job_id, state_root)
    directory.mkdir(parents=True)
    spec = jobs.validate_spec(make_spec(repo))
    spec_text = json.dumps(spec)
    (directory / "spec.json").write_text(spec_text, encoding="utf-8")
    jobs.atomic_json(directory / "state.json", {
        "job_id": job_id, "spec_sha256": hashlib.sha256(spec_text.encode()).hexdigest(),
        "status": "running", "verification": "unverified", "worktree": None,
    })
    state = jobs.finish_job(job_id, state_root, "completed", "Worker succeeded without test evidence")
    assert state["status"] == "completed"
    assert state["verification"] == "unverified"
    assert state["usage"] == {"model": None, "tokens": None, "credits": None}
    assert (directory / "manifest.txt").is_file()
    assert (directory / "patch.json").is_file()
    assert (directory / "test_evidence.json").is_file()
    assert len((directory / "manifest.txt").read_text().split()) <= 300


def test_actual_usage_only_and_environment_secret_stripping(monkeypatch: pytest.MonkeyPatch) -> None:
    assert supervisor._usage_summary({}) == {"model": None, "tokens": None, "credits": None}
    assert supervisor._usage_summary({
        "model": "model-x", "total_tokens": 4, "totalNanoAiu": 2_000_000_000,
    }) == {"model": "model-x", "tokens": 4, "credits": 2.0}
    monkeypatch.setenv("GOOGLE_API_KEY", "google-secret")
    monkeypatch.setenv("COPILOT_ACCOUNT_1_TOKEN", "copilot-token")
    monkeypatch.setenv("COPILOT_ACCOUNT_1_NAME", "personal-account")
    monkeypatch.setenv("FLEET_JOB_ACCOUNTS", '[{"worker_id":"w1","token":"pool-token"}]')
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "C:\\hooks")
    clean = supervisor._sanitized_environment("chosen-token")
    assert "GOOGLE_API_KEY" not in clean
    assert "COPILOT_ACCOUNT_1_TOKEN" not in clean
    assert "COPILOT_ACCOUNT_1_NAME" not in clean
    assert "FLEET_JOB_ACCOUNTS" not in clean
    assert not any(key.startswith("GIT_CONFIG_") for key in clean)
    assert clean["COPILOT_GITHUB_TOKEN"] == "chosen-token"


def test_account_lock_skips_busy_worker_and_honors_explicit_worker_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    accounts = [
        {"worker_id": "w1", "token": "first"},
        {"worker_id": "w2", "token": "second"},
    ]
    job_id = "job-" + "f" * 32
    directory = jobs.job_dir(job_id, tmp_path)
    directory.mkdir(parents=True)
    jobs.atomic_json(directory / "state.json", {
        "job_id": job_id, "status": "running", "cancel_requested": False,
    })
    monkeypatch.setattr(supervisor, "_configured_accounts", lambda: accounts)
    busy = jobs.FileLock(tmp_path / ".account-locks" / "w1.lock", blocking=False)
    busy.__enter__()
    try:
        worker, token, lock = asyncio.run(supervisor._select_locked_account(
            None, tmp_path, job_id, time.monotonic() + 2,
        ))
        try:
            assert (worker, token) == ("w2", "second")
        finally:
            lock.__exit__(None, None, None)
        with pytest.raises(jobs.JobError, match="No configured Copilot account"):
            asyncio.run(supervisor._select_locked_account(
                "missing", tmp_path, job_id, time.monotonic() + 2,
            ))
    finally:
        busy.__exit__(None, None, None)
    worker, token, lock = asyncio.run(supervisor._select_locked_account(
        "w2", tmp_path, job_id, time.monotonic() + 2,
    ))
    try:
        assert (worker, token) == ("w2", "second")
    finally:
        lock.__exit__(None, None, None)


@pytest.mark.parametrize("cancel", [False, True])
def test_test_command_obeys_supervisor_timeout_and_cancel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cancel: bool,
) -> None:
    import asyncio
    from tools import fleet_job_supervisor as supervisor

    job_id = "job-" + "c" * 32
    state_root = tmp_path / "jobs"
    directory = jobs.job_dir(job_id, state_root)
    directory.mkdir(parents=True)
    jobs.atomic_json(directory / "state.json", {
        "job_id": job_id, "status": "running", "verification": "unverified",
        "heartbeat": time.time(), "job_started_at": time.time(),
        "cancel_requested": cancel,
    })
    stopped: list[str] = []

    class MockProcess:
        pid = 12345
        returncode = 1

        def __init__(self) -> None:
            self.done = asyncio.Event()

        async def communicate(self) -> tuple[bytes, bytes]:
            await self.done.wait()
            return b"", b""

        def kill(self) -> None:
            self.done.set()

    process = MockProcess()

    async def create_exec(*args: object, **kwargs: object) -> MockProcess:
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_exec)
    monkeypatch.setattr(
        jobs, "_process_identity",
        lambda pid, jid, **kwargs: {"pid": pid, "create_time": 1, "command": ["python", "test"], "exact_command": True, "job_id": jid},
    )
    async def kill_tree(identity: object, jid: str, tree: object = None) -> None:
        stopped.append(jid)

    monkeypatch.setattr(supervisor, "_kill_verified_tree", kill_tree)
    monkeypatch.setattr(supervisor, "_sanitized_environment", lambda token: {})
    spec = {
        "overall_deadline": time.time() + (30 if cancel else 0.05),
        "timeout_seconds": 30,
    }
    result = asyncio.run(supervisor._run_test_command(
        job_id, state_root, tmp_path, ["python", "test"], spec, [],
    ))
    assert (result.get("cancelled") is True) == cancel
    assert (result.get("timed_out") is True) == (not cancel)
    assert stopped == [job_id]


def test_test_argv_preserves_failure_exit_code_and_exact_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    job_id = "job-" + "d" * 32
    state_root = tmp_path / "jobs"
    directory = jobs.job_dir(job_id, state_root)
    directory.mkdir(parents=True)
    jobs.atomic_json(directory / "state.json", {
        "job_id": job_id, "status": "running", "verification": "unverified",
        "heartbeat": time.time(), "job_started_monotonic": time.monotonic(),
        "cancel_requested": False,
    })
    spec = {"overall_deadline": time.time() + 30, "timeout_seconds": 20}
    argv = [sys.executable, "-c", "import sys; sys.exit(7)"]
    result = asyncio.run(supervisor._run_test_command(
        job_id, state_root, tmp_path, argv, spec, [],
    ))
    assert result["command"] == argv
    assert result["exit_code"] == 7
    assert jobs.read_state(job_id, state_root)["worker"] is None


def test_exit_seven_test_is_persisted_as_failed_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import client.adapters.copilot_cli_adapter as adapter_module

    repo = make_repo(tmp_path)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "base"],
        cwd=repo, check=True, capture_output=True,
    )
    state_root = tmp_path / "jobs"
    spec = make_spec(repo, timeout_seconds=30, test_commands=[
        [sys.executable, "-c", "import sys; sys.exit(7)"],
    ])
    monkeypatch.setattr(jobs, "_launch_supervisor", lambda job_id, root: job_id)
    job_id = jobs.start_job(write_spec(tmp_path / "spec.json", spec), state_root=state_root)

    class FakeAdapter:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def execute_task(self, *args: object) -> dict[str, object]:
            return {"success": True, "summary": "mocked provider success"}

    class AccountLock:
        def __exit__(self, *args: object) -> None:
            pass

    async def select_account(worker_id: str | None, root: Path, jid: str, deadline: float):
        return "w1", "never-a-real-token", AccountLock()

    monkeypatch.setattr(adapter_module, "CopilotCLIAdapter", FakeAdapter)
    monkeypatch.setattr(supervisor, "_select_locked_account", select_account)
    old_stdout, old_stderr = sys.stdout, sys.stderr
    old_environment = os.environ.copy()
    try:
        asyncio.run(supervisor._run_guarded(job_id, state_root))
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
        os.environ.clear()
        os.environ.update(old_environment)
    state = jobs.read_state(job_id, state_root)
    evidence = json.loads(
        (jobs.job_dir(job_id, state_root) / "test_evidence.json").read_text(encoding="utf-8"),
    )["commands"]
    assert state["status"] == "failed"
    assert state["verification"] == "failed"
    assert evidence[0]["exit_code"] == 7
    assert evidence[0]["command"] == spec["test_commands"][0]


def test_supervisor_startup_handles_initial_null_supervisor_and_terminalizes_without_account(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    state_root = tmp_path / "jobs"
    state_root.mkdir()
    job_id = "job-" + "e" * 32
    directory = jobs.job_dir(job_id, state_root)
    directory.mkdir()
    spec = jobs.validate_spec(make_spec(repo))
    spec_text = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    (directory / "spec.json").write_text(spec_text, encoding="utf-8")
    jobs.atomic_json(directory / "state.json", {
        "job_id": job_id, "spec_sha256": hashlib.sha256(spec_text.encode()).hexdigest(),
        "status": "queued", "verification": "unverified", "created_at": time.time(),
        "updated_at": time.time(), "heartbeat": time.time(), "attempt": 1,
        "overall_deadline": spec["overall_deadline"], "cancel_requested": False,
        "supervisor": None, "worker": None, "worktree": None, "summary": "",
        "test_evidence": [], "usage": {"model": None, "tokens": None, "credits": None},
    })
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("COPILOT_ACCOUNT_") or key in {
            "COPILOT_GITHUB_TOKEN", "FLEET_JOB_ACCOUNTS", "FLEET_JOB_WORKER_ID",
        }:
            env.pop(key, None)
    env["FLEET_JOB_ACCOUNTS"] = "[]"
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "tools.fleet_job_supervisor",
            "--job-id", job_id, "--state-root", str(state_root),
        ],
        cwd=Path(__file__).resolve().parents[1], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    state = jobs.read_state(job_id, state_root)
    state["supervisor"] = jobs._process_identity(proc.pid, job_id)
    jobs.atomic_json(directory / "state.json", state)
    try:
        proc.wait(timeout=20)
        state = jobs.read_state(job_id, state_root)
        assert state["status"] == "failed"
        assert state["patch_present"] is True
        assert (directory / "patch.json").is_file()
        assert (directory / "test_evidence.json").is_file()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_supervisor_marks_expired_queued_spec_timed_out(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    raw_spec = make_spec(repo, overall_deadline=time.time() - 1)
    spec_text = json.dumps(raw_spec, indent=2, sort_keys=True) + "\n"
    state_root = tmp_path / "jobs"
    state_root.mkdir()
    job_id = "job-" + "9" * 32
    directory = jobs.job_dir(job_id, state_root)
    directory.mkdir()
    (directory / "spec.json").write_text(spec_text, encoding="utf-8")
    jobs.atomic_json(directory / "state.json", {
        "job_id": job_id, "spec_sha256": hashlib.sha256(spec_text.encode()).hexdigest(),
        "status": "queued", "verification": "unverified", "created_at": time.time(),
        "updated_at": time.time(), "heartbeat": time.time(), "attempt": 1,
        "overall_deadline": raw_spec["overall_deadline"], "cancel_requested": False,
        "supervisor": None, "worker": None, "worktree": None, "summary": "",
        "test_evidence": [], "usage": {"model": None, "tokens": None, "credits": None},
    })
    env = os.environ.copy()
    env["FLEET_JOB_ACCOUNTS"] = "[]"
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "tools.fleet_job_supervisor",
            "--job-id", job_id, "--state-root", str(state_root),
        ],
        cwd=Path(__file__).resolve().parents[1], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    state = jobs.read_state(job_id, state_root)
    state["supervisor"] = jobs._process_identity(proc.pid, job_id)
    jobs.atomic_json(directory / "state.json", state)
    try:
        proc.wait(timeout=10)
        assert jobs.read_state(job_id, state_root)["status"] == "timed_out"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_expired_deadline_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    with pytest.raises(jobs.JobError, match="overall_deadline"):
        jobs.validate_spec(make_spec(repo, overall_deadline=time.time() - 1))


def test_job_id_regex_and_batch_route() -> None:
    with pytest.raises(jobs.JobError):
        jobs.job_dir("../../bad")
    wrapper = (Path(__file__).resolve().parents[1] / "fleet.bat").read_text(encoding="utf-8")
    assert 'if /I "%~1"=="job" goto :fleet_job' in wrapper
    assert "tools\\fleet_jobs.py" in wrapper


def test_direct_fleet_job_list_works_outside_repository(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "fleet_jobs.py"), "list", "--json"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert isinstance(json.loads(result.stdout), list)
