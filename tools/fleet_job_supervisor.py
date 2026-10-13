"""Hidden per-job controller; invoked only by ``tools.fleet_jobs``."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tools import fleet_jobs as jobs

LOG_SECRETS: list[str] = []


class RedactingStream:
    def __init__(self, stream: Any, secrets: list[str]):
        self.stream = stream
        self.secrets = secrets
        self.pending = ""

    def write(self, text: str) -> int:
        self.pending += text
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            self.stream.write(jobs._redact(line + "\n", self.secrets))
        return len(text)

    def flush(self) -> None:
        if self.pending:
            self.stream.write(jobs._redact(self.pending, self.secrets))
            self.pending = ""
        self.stream.flush()


def _sanitized_environment(token: str) -> dict[str, str]:
    blocked = re.compile(
        r"(?:KEY|TOKEN|SECRET|CREDENTIAL)",
        re.I,
    )
    env = {
        key: value for key, value in os.environ.items()
        if (
            not blocked.search(key)
            and not key.startswith(("COPILOT_ACCOUNT_", "GIT_CONFIG_"))
        )
    }
    env.pop("COPILOT_GITHUB_TOKEN", None)
    env.pop("FLEET_JOB_WORKER_ID", None)
    env.pop("FLEET_JOB_ACCOUNTS", None)
    if token:
        env["COPILOT_GITHUB_TOKEN"] = token
    return env


def _configured_accounts() -> list[dict[str, str]]:
    encoded = os.environ.get("FLEET_JOB_ACCOUNTS")
    if encoded:
        try:
            raw = json.loads(encoded)
        except json.JSONDecodeError as exc:
            raise jobs.JobError("Configured Copilot accounts are unavailable") from exc
        if not isinstance(raw, list):
            raise jobs.JobError("Configured Copilot accounts are unavailable")
        accounts = [
            {"worker_id": str(item["worker_id"]), "token": str(item["token"])}
            for item in raw
            if isinstance(item, dict) and item.get("worker_id") and item.get("token")
        ]
        if any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", a["worker_id"]) for a in accounts):
            raise jobs.JobError("Configured Copilot account has an invalid worker ID")
        return accounts
    original = dict(os.environ)
    try:
        from tools.copilot_fleet import discover_accounts, load_env_fleet
        loaded = load_env_fleet()
        accounts = discover_accounts(loaded)
    finally:
        os.environ.clear()
        os.environ.update(original)
    accounts = [
        {"worker_id": str(account["worker_id"]), "token": str(account["token"])}
        for account in accounts
        if account.get("has_token") and account.get("worker_id") and account.get("token")
    ]
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", a["worker_id"]) for a in accounts):
        raise jobs.JobError("Configured Copilot account has an invalid worker ID")
    return accounts


async def _select_locked_account(
    worker_id: str | None,
    root: Path,
    job_id: str,
    deadline_monotonic: float,
) -> tuple[str, str, jobs.FileLock]:
    accounts = _configured_accounts()
    if worker_id:
        accounts = [account for account in accounts if account["worker_id"] == worker_id]
    if not accounts:
        raise jobs.JobError("No configured Copilot account is available for this job")
    while time.monotonic() < deadline_monotonic:
        state = jobs.read_state(job_id, root)
        if state.get("cancel_requested"):
            raise jobs.JobError("Job cancelled while waiting for an available Copilot account")
        for account in accounts:
            lock = jobs.FileLock(
                root / ".account-locks" / f"{account['worker_id']}.lock",
                blocking=False,
            )
            try:
                lock.__enter__()
                return account["worker_id"], account["token"], lock
            except (OSError, BlockingIOError):
                continue
        await asyncio.sleep(0.25)
    raise jobs.JobTimeoutError("Execution timeout expired waiting for an available Copilot account")


def _heartbeat(job_id: str, root: Path, **fields: Any) -> None:
    with jobs.state_lock(job_id, root):
        state = jobs.read_state(job_id, root)
        if state["status"] in jobs.TERMINAL:
            return
        state.update(fields)
        def merge_tree(key: str, latest: list[dict[str, Any]]) -> list[dict[str, Any]]:
            known = {
                (item.get("pid"), item.get("create_time")): item
                for item in state.get(key, [])
                if isinstance(item, dict)
            }
            known.update({
                (item.get("pid"), item.get("create_time")): item
                for item in latest
            })
            return list(known.values())

        worker = state.get("worker")
        if worker:
            state["worker_tree"] = merge_tree(
                "worker_tree", jobs._snapshot_process_tree(worker, job_id),
            )
        if (state.get("supervisor") or {}).get("pid") == os.getpid():
            state["supervisor_tree"] = merge_tree(
                "supervisor_tree",
                jobs._snapshot_process_tree(state["supervisor"], job_id),
            )
        state["heartbeat"] = time.time()
        state["updated_at"] = time.time()
        jobs.atomic_json(jobs.job_dir(job_id, root) / "state.json", state)


def _usage_summary(usage_data: Any) -> dict[str, Any]:
    if not isinstance(usage_data, dict):
        usage_data = {}
    tokens = usage_data.get("total_tokens", usage_data.get("tokens"))
    details = usage_data.get("tokenDetails")
    if tokens is None and isinstance(details, dict):
        counts = []
        for name in ("input", "output", "cache_read"):
            entry = details.get(name)
            if isinstance(entry, dict) and isinstance(entry.get("tokenCount"), (int, float)):
                counts.append(entry["tokenCount"])
        tokens = sum(counts) if counts else None
    credits = usage_data.get("totalPremiumRequestCost")
    if credits is None:
        credits = usage_data.get("credits_used", usage_data.get("ai_credits_used"))
    if credits is None and isinstance(usage_data.get("totalNanoAiu"), (int, float)):
        credits = round(usage_data["totalNanoAiu"] / 1_000_000_000, 2)
    return {
        "model": usage_data.get("currentModel") or usage_data.get("model"),
        "tokens": tokens,
        "credits": credits,
    }


def _git_head(repo: Path) -> str:
    result = jobs._git_inspection(repo, ["rev-parse", "--verify", "HEAD"])
    return result.stdout.decode("ascii").strip()


def _out_of_scope(worktree: Path, allowed_files: list[str], changes: list[str]) -> list[str]:
    escaped = []
    for name in changes:
        path = worktree.joinpath(*jobs.PurePosixPath(name).parts)
        if not jobs._within_allowed(name, allowed_files):
            escaped.append(name)
        elif not path.is_symlink() and not path.resolve().is_relative_to(worktree.resolve()):
            escaped.append(name)
    return escaped


async def _run_test_command(
    job_id: str,
    root: Path,
    worktree: Path,
    command: list[str],
    spec: dict[str, Any],
    secrets: list[str],
    deadline_monotonic: float | None = None,
) -> dict[str, Any]:
    if deadline_monotonic is None:
        deadline_monotonic = time.monotonic() + max(0, spec["overall_deadline"] - time.time())
    env = _sanitized_environment("")
    proc = await asyncio.create_subprocess_exec(
        *command, cwd=worktree, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    identity: dict[str, Any] | None = None
    try:
        identity = jobs._process_identity(proc.pid, job_id, allow_unmarked=True)
    except Exception as exc:
        import psutil
        if not isinstance(exc, psutil.NoSuchProcess):
            proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()
            raise
        await proc.wait()
    try:
        _heartbeat(job_id, root, worker=identity, phase="verifying")
    except Exception:
        proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        raise
    evidence = list(jobs.read_state(job_id, root).get("test_evidence", []))
    evidence.append({
        "command": command, "exit_code": None, "running": True,
        "started_at": time.time(),
    })
    _heartbeat(job_id, root, test_evidence=evidence)
    communication = asyncio.create_task(proc.communicate())
    last_heartbeat = time.monotonic()
    cancel_deadline: float | None = None
    completed = False
    try:
        while not communication.done():
            state = jobs.read_state(job_id, root)
            now = time.monotonic()
            started = float(state.get("job_started_monotonic", now))
            expired = (
                now >= deadline_monotonic
                or now - started >= float(spec["timeout_seconds"])
            )
            if state.get("cancel_requested") and cancel_deadline is None:
                cancel_deadline = now + 10
            reason = (
                "timed_out" if expired
                else "cancelled" if cancel_deadline is not None and now >= cancel_deadline
                else None
            )
            if reason:
                current = jobs.read_state(job_id, root)
                await _kill_verified_tree(identity, job_id, current.get("worker_tree"))
                with contextlib.suppress(Exception):
                    proc.kill()
                with contextlib.suppress(Exception):
                    await communication
                completed = True
                return {
                    "command": command, "exit_code": None, reason: True,
                    "stdout": "", "stderr": "",
                }
            if now - last_heartbeat >= 15:
                _heartbeat(job_id, root, worker=identity, phase="verifying")
                last_heartbeat = now
            await asyncio.sleep(0.2)
        stdout, stderr = await communication
        completed = True
        return {
            "command": command, "exit_code": proc.returncode,
            "stdout": jobs._redact(stdout.decode("utf-8", errors="replace")[-8000:], secrets),
            "stderr": jobs._redact(stderr.decode("utf-8", errors="replace")[-8000:], secrets),
        }
    finally:
        if completed:
            _heartbeat(job_id, root, worker=None)


async def _run(job_id: str, root: Path) -> int:
    directory = jobs.job_dir(job_id, root)
    with (directory / "supervisor.log").open("a", encoding="utf-8") as log:
        secrets = LOG_SECRETS
        sys.stdout = RedactingStream(log, LOG_SECRETS)  # type: ignore[assignment]
        sys.stderr = RedactingStream(log, LOG_SECRETS)  # type: ignore[assignment]
        original = (directory / "spec.json").read_text(encoding="utf-8")
        state = jobs.read_state(job_id, root)
        if hashlib.sha256(original.encode()).hexdigest() != state.get("spec_sha256"):
            raise jobs.JobError("Immutable job spec integrity check failed")
        raw_spec = json.loads(original)
        deadline = raw_spec.get("overall_deadline") if isinstance(raw_spec, dict) else None
        if isinstance(deadline, (int, float)) and not isinstance(deadline, bool) and deadline <= time.time():
            jobs.finish_job(job_id, root, "timed_out", "Overall deadline expired before execution")
            return 0
        spec = jobs.validate_spec(raw_spec)
        if jobs.read_state(job_id, root).get("overall_deadline") != spec["overall_deadline"]:
            raise jobs.JobError("Original overall deadline integrity check failed")
        deadline_monotonic = time.monotonic() + max(0, spec["overall_deadline"] - time.time())
        if deadline_monotonic <= time.monotonic():
            jobs.finish_job(job_id, root, "timed_out", "Overall deadline expired before execution")
            return 0
        if jobs.read_state(job_id, root).get("cancel_requested"):
            jobs.finish_job(job_id, root, "cancelled", "Cancelled before worktree provisioning")
            return 0
        repo = Path(spec["repo_path"])
        worktree = Path(jobs.read_state(job_id, root).get("worktree") or (repo / ".worktrees" / job_id))
        if not worktree.exists():
            branch = f"codex/{job_id}"
            worktree.parent.mkdir(parents=True, exist_ok=True)
            try:
                created = subprocess.run(
                    ["git", "worktree", "add", "-b", branch, str(worktree), "HEAD"],
                    cwd=repo, capture_output=True, text=True, check=False,
                    timeout=max(0.1, deadline_monotonic - time.monotonic()),
                )
            except subprocess.TimeoutExpired:
                jobs.finish_job(job_id, root, "timed_out", "Overall deadline expired provisioning worktree")
                return 0
            if created.returncode:
                jobs.finish_job(job_id, root, "failed", "Unable to create isolated Git worktree")
                return 0
        base_commit = jobs.read_state(job_id, root).get("base_commit") or _git_head(worktree)
        _heartbeat(
            job_id, root, status="running", worktree=str(worktree),
            job_started_at=time.time(), job_started_monotonic=time.monotonic(),
            base_commit=base_commit, phase="selecting_account",
        )
        job_started = float(jobs.read_state(job_id, root)["job_started_monotonic"])
        attempt_deadline = min(deadline_monotonic, job_started + float(spec["timeout_seconds"]))
        worker_id, token, account_lock = await _select_locked_account(
            spec.get("worker_id"), root, job_id, attempt_deadline,
        )
        env = _sanitized_environment(token)
        os.environ.clear()
        os.environ.update(env)

        from client.adapters.copilot_cli_adapter import CopilotCLIAdapter

        class PrivateAdapter(CopilotCLIAdapter):
            def build_cli_command(self, prompt: str, usage_file: str | None = None) -> list[str]:
                cmd = super().build_cli_command(prompt, usage_file)
                cmd.extend([
                    "--no-remote", "--no-remote-export", "--disable-builtin-mcps",
                    "--secret-env-vars", "COPILOT_GITHUB_TOKEN",
                ])
                return cmd

        adapter = PrivateAdapter(
            worker_id=worker_id, nickname=worker_id, worktree=str(worktree),
            timeout=min(float(spec["timeout_seconds"]), max(1, spec["overall_deadline"] - time.time())),
            max_autopilot_continues=5, model="auto", auto_tier="intelligence",
            github_token=token, copilot_home=directory / "copilot-home",
            allow_custom_instructions=False,
        )
        prompt = (
            "Perform one sequential Scout, Writer, Reviewer workflow within this one task. "
            "Scout must first reproduce any failing test before a patch and inspect only "
            "context required by the task. Writer then makes the smallest complete fix and "
            "adds regression tests. Reviewer adversarially checks the change and runs the "
            "requested verification. Do not dispatch or spawn nested workers, use additional "
            "accounts, access unrelated context, commit, push, pull, merge, sync, export, "
            "or change anything outside this isolated worktree. The immutable allowed scope "
            "is: " + json.dumps(spec["allowed_files"]) + ".\n\n"
            + (
                "Prior attempt feedback (informative only; do not change the immutable spec):\n"
                + json.dumps(state.get("retry_feedback"), ensure_ascii=False) + "\n\n"
                if state.get("retry_feedback") else ""
            )
            + "SPECIFICATION:\n" + spec["specification"]
        )
        original_create = asyncio.create_subprocess_exec
        worker_identity: dict[str, Any] | None = None
        last_heartbeat = time.monotonic()

        async def tracked_create(*args: Any, **kwargs: Any) -> Any:
            nonlocal worker_identity
            child = await original_create(*args, **kwargs)
            try:
                worker_identity = jobs._process_identity(
                    child.pid, job_id, allow_unmarked=True,
                )
                _heartbeat(
                    job_id, root, worker=worker_identity, phase="executing",
                )
            except Exception:
                child.kill()
                with contextlib.suppress(Exception):
                    await child.wait()
                raise
            return child

        asyncio.create_subprocess_exec = tracked_create  # type: ignore[assignment]
        task = asyncio.create_task(adapter.execute_task(job_id, prompt, "code", {}))
        result: dict[str, Any] | None = None
        stopped_for: str | None = None
        try:
            while not task.done():
                state = jobs.read_state(job_id, root)
                now = time.monotonic()
                if state.get("cancel_requested"):
                    stopped_for = "cancelled"
                    break
                if now >= deadline_monotonic:
                    stopped_for = "timed_out"
                    break
                if now - float(state.get("job_started_monotonic", now)) >= float(spec["timeout_seconds"]):
                    stopped_for = "timed_out"
                    break
                if now - last_heartbeat >= 15:
                    _heartbeat(job_id, root, phase="executing")
                    last_heartbeat = now
                await asyncio.sleep(0.2)
            if stopped_for:
                current = jobs.read_state(job_id, root)
                await _kill_verified_tree(
                    worker_identity, job_id, current.get("worker_tree"),
                )
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            else:
                result = await task
        finally:
            asyncio.create_subprocess_exec = original_create  # type: ignore[assignment]
            account_lock.__exit__(None, None, None)
        if result:
            print("[WORKER SUMMARY]", jobs._redact(str(result.get("summary") or ""), secrets))
            worker_output = str(result.get("result_text") or "")
            if worker_output:
                print("[WORKER OUTPUT]")
                print(jobs._redact(worker_output[-40000:], secrets))
            worker_error = str(result.get("error") or "")
            if worker_error:
                print("[WORKER ERROR]", jobs._redact(worker_error, secrets))

        base_commit = jobs.read_state(job_id, root).get("base_commit")
        changes = jobs._repo_changes(worktree, base_commit)
        escaped = _out_of_scope(worktree, spec["allowed_files"], changes)
        committed = bool(base_commit and _git_head(worktree) != base_commit)
        evidence = []
        verification = "unverified"
        if stopped_for:
            status = stopped_for
            summary = f"Job {stopped_for} by supervisor"
        elif escaped:
            status, verification = "failed", "failed"
            summary = "Worker changed files outside allowed_files"
        elif committed:
            status, verification = "failed", "failed"
            summary = "Worker created a commit; commits are not accepted"
        elif result and "TIMEOUT" in str(result.get("error", "")).upper():
            status = "timed_out"
            summary = "Copilot worker exceeded its execution timeout"
        elif not result or not result.get("success"):
            status = "failed"
            summary = "Copilot worker failed"
        else:
            status = "completed"
            verification = "unverified"
            summary = str(result.get("summary") or "Copilot worker completed")
            for command in spec["test_commands"]:
                _heartbeat(job_id, root, phase="verifying", verification=verification)
                test = await _run_test_command(
                    job_id, root, worktree, command, spec, secrets, deadline_monotonic,
                )
                evidence.append(test)
                _heartbeat(job_id, root, test_evidence=evidence)
                if test.get("cancelled"):
                    status = "cancelled"
                    break
                if test.get("timed_out"):
                    status, verification = "timed_out", "failed"
                    break
                if test["exit_code"]:
                    status, verification = "failed", "failed"
                    break
                else:
                    verification = "passed"
        changes = jobs._repo_changes(worktree, base_commit)
        escaped = _out_of_scope(worktree, spec["allowed_files"], changes)
        committed = bool(base_commit and _git_head(worktree) != base_commit)
        if escaped:
            status, verification = "failed", "failed"
            summary = "Worker or verification command changed files outside allowed_files"
        elif committed:
            status, verification = "failed", "failed"
            summary = "Worker or verification command created a commit"
            if spec["test_commands"] and verification != "passed" and status != "timed_out":
                summary = "One or more configured test commands failed"
        usage = _usage_summary(result.get("usage_data", {}) if result else {})
        jobs.finish_job(
            job_id, root, status, jobs._redact(summary, secrets), verification,
            evidence, {"usage": usage},
        )
        return 0


async def _kill_verified_tree(
    identity: dict[str, Any] | None,
    job_id: str,
    tree: list[dict[str, Any]] | None = None,
) -> None:
    jobs.kill_verified_tree(identity, job_id, tree)


async def _run_guarded(job_id: str, root: Path) -> int:
    try:
        return await _run(job_id, root)
    except Exception as exc:
        directory = jobs.job_dir(job_id, root)
        state = jobs.read_state(job_id, root)
        cleanup_error = ""
        try:
            await _kill_verified_tree(
                state.get("worker"), job_id, state.get("worker_tree"),
            )
        except jobs.JobError as cleanup_exc:
            cleanup_error = f"; process cleanup incomplete: {cleanup_exc}"
        deadline = state.get("overall_deadline")
        status = (
            "cancelled" if state.get("cancel_requested")
            else "timed_out" if (
                isinstance(exc, jobs.JobTimeoutError)
                or isinstance(deadline, (int, float)) and time.time() >= deadline
            )
            else "failed"
        )
        message = jobs._redact(
            f"Supervisor {status}: {type(exc).__name__}: {exc}{cleanup_error}",
            LOG_SECRETS,
        )
        jobs.finish_job(
            job_id, root, status, message,
            "failed" if status != "cancelled" else "unverified",
        )
        print(message, file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--state-root", type=Path, default=jobs.STATE_ROOT)
    args = parser.parse_args(argv)
    jobs.validate_job_id(args.job_id)
    root = args.state_root
    # Parent creates state and records this exact process identity before releasing us.
    for _ in range(100):
        state = jobs.read_state(args.job_id, root)
        if (state.get("supervisor") or {}).get("pid") == os.getpid():
            break
        time.sleep(0.05)
    else:
        return 2
    # A queued job waits without consuming an active slot; process remains visible.
    queue_state = jobs.read_state(args.job_id, root)
    spec_path = jobs.job_dir(args.job_id, root) / "spec.json"
    try:
        spec_text = spec_path.read_text(encoding="utf-8")
        if hashlib.sha256(spec_text.encode()).hexdigest() != queue_state.get("spec_sha256"):
            jobs.finish_job(args.job_id, root, "failed", "Immutable job spec integrity check failed", "failed")
            return 1
        raw_spec = json.loads(spec_text)
    except (OSError, json.JSONDecodeError, jobs.JobError) as exc:
        jobs.finish_job(
            args.job_id, root, "failed",
            f"Supervisor startup validation failed: {type(exc).__name__}", "failed",
        )
        return 1
    deadline_value = raw_spec.get("overall_deadline") if isinstance(raw_spec, dict) else None
    if deadline_value != queue_state.get("overall_deadline"):
        jobs.finish_job(args.job_id, root, "failed", "Original overall deadline integrity check failed", "failed")
        return 1
    if isinstance(deadline_value, (int, float)) and not isinstance(deadline_value, bool) and deadline_value <= time.time():
        jobs.finish_job(args.job_id, root, "timed_out", "Overall deadline expired before execution")
        return 0
    try:
        configured = _configured_accounts()
        LOG_SECRETS.extend(account["token"] for account in configured)
    except jobs.JobError as exc:
        jobs.finish_job(
            args.job_id, root, "failed",
            f"Supervisor account configuration failed: {type(exc).__name__}", "failed",
        )
        return 1
    deadline_monotonic = time.monotonic() + max(0, queue_state.get("overall_deadline", time.time()) - time.time())
    while time.monotonic() < deadline_monotonic:
        state = jobs.read_state(args.job_id, root)
        if state.get("cancel_requested"):
            jobs.finish_job(args.job_id, root, "cancelled", "Cancelled while queued")
            return 0
        for number in range(1, jobs.MAX_ACTIVE_JOBS + 1):
            try:
                slot = jobs.FileLock(root / ".active-slots" / f"slot-{number}.lock", blocking=False)
                slot.__enter__()
            except (OSError, BlockingIOError):
                continue
            try:
                return asyncio.run(_run_guarded(args.job_id, root))
            finally:
                slot.__exit__(None, None, None)
        _heartbeat(args.job_id, root)
        time.sleep(1)
    jobs.finish_job(args.job_id, root, "timed_out", "Overall deadline expired while queued")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
