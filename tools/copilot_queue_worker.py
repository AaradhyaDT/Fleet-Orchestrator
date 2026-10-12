#!/usr/bin/env python3
"""
Copilot Queue Worker:
Headless background worker connecting GitHub Copilot CLI to orchestrator-state/.
Polls orchestrator-state/tasks/ for kind: "code" and status: "pending",
claims the task using round-robin account rotation across the 27 Copilot workers,
executes non-interactively in an isolated worktree via CopilotCLIAdapter (without --model),
records credit headroom telemetry and auto-cooldowns exhausted accounts,
automatically commits worktree changes and tears down the worktree,
writes orchestrator-state/checkpoints/<task_id>.json, and marks the task "done".
Supports multi-process and in-process concurrency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from client.adapters.copilot_cli_adapter import CopilotCLIAdapter
from tools.copilot_fleet import discover_accounts, load_env_fleet
from tools.credit_ledger import (
    resolve_state_dir,
    next_billing_reset,
    sync_worker_ledger,
    parse_iso_utc,
    atomic_write_json,
    initialize_ledgers,
    FileLock,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [CopilotQueueWorker] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("copilot_queue_worker")

WIN32_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Suppress noisy HTTP client logs from httpx/httpcore
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_pid_alive(pid: int | None) -> bool:
    """Checks whether an OS process ID is currently running."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel32.CloseHandle(handle)
                STILL_ACTIVE = 259
                return exit_code.value == STILL_ACTIVE
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class CopilotQueueWorker:
    def __init__(
        self,
        state_dir: Path | str | None = None,
        poll_interval: float = 5.0,
        dry_run: bool = False,
        worktree_root: Path | str | None = None,
        repo_root: Path | str | None = None,
        auto_worktrees: bool = True,
        concurrency: int = 1,
        worker_id_filter: str | None = None,
    ):
        self.state_dir = resolve_state_dir(str(state_dir) if state_dir else None)
        self.tasks_dir = self.state_dir / "tasks"
        self.checkpoints_dir = self.state_dir / "checkpoints"
        self.live_status_dir = self.state_dir / "live-status"
        self.poll_interval = poll_interval
        self.dry_run = dry_run

        self.repo_root = Path(repo_root).resolve() if repo_root else PROJECT_ROOT
        self.worktree_root = Path(worktree_root).resolve() if worktree_root else (self.repo_root / ".worktrees")
        self.auto_worktrees = auto_worktrees
        self.concurrency = max(1, concurrency)
        self.worker_id_filter = worker_id_filter

        self._ensure_dirs()
        self.env_vars = load_env_fleet()
        self.accounts = discover_accounts(self.env_vars)
        if self.worker_id_filter:
            self.accounts = [a for a in self.accounts if a.get("worker_id") == self.worker_id_filter]
        self.ready_accounts = [a for a in self.accounts if a.get("has_token")]
        self._current_account_idx = 0
        self._running = False

        self.account_credits: dict[str, float] = {}
        self.account_cooldowns: dict[str, datetime] = {}
        self._account_file_mtimes: dict[str, float] = {}
        self._initialize_fleet_status_files()
        self._load_live_status_telemetry()

    def _ensure_dirs(self) -> None:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.live_status_dir.mkdir(parents=True, exist_ok=True)

    def _initialize_fleet_status_files(self) -> None:
        """Ensures all accounts have an initialized live-status file in orchestrator-state."""
        initialize_ledgers(self.state_dir, self.accounts)

    def _load_live_status_telemetry(self) -> None:
        """Loads existing credit telemetry and cooldown state from orchestrator-state/live-status/."""
        if not self.live_status_dir.exists():
            return

        now = datetime.now(timezone.utc)
        for acc in self.accounts:
            wid = acc["worker_id"]
            status_file = self.live_status_dir / f"{wid}.json"
            if status_file.exists():
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "credits_used" in data and isinstance(data["credits_used"], (int, float)):
                        self.account_credits[wid] = float(data["credits_used"])
                    if "cooldown_until" in data and data["cooldown_until"]:
                        exp = parse_iso_utc(data["cooldown_until"])
                        if exp and exp > now:
                            self.account_cooldowns[wid] = exp
                except Exception as e:
                    logger.debug(f"Could not load status for {wid}: {e}")

    def is_in_cooldown(self, worker_id: str) -> bool:
        """Returns True if worker is in active cooldown."""
        # Re-check live status file on disk (cached by mtime) to catch external cooldowns
        status_file = self.live_status_dir / f"{worker_id}.json"
        if status_file.exists():
            try:
                mtime = status_file.stat().st_mtime
                if mtime != self._account_file_mtimes.get(worker_id, 0.0):
                    self._account_file_mtimes[worker_id] = mtime
                    with open(status_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cd = data.get("cooldown_until")
                    if cd:
                        exp = parse_iso_utc(cd)
                        if exp and exp > datetime.now(timezone.utc):
                            self.account_cooldowns[worker_id] = exp
                        else:
                            self.account_cooldowns.pop(worker_id, None)
                    else:
                        self.account_cooldowns.pop(worker_id, None)
            except Exception:
                pass

        exp = self.account_cooldowns.get(worker_id)
        if not exp:
            return False
        if datetime.now(timezone.utc) >= exp:
            del self.account_cooldowns[worker_id]
            return False
        return True

    def mark_cooldown(
        self,
        worker_id: str,
        minutes: int | None = 60,
        *,
        until: datetime | None = None,
        quota_exhausted: bool = False,
        reason: str = "",
    ) -> None:
        """Transitions worker account to cooldown state and updates live-status."""
        now = datetime.now(timezone.utc)
        if until:
            exp = until
        elif quota_exhausted:
            exp = next_billing_reset(now)
        else:
            exp = now + timedelta(minutes=minutes if minutes is not None else 60)

        self.account_cooldowns[worker_id] = exp
        exp_iso = exp.strftime("%Y-%m-%dT%H:%M:%SZ")

        note = f"Cooldown ({minutes}m): {reason}" if minutes else f"Cooldown: {reason}"
        if quota_exhausted:
            note = f"Exhausted: {reason} (Resets {exp.strftime('%Y-%m-%d')})"

        logger.warning(f"Worker {worker_id} placed in COOLDOWN until {exp_iso}. Reason: {reason}")
        self._update_live_status(
            account=worker_id,
            current_task_id=None,
            note=note,
            status="cooldown",
            cooldown_until=exp_iso,
            quota_exhausted=quota_exhausted,
        )

    def record_credit_usage(self, worker_id: str, credits_used: float, session_id: str | None = None) -> float:
        """Records consumed credits and auto-cooldowns when monthly limit reached."""
        acc_dict = None
        for acc in self.accounts:
            if acc.get("worker_id") == worker_id:
                acc_dict = acc
                break

        if not acc_dict:
            acc_dict = {
                "worker_id": worker_id,
                "name": worker_id,
                "monthly_credits": 200,
                "state_dir": Path.home() / ".copilot-workers" / f"worker_{worker_id}",
            }

        # Check if worker_home session-state exists to decide if provisional credits needed
        worker_home = Path(acc_dict.get("state_dir", ""))
        sess_dir = worker_home / "session-state"
        has_real_sessions = sess_dir.exists() and any(sess_dir.glob("*"))

        # If no real session files exist on disk (e.g. test fixture), supply provisional_credits
        prov = credits_used if not has_real_sessions else 0.0

        res = sync_worker_ledger(
            self.state_dir,
            acc_dict,
            provisional_credits=prov,
        )

        current = float(res.get("credits_used", 0.0))
        self.account_credits[worker_id] = current
        limit = acc_dict.get("monthly_credits", 200)

        logger.info(f"Worker {worker_id} credit update: +{credits_used:.2f} used (Total: {current:.2f}/{limit})")
        if res.get("quota_exhausted") or current >= limit:
            self.mark_cooldown(
                worker_id,
                until=next_billing_reset(),
                quota_exhausted=True,
                reason=f"Monthly quota exhausted ({current:.2f}/{limit} credits)",
            )

        return current

    def get_next_account(self) -> dict[str, Any] | None:
        """Round-robin selection across ready Copilot accounts, bypassing accounts in cooldown.
        
        Persists circular selection state across processes and CLI invocations to
        guarantee true circular rotation across all pooled accounts rather than
        restarting at worker 1 on every one-shot task execution.
        """
        if not self.ready_accounts:
            # Fallback to default local worker if no tokens configured
            return {
                "index": 1,
                "worker_id": "copilot-w1",
                "name": "default-local",
                "token": "",
                "has_token": False,
                "monthly_credits": 200,
                "state_dir": Path.home() / ".copilot-workers" / "worker_1_default",
            }

        eligible = [a for a in self.ready_accounts if not self.is_in_cooldown(a["worker_id"])]
        if not eligible:
            logger.warning("All ready Copilot accounts are currently in cooldown.")
            return None

        pointer_file = self.state_dir / "round_robin_pointer.json"
        lock_file = self.state_dir / "round_robin_pointer.lock"

        # Synchronize across concurrent processes via cross-platform OS file lock
        try:
            with FileLock(lock_file):
                last_worker_id = None
                if pointer_file.exists():
                    try:
                        with open(pointer_file, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                            if isinstance(p_data, dict):
                                last_worker_id = p_data.get("last_worker_id")
                    except Exception:
                        pass

                eligible_ids = [a["worker_id"] for a in eligible]
                if last_worker_id and last_worker_id in eligible_ids:
                    next_idx = (eligible_ids.index(last_worker_id) + 1) % len(eligible)
                elif last_worker_id:
                    # If last worker is now in cooldown, find next available eligible worker
                    # following ready_accounts circular ordering
                    ready_ids = [a["worker_id"] for a in self.ready_accounts]
                    if last_worker_id in ready_ids:
                        last_ready_idx = ready_ids.index(last_worker_id)
                        next_idx = 0
                        for offset in range(1, len(ready_ids) + 1):
                            cand_id = ready_ids[(last_ready_idx + offset) % len(ready_ids)]
                            if cand_id in eligible_ids:
                                next_idx = eligible_ids.index(cand_id)
                                break
                    else:
                        next_idx = self._current_account_idx % len(eligible)
                else:
                    next_idx = self._current_account_idx % len(eligible)

                acc = eligible[next_idx]
                self._current_account_idx = next_idx + 1

                # Persist chosen account pointer atomically
                try:
                    atomic_write_json(
                        pointer_file,
                        {
                            "last_worker_id": acc["worker_id"],
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                except Exception as e:
                    logger.warning(f"Could not persist round-robin pointer to {pointer_file}: {e}")

                return acc
        except Exception as e:
            logger.warning(f"Lock acquisition or pointer persistence failed, falling back to in-memory rotation: {e}")
            acc = eligible[self._current_account_idx % len(eligible)]
            self._current_account_idx += 1
            return acc

    def find_pending_code_tasks(self) -> list[dict[str, Any]]:
        """Scans orchestrator-state/tasks for pending code tasks."""
        if not self.tasks_dir.exists():
            return []

        pending_tasks = []
        # Support both canonical task_*.json and legacy TASK-*.json
        task_files = set(self.tasks_dir.glob("task_*.json")) | set(self.tasks_dir.glob("TASK-*.json"))
        for task_file in sorted(task_files, key=lambda p: p.name):
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    # Normalize field aliases for dual compatibility
                    if "id" not in data and "task_id" in data:
                        data["id"] = data["task_id"]
                    if "spec" not in data and "prompt" in data:
                        data["spec"] = data["prompt"]
                    if "kind" not in data:
                        data["kind"] = "code"

                    stage = data.get("current_stage") or data.get("stage") or (data.get("pipeline_stages")[0] if data.get("pipeline_stages") else None)
                    is_eligible = (data.get("kind") == "code") or (stage in ["code", "draft", "research", "format", "refactor", "unit_test"])

                    if is_eligible:
                        status = data.get("status")
                        if status == "pending":
                            pending_tasks.append(data)
                        elif status == "claimed":
                            owner_pid = data.get("owner_pid")
                            if owner_pid and not is_pid_alive(owner_pid):
                                logger.info(f"Reclaiming zombie task {data.get('id')} from dead PID {owner_pid}")
                                data["status"] = "pending"
                                data["owner_account"] = None
                                data["owner_pid"] = None
                                try:
                                    with open(task_file, "w", encoding="utf-8") as f:
                                        json.dump(data, f, indent=2)
                                    pending_tasks.append(data)
                                except Exception:
                                    pass
            except Exception as e:
                logger.warning(f"Error reading task file {task_file.name}: {e}")

        return pending_tasks

    def claim_task(self, task_id: str, account: dict[str, Any]) -> dict[str, Any] | None:
        """
        Optimistically claims a task according to SCHEMA.md contract.
        Uses kernel atomic O_CREAT | O_EXCL claim token plus atomic file replacement
        to guarantee zero double-claims across concurrent OS processes.
        """
        task_path = self.tasks_dir / f"{task_id}.json"
        if not task_path.exists():
            return None

        # Cross-process atomic claim gate
        lock_path = task_path.with_suffix(f".claim_{task_id}")
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except (FileExistsError, OSError):
            # Another worker process is concurrently claiming this task
            return None

        try:
            with open(task_path, "r", encoding="utf-8") as f:
                task = json.load(f)

            if task.get("status") != "pending" or task.get("owner_account") is not None:
                logger.info(f"Task {task_id} was already claimed or is no longer pending.")
                return None

            now = _now_iso()
            task["status"] = "claimed"
            task["owner_account"] = account["worker_id"]
            task["owner_pid"] = os.getpid()
            task["branch_name"] = f"task/{task_id}"
            task["updated_at"] = now

            # Atomic write to avoid partial reads by concurrent processes
            tmp_path = task_path.with_suffix(f".tmp.{os.getpid()}.{task_id}")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(task, f, indent=2)
            os.replace(tmp_path, task_path)

            # Update live-status for the account
            self._update_live_status(
                account=account["worker_id"],
                current_task_id=task_id,
                note=f"Executing code task {task_id}",
                status="busy",
            )

            logger.info(f"Successfully claimed {task_id} for worker {account['worker_id']} ({account['name']})")
            return task
        except Exception as e:
            logger.error(f"Failed to claim task {task_id}: {e}")
            return None
        finally:
            if lock_path.exists():
                try:
                    lock_path.unlink()
                except Exception:
                    pass

    def _update_live_status(
        self,
        account: str,
        current_task_id: str | None,
        note: str,
        status: str = "busy",
        cooldown_until: str | None = None,
        quota_exhausted: bool | None = None,
    ) -> None:
        """Updates live status light in orchestrator-state/live-status/<account>.json."""
        status_file = self.live_status_dir / f"{account}.json"

        # Load fresh values from disk to avoid overwriting harvested credits
        used = round(float(self.account_credits.get(account, 0.0)), 2)
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        limit = 200
        for acc in self.accounts:
            if acc.get("worker_id") == account:
                limit = acc.get("monthly_credits", 200)
                break

        is_quota_ex = quota_exhausted if quota_exhausted is not None else (used >= limit)
        if status_file.exists():
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if d.get("period") == period and "credits_used" in d:
                    used = float(d["credits_used"])
                    self.account_credits[account] = used
                if quota_exhausted is None:
                    is_quota_ex = d.get("quota_exhausted", is_quota_ex)
            except Exception:
                pass

        rem = max(0.0, round(limit - used, 2))
        cd_exp = self.account_cooldowns.get(account)
        cd_iso = cooldown_until or (cd_exp.strftime("%Y-%m-%dT%H:%M:%SZ") if cd_exp else None)

        actual_status = status
        if cd_iso:
            exp_dt = parse_iso_utc(cd_iso)
            if exp_dt and datetime.now(timezone.utc) < exp_dt:
                actual_status = "cooldown"
            else:
                cd_iso = None
                actual_status = "idle" if current_task_id is None else "busy"
        elif current_task_id is None:
            actual_status = "idle"

        data = {
            "account": account,
            "status": actual_status,
            "period": period,
            "current_task_id": current_task_id,
            "credits_used": used,
            "credits_remaining": rem,
            "monthly_credits": limit,
            "quota_exhausted": is_quota_ex,
            "cooldown_until": cd_iso,
            "heartbeat_at": _now_iso(),
            "pid": os.getpid(),
            "note": note,
        }
        try:
            atomic_write_json(status_file, data)
        except Exception as e:
            logger.warning(f"Could not update live-status for {account}: {e}")

    def _is_git_repo(self, path: Path) -> bool:
        """Checks if a path resides inside a Git repository."""
        if not path or not path.exists():
            return False
        git_entry = path / ".git"
        if git_entry.exists():
            return True
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                creationflags=WIN32_NO_WINDOW,
            )
            return res.returncode == 0 and "true" in res.stdout.lower()
        except Exception:
            return False

    async def provision_worktree(
        self,
        task_id: str,
        branch_name: str,
        target_repo: str | Path | None = None,
    ) -> Path:
        """
        Auto-provisions an isolated Git worktree:
        `git worktree add -b task/<task_id> <worktree_dir> HEAD`
        Supports target_repo cross-repository routing and pre-flight worktree self-healing.
        """
        root = Path(target_repo).resolve() if target_repo else self.repo_root
        wt_root = (root / ".worktrees") if target_repo else self.worktree_root
        worktree_dir = wt_root / task_id

        if self.dry_run or not self.auto_worktrees or not self._is_git_repo(root):
            worktree_dir.mkdir(parents=True, exist_ok=True)
            return worktree_dir

        wt_root.mkdir(parents=True, exist_ok=True)

        # 1. Pre-flight Git self-healing: prune stale worktree registrations
        try:
            prune_proc = await asyncio.create_subprocess_exec(
                "git", "worktree", "prune",
                cwd=str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=WIN32_NO_WINDOW,
            )
            await prune_proc.communicate()
        except Exception:
            pass

        # 2. Check if branch is locked to an existing worktree via git worktree list
        try:
            list_proc = await asyncio.create_subprocess_exec(
                "git", "worktree", "list", "--porcelain",
                cwd=str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=WIN32_NO_WINDOW,
            )
            list_out, _ = await list_proc.communicate()
            list_text = list_out.decode("utf-8", errors="replace")
            if f"branch refs/heads/{branch_name}" in list_text:
                for block in list_text.split("\n\n"):
                    if f"branch refs/heads/{branch_name}" in block:
                        for line in block.splitlines():
                            if line.startswith("worktree "):
                                stale_wt = Path(line.replace("worktree ", "").strip())
                                if stale_wt != root and stale_wt.exists():
                                    rm_proc = await asyncio.create_subprocess_exec(
                                        "git", "worktree", "remove", "--force", str(stale_wt),
                                        cwd=str(root),
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE,
                                        creationflags=WIN32_NO_WINDOW,
                                    )
                                    await rm_proc.communicate()
                prune_proc = await asyncio.create_subprocess_exec(
                    "git", "worktree", "prune",
                    cwd=str(root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=WIN32_NO_WINDOW,
                )
                await prune_proc.communicate()
        except Exception as e:
            logger.debug(f"Pre-flight worktree self-healing notice: {e}")

        # 3. Clean up directory on disk if it still exists
        if worktree_dir.exists():
            await self.teardown_worktree(worktree_dir, branch_name=None, commit=False, repo_root=root)

        # 4. Check if branch already exists
        check_proc = await asyncio.create_subprocess_exec(
            "git", "branch", "--list", branch_name,
            cwd=str(root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=WIN32_NO_WINDOW,
        )
        out, _ = await check_proc.communicate()
        branch_exists = bool(branch_name.strip() and branch_name in out.decode("utf-8", errors="replace"))

        cmd = ["git", "worktree", "add"]
        if branch_exists:
            cmd.extend([str(worktree_dir), branch_name])
        else:
            cmd.extend(["-b", branch_name, str(worktree_dir), "HEAD"])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=WIN32_NO_WINDOW,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            logger.warning(
                f"git worktree add returned {proc.returncode}: {err.decode('utf-8', errors='replace')}. "
                "Falling back to plain directory."
            )
            worktree_dir.mkdir(parents=True, exist_ok=True)

        return worktree_dir

    async def teardown_worktree(
        self,
        worktree_dir: Path,
        branch_name: str | None = None,
        task_id: str | None = None,
        commit: bool = True,
        prune_branch: bool = False,
        repo_root: Path | str | None = None,
    ) -> str | None:
        """
        Automatically commits changes inside the worktree (if any),
        records the commit SHA, and cleans up the worktree.
        """
        commit_sha = None
        if not worktree_dir.exists():
            return None

        root = Path(repo_root).resolve() if repo_root else self.repo_root
        is_git = self._is_git_repo(worktree_dir)

        if commit and is_git and not self.dry_run:
            try:
                # Clean up ephemeral projected Antigravity context files before committing
                try:
                    from client.antigravity_bridge import cleanup_worktree_context
                    cleanup_worktree_context(worktree_dir)
                except Exception as e:
                    logger.debug(f"Context cleanup notice: {e}")

                status_proc = await asyncio.create_subprocess_exec(
                    "git", "status", "--porcelain",
                    cwd=str(worktree_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=WIN32_NO_WINDOW,
                )
                status_out, _ = await status_proc.communicate()
                has_changes = bool(status_out.strip())

                if has_changes:
                    add_proc = await asyncio.create_subprocess_exec(
                        "git", "add", "-A",
                        cwd=str(worktree_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        creationflags=WIN32_NO_WINDOW,
                    )
                    await add_proc.communicate()

                    msg = f"feat({task_id or 'copilot'}): automated implementation"
                    commit_proc = await asyncio.create_subprocess_exec(
                        "git", "commit", "-m", msg,
                        cwd=str(worktree_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        creationflags=WIN32_NO_WINDOW,
                    )
                    await commit_proc.communicate()

                sha_proc = await asyncio.create_subprocess_exec(
                    "git", "rev-parse", "HEAD",
                    cwd=str(worktree_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=WIN32_NO_WINDOW,
                )
                sha_out, _ = await sha_proc.communicate()
                if sha_proc.returncode == 0:
                    commit_sha = sha_out.decode("utf-8", errors="replace").strip()
            except Exception as e:
                logger.warning(f"Error committing changes in worktree {worktree_dir}: {e}")

        # Remove git worktree
        if is_git and not self.dry_run:
            try:
                rm_proc = await asyncio.create_subprocess_exec(
                    "git", "worktree", "remove", "--force", str(worktree_dir),
                    cwd=str(root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=WIN32_NO_WINDOW,
                )
                await rm_proc.communicate()

                prune_proc = await asyncio.create_subprocess_exec(
                    "git", "worktree", "prune",
                    cwd=str(root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=WIN32_NO_WINDOW,
                )
                await prune_proc.communicate()
            except Exception as e:
                logger.warning(f"Error removing git worktree: {e}")

        # Clean up directory from filesystem if still present
        if worktree_dir.exists():
            def _remove_readonly(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                    func(path)
                except OSError:
                    pass

            for attempt in range(4):
                try:
                    shutil.rmtree(worktree_dir, onerror=_remove_readonly)
                    if not worktree_dir.exists():
                        break
                except Exception:
                    await asyncio.sleep(0.08 * (2 ** attempt))

            if worktree_dir.exists() and sys.platform == "win32":
                try:
                    p = await asyncio.create_subprocess_exec(
                        "cmd.exe", "/c", "rmdir", "/s", "/q", str(worktree_dir),
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                        creationflags=WIN32_NO_WINDOW,
                    )
                    await p.communicate()
                except Exception:
                    pass

        # Optional ephemeral branch deletion
        if prune_branch and branch_name and is_git and not self.dry_run:
            try:
                cur_branch_proc = await asyncio.create_subprocess_exec(
                    "git", "branch", "--show-current",
                    cwd=str(self.repo_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=WIN32_NO_WINDOW,
                )
                cur_out, _ = await cur_branch_proc.communicate()
                cur_branch = cur_out.decode("utf-8", errors="replace").strip()
                if branch_name != cur_branch:
                    del_branch_proc = await asyncio.create_subprocess_exec(
                        "git", "branch", "-D", branch_name,
                        cwd=str(self.repo_root),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        creationflags=WIN32_NO_WINDOW,
                    )
                    await del_branch_proc.communicate()
            except Exception as e:
                logger.warning(f"Error pruning task branch {branch_name}: {e}")

        return commit_sha

    def prune_completed_task_branches(self) -> int:
        """
        Scans orchestrator-state/tasks/ for tasks with status 'done' or 'blocked'.
        Safely prunes local git branches matching task/{task_id} to prevent
        exponential branch accumulation.
        """
        if not self._is_git_repo(self.repo_root):
            return 0

        finished_ids = set()
        for f in self.tasks_dir.glob("task_*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if data.get("status") in ("done", "blocked"):
                    tid = data.get("id") or f.stem
                    finished_ids.add(tid)
            except Exception:
                pass

        try:
            res = subprocess.run(
                ["git", "branch", "--list", "task/*"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
                creationflags=WIN32_NO_WINDOW,
            )
            if res.returncode != 0 or not res.stdout.strip():
                return 0

            cur_res = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
                creationflags=WIN32_NO_WINDOW,
            )
            current_branch = cur_res.stdout.strip()

            pruned = 0
            for line in res.stdout.splitlines():
                b = line.strip().lstrip("*").strip()
                if not b or b == current_branch:
                    continue
                tid = b.removeprefix("task/")
                if tid in finished_ids or b.startswith("task/task_1791"):
                    del_res = subprocess.run(
                        ["git", "branch", "-D", b],
                        cwd=str(self.repo_root),
                        capture_output=True,
                        text=True,
                        check=False,
                        creationflags=WIN32_NO_WINDOW,
                    )
                    if del_res.returncode == 0:
                        pruned += 1
            if pruned > 0:
                logger.info(f"Pruned {pruned} completed task branch(es).")
            return pruned
        except Exception as e:
            logger.warning(f"Error during task branch pruning: {e}")
            return 0

    async def execute_task(
        self,
        task: dict[str, Any],
        account: dict[str, Any],
        worktree_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Executes task spec via CopilotCLIAdapter without --model (auto-routing)."""
        task_id = task["id"]
        spec = task.get("spec", "")

        target_worktree = worktree_dir or self.worktree_root

        if self.dry_run:
            logger.info(f"[DRY-RUN] Simulating code generation for {task_id} in {target_worktree}...")
            await asyncio.sleep(0.5)
            return {
                "success": True,
                "summary": f"Simulated implementation of {task_id} ({spec[:60]}...)",
                "commit_sha": "dryrun0001",
                "branch_name": f"task/{task_id}",
                "credits_used": 1,
                "quota_exhausted": False,
                "usage_data": {"credits": 1, "tokens": 50},
            }

        # Resolve and project Antigravity scope if available
        antigravity_scope = task.get("antigravity_scope") or task.get("context", {}).get("antigravity_scope")
        if not antigravity_scope:
            if "chat_context" in task or "chat_context" in task.get("context", {}):
                antigravity_scope = {
                    "chat_context": task.get("chat_context") or task.get("context", {}).get("chat_context", {}),
                    "antigravity_customizations": task.get("antigravity_customizations") or task.get("context", {}).get("antigravity_customizations", {}),
                }
            else:
                # Auto-discover active Antigravity session if brain exists
                try:
                    from client.antigravity_bridge import build_antigravity_scope
                    discovered = build_antigravity_scope(repo_root=self.repo_root)
                    if discovered.get("chat_context", {}).get("conversation_id"):
                        antigravity_scope = discovered
                        task["antigravity_scope"] = antigravity_scope
                except Exception:
                    pass

        if target_worktree and target_worktree.exists() and antigravity_scope:
            try:
                from client.antigravity_bridge import project_worktree_context
                project_worktree_context(target_worktree, antigravity_scope)
            except Exception as e:
                logger.warning(f"Could not project Antigravity context into worktree: {e}")

        has_customizations = bool(
            antigravity_scope or (target_worktree and (target_worktree / "AGENTS.md").exists())
        )

        # Resolve timeout: support dynamic time_allocation ceiling if available
        timeout_val = task.get("timeout")
        if not timeout_val and "time_allocation" in task:
            timeout_val = task["time_allocation"].get("timeout_ceiling_s")
        timeout_sec = float(timeout_val if timeout_val is not None else 420.0)

        # Check if local SLM bypass is requested
        exec_route = task.get("execution_route") or task.get("time_allocation", {}).get("execution_route")
        if exec_route == "LOCAL_SLM":
            logger.info(f"Task {task_id} has route LOCAL_SLM - executing via local SLM engine...")
            try:
                from tools.fast_intent_router import _call_lm_studio
                local_resp = _call_lm_studio(spec)
                if local_resp:
                    return {
                        "success": True,
                        "summary": f"Executed locally via Local SLM: {task_id}",
                        "commit_sha": None,
                        "branch_name": f"task/{task_id}",
                        "credits_used": 0.0,
                        "tokens_used": 150,
                        "model_used": "local-slm-qwen",
                        "raw_output": str(local_resp),
                    }
            except Exception as e:
                logger.warning(f"LOCAL_SLM execution failed, falling back to Copilot: {e}")

        # Resolve model and auto_tier from task metadata
        model = task.get("model") or task.get("recommended_model")
        auto_tier = task.get("auto_tier")

        adapter = CopilotCLIAdapter(
            worker_id=account["worker_id"],
            nickname=account["name"],
            worktree=str(target_worktree) if target_worktree else None,
            model=model,
            auto_tier=auto_tier,
            github_token=account.get("token") or None,
            copilot_home=account.get("state_dir") or None,
            allow_custom_instructions=has_customizations,
            timeout=timeout_sec,
        )

        logger.info(f"Executing {task_id} via Copilot CLI (Worker: {account['worker_id']}, Auto-Tier: {auto_tier}, Model: {model}, Worktree: {target_worktree})...")
        exec_result = await adapter.execute_task(
            task_id=task_id,
            spec=spec,
            stage="code",
            context=task,
        )

        return exec_result

    def submit_checkpoint_and_complete(
        self,
        task_id: str,
        account: dict[str, Any],
        summary: str,
        branch_name: str | None = None,
        commit_sha: str | None = None,
        actual_duration_s: float | None = None,
    ) -> None:
        """Writes checkpoint file and transitions task to done."""
        now = _now_iso()
        branch = branch_name or f"task/{task_id}"
        sha = commit_sha or "HEAD"

        checkpoint = {
            "task_id": task_id,
            "kind": "code",
            "summary": summary,
            "branch_name": branch,
            "commit_sha": sha,
            "actual_duration_s": actual_duration_s,
            "result_text": None,
            "submitted_by": account["worker_id"],
            "submitted_at": now,
        }

        checkpoint_file = self.checkpoints_dir / f"{task_id}.json"
        tmp_cp = checkpoint_file.with_suffix(f".tmp.{os.getpid()}")
        with open(tmp_cp, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)
        os.replace(tmp_cp, checkpoint_file)

        # Update task file to status: "done"
        task_path = self.tasks_dir / f"{task_id}.json"
        if task_path.exists():
            try:
                with open(task_path, "r", encoding="utf-8") as f:
                    task = json.load(f)
                task["status"] = "done"
                task["updated_at"] = now
                tmp_task = task_path.with_suffix(f".tmp.{os.getpid()}")
                with open(tmp_task, "w", encoding="utf-8") as f:
                    json.dump(task, f, indent=2)
                os.replace(tmp_task, task_path)
            except Exception as e:
                logger.error(f"Error updating task {task_id} to done: {e}")

        # Clear live-status
        self._update_live_status(
            account=account["worker_id"],
            current_task_id=None,
            note="Idle - completed task",
            status="idle",
        )
        logger.info(f"Task {task_id} marked DONE. Checkpoint written to {checkpoint_file.name}")

    def _record_copilot_mistake(
        self,
        task: dict[str, Any],
        account: dict[str, Any],
        result: dict[str, Any],
        error_msg: str,
    ) -> None:
        """Records failed task execution trace for continuous counter-dataset training."""
        try:
            mistakes_dir = self.state_dir / "qa-reviews" / "copilot_mistakes"
            mistakes_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "task_id": task.get("id"),
                "timestamp": _now_iso(),
                "worker_id": account.get("worker_id"),
                "auto_tier": task.get("auto_tier"),
                "model": task.get("model") or task.get("recommended_model"),
                "spec": task.get("spec", ""),
                "error": error_msg,
                "stdout": result.get("stdout", "")[:2000] if isinstance(result.get("stdout"), str) else "",
                "stderr": result.get("stderr", "")[:2000] if isinstance(result.get("stderr"), str) else "",
            }
            out_file = mistakes_dir / f"{task.get('id')}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
            logger.info(f"Recorded Copilot mistake trace to {out_file.name}")
        except Exception as e:
            logger.warning(f"Could not record Copilot mistake trace: {e}")

    def _mark_task_blocked(self, task_id: str, account: dict[str, Any], reason: str) -> None:
        """Transitions task to blocked state per SCHEMA.md."""
        task_path = self.tasks_dir / f"{task_id}.json"
        if task_path.exists():
            try:
                with open(task_path, "r", encoding="utf-8") as f:
                    task = json.load(f)
                task["status"] = "blocked"
                task["blocked_reason"] = reason
                task["updated_at"] = _now_iso()
                tmp_path = task_path.with_suffix(f".tmp.{os.getpid()}.{task_id}")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(task, f, indent=2)
                os.replace(tmp_path, task_path)
            except Exception as e:
                logger.error(f"Error marking task {task_id} blocked: {e}")

        self._update_live_status(
            account=account["worker_id"],
            current_task_id=None,
            note=f"Blocked on {task_id}: {reason}",
            status="idle",
        )

    async def process_one_task(self, target_task_id: str | None = None) -> bool:
        """Picks up, claims, and executes a single pending code task. Returns True if a task was processed."""
        if target_task_id:
            pending = [t for t in self.find_pending_code_tasks() if t.get("id") == target_task_id]
        else:
            pending = self.find_pending_code_tasks()
        if not pending:
            return False

        account = self.get_next_account()
        if not account:
            return False

        # Attempt to claim candidates in order to gracefully resolve multi-process claim races
        claimed_task = None
        for task_candidate in pending:
            claimed_task = self.claim_task(task_candidate["id"], account)
            if claimed_task:
                break

        if not claimed_task:
            return False

        task_id = claimed_task["id"]
        branch_name = claimed_task.get("branch_name") or f"task/{task_id}"
        target_repo = claimed_task.get("target_repo")

        print(f"[CLAIMED] Worker {account['worker_id']} acquired lease for {task_id} (PID: {os.getpid()})", flush=True)

        worktree_dir = await self.provision_worktree(task_id, branch_name, target_repo=target_repo)
        print(f"[WORKTREE] Provisioned isolated worktree {worktree_dir.name} on branch {branch_name}", flush=True)

        exec_start = time.perf_counter()
        auto_tier = claimed_task.get("auto_tier", "balance")
        model = claimed_task.get("model") or claimed_task.get("recommended_model") or "auto"
        print(f"[EXEC] Running Copilot CLI (Model: {model}, Auto-Tier: {auto_tier})...", flush=True)

        try:
            result = await self.execute_task(claimed_task, account, worktree_dir=worktree_dir)
            actual_duration = round(time.perf_counter() - exec_start, 1)

            # Telemetry & Quota handling
            credits_used = float(result.get("credits_used", 1.0 if result.get("success") else 0.0))
            self.record_credit_usage(account["worker_id"], credits_used)

            if result.get("quota_exhausted"):
                self.mark_cooldown(account["worker_id"], until=next_billing_reset(), quota_exhausted=True, reason="Copilot CLI quota exhausted")
            elif result.get("rate_limited_429"):
                self.mark_cooldown(account["worker_id"], minutes=60, quota_exhausted=False, reason="Rate limited (HTTP 429)")

            # Commit changes and cleanup worktree
            commit_sha = await self.teardown_worktree(
                worktree_dir,
                branch_name=branch_name,
                task_id=task_id,
                commit=result.get("success", False),
                repo_root=target_repo,
            )

            summary = result.get("summary") or f"Implemented task {task_id}"
            sha = commit_sha or result.get("commit_sha") or "HEAD"

            if result.get("success"):
                print(f"[CHECKPOINT] Deliverable committed to branch {branch_name} ({sha[:7] if len(sha) >= 7 else sha})", flush=True)
                self.submit_checkpoint_and_complete(
                    task_id=task_id,
                    account=account,
                    summary=summary,
                    branch_name=branch_name,
                    commit_sha=sha,
                    actual_duration_s=actual_duration,
                )
                print(f"[COMPLETED] Task {task_id} successfully finalized in {actual_duration}s.", flush=True)
                return True
            else:
                error_msg = result.get("error") or "Execution failed"
                print(f"[FAILED] Task {task_id} execution failed: {error_msg}", flush=True)
                self._record_copilot_mistake(task=claimed_task, account=account, result=result, error_msg=error_msg)
                self._mark_task_blocked(task_id, account, error_msg)
                return False

        except Exception as e:
            logger.error(f"Execution error on task {task_id}: {e}")
            await self.teardown_worktree(worktree_dir, branch_name=branch_name, task_id=task_id, commit=False, repo_root=target_repo)
            self._record_copilot_mistake(task=claimed_task, account=account, result={}, error_msg=str(e))
            self._mark_task_blocked(task_id, account, str(e))
            print(f"[ERROR] Task {task_id} encountered exception: {e}", flush=True)
            return False

    async def run(self, once: bool = False, target_task_id: str | None = None, timeout: float = 300.0) -> None:
        """Main queue worker loop supporting concurrent task execution and targeted one-shot polling."""
        self._running = True
        logger.info(
            f"Copilot Queue Worker started | State Dir: {self.state_dir} | "
            f"Ready Accounts: {len(self.ready_accounts)} | Concurrency: {self.concurrency} | "
            f"Poll Interval: {self.poll_interval}s"
        )

        if target_task_id and once:
            print(f"[DISPATCH] Monitoring targeted task: {target_task_id}", flush=True)
            start_t = time.perf_counter()
            while self._running:
                processed = await self.process_one_task(target_task_id=target_task_id)
                if processed:
                    break
                if time.perf_counter() - start_t > timeout:
                    print(f"[TIMEOUT] Targeted task {target_task_id} was not processed within {timeout}s.", flush=True)
                    break
                await asyncio.sleep(1.0)
            return

        if self.concurrency <= 1:
            while self._running:
                processed = await self.process_one_task(target_task_id=target_task_id)
                if once:
                    break
                if not processed:
                    await asyncio.sleep(self.poll_interval)
        else:
            semaphore = asyncio.Semaphore(self.concurrency)

            async def _worker_loop():
                while self._running:
                    async with semaphore:
                        processed = await self.process_one_task(target_task_id=target_task_id)
                    if once:
                        break
                    if not processed:
                        await asyncio.sleep(self.poll_interval)

            tasks = [asyncio.create_task(_worker_loop()) for _ in range(self.concurrency)]
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                pass

    def stop(self) -> None:
        self._running = False


async def main() -> None:
    parser = argparse.ArgumentParser(description="Copilot Queue Worker for orchestrator-state/")
    parser.add_argument("--state-dir", type=str, default=None, help="Path to orchestrator-state directory")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Poll interval in seconds (default: 5.0)")
    parser.add_argument("--repo-root", type=str, default=None, help="Root path of git repository to provision worktrees from")
    parser.add_argument("--worktree-root", type=str, default=None, help="Root path for git worktrees")
    parser.add_argument("--no-worktree", action="store_true", help="Disable git worktree provisioning")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent worker tasks (default: 1)")
    parser.add_argument("--worker-id", type=str, default=None, help="Bind this worker process to a specific worker ID (e.g. copilot-w1)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without spawning copilot.exe")
    parser.add_argument("--once", action="store_true", help="Process at most one task and exit")
    parser.add_argument("--task-id", type=str, default=None, help="Target a specific pending task ID")
    parser.add_argument("--timeout", type=float, default=300.0, help="Timeout in seconds for targeted one-shot execution (default: 300.0)")

    args = parser.parse_args()

    worker = CopilotQueueWorker(
        state_dir=args.state_dir,
        poll_interval=args.poll_interval,
        dry_run=args.dry_run,
        worktree_root=args.worktree_root,
        repo_root=args.repo_root,
        auto_worktrees=not args.no_worktree,
        concurrency=args.concurrency,
        worker_id_filter=args.worker_id,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except (NotImplementedError, RuntimeError):
            # Windows may not support add_signal_handler for all signals
            pass

    await worker.run(once=args.once, target_task_id=args.task_id, timeout=args.timeout)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
