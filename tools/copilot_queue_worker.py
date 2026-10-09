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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from client.adapters.copilot_cli_adapter import CopilotCLIAdapter
from tools.copilot_fleet import discover_accounts, load_env_fleet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [CopilotQueueWorker] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("copilot_queue_worker")

# Suppress noisy HTTP client logs from httpx/httpcore
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_state_dir(explicit_path: str | None = None) -> Path:
    """Finds orchestrator-state root directory."""
    if explicit_path:
        p = Path(explicit_path).resolve()
        if p.exists():
            return p

    env_path = os.getenv("ORCHESTRATOR_STATE_DIR")
    if env_path:
        p = Path(env_path).resolve()
        if p.exists():
            return p

    # Check local orchestrator-state in Fleet-Orchestrator
    local_state = PROJECT_ROOT / "orchestrator-state"
    if local_state.exists():
        return local_state

    # Check sibling Claude-Desktop/orchestrator-state
    sibling_state = PROJECT_ROOT.parent / "Claude-Desktop" / "orchestrator-state"
    if sibling_state.exists():
        return sibling_state

    # Fallback to local_state even if not yet populated
    return local_state


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
        self._initialize_fleet_status_files()
        self._load_live_status_telemetry()

    def _ensure_dirs(self) -> None:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.live_status_dir.mkdir(parents=True, exist_ok=True)

    def _initialize_fleet_status_files(self) -> None:
        """Ensures all accounts have an initialized live-status file in orchestrator-state."""
        self.live_status_dir.mkdir(parents=True, exist_ok=True)
        now_str = _now_iso()
        for acc in self.accounts:
            wid = acc["worker_id"]
            status_file = self.live_status_dir / f"{wid}.json"
            if not status_file.exists():
                limit = acc.get("monthly_credits", 200)
                data = {
                    "account": wid,
                    "name": acc["name"],
                    "status": "idle" if acc["has_token"] else "offline",
                    "current_task_id": None,
                    "credits_used": 0.0,
                    "credits_remaining": float(limit),
                    "monthly_credits": limit,
                    "cooldown_until": None,
                    "heartbeat_at": now_str,
                    "note": "Ready (Initialized)" if acc["has_token"] else "No Token",
                }
                try:
                    tmp = status_file.with_suffix(f".tmp.{os.getpid()}")
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    os.replace(tmp, status_file)
                except Exception:
                    pass

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
                        exp = datetime.fromisoformat(data["cooldown_until"].replace("Z", "+00:00"))
                        if exp > now:
                            self.account_cooldowns[wid] = exp
                except Exception as e:
                    logger.debug(f"Could not load status for {wid}: {e}")

    def is_in_cooldown(self, worker_id: str) -> bool:
        """Returns True if worker is in active cooldown."""
        exp = self.account_cooldowns.get(worker_id)
        if not exp:
            return False
        if datetime.now(timezone.utc) >= exp:
            del self.account_cooldowns[worker_id]
            return False
        return True

    def mark_cooldown(self, worker_id: str, minutes: int = 60, reason: str = "") -> None:
        """Transitions worker account to cooldown state and updates live-status."""
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=minutes)
        self.account_cooldowns[worker_id] = exp
        logger.warning(f"Worker {worker_id} placed in COOLDOWN for {minutes}m. Reason: {reason}")
        self._update_live_status(
            account=worker_id,
            current_task_id=None,
            note=f"Cooldown ({minutes}m): {reason}",
            status="cooldown",
        )

    def record_credit_usage(self, worker_id: str, credits_used: float) -> float:
        """Records consumed credits and auto-cooldowns when monthly limit reached."""
        current = round(float(self.account_credits.get(worker_id, 0.0)) + float(credits_used), 2)
        self.account_credits[worker_id] = current

        limit = 200
        for acc in self.accounts:
            if acc.get("worker_id") == worker_id:
                limit = acc.get("monthly_credits", 200)
                break

        logger.info(f"Worker {worker_id} credit update: +{credits_used:.2f} used (Total: {current:.2f}/{limit})")
        if current >= limit:
            self.mark_cooldown(worker_id, minutes=60 * 24 * 30, reason=f"Monthly quota exhausted ({current:.2f}/{limit} credits)")

        return current

    def get_next_account(self) -> dict[str, Any] | None:
        """Round-robin selection across ready Copilot accounts, bypassing accounts in cooldown."""
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

                    if is_eligible and data.get("status") == "pending":
                        pending_tasks.append(data)
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
    ) -> None:
        """Updates live status light in orchestrator-state/live-status/<account>.json."""
        status_file = self.live_status_dir / f"{account}.json"

        used = round(float(self.account_credits.get(account, 0.0)), 2)
        limit = 200
        for acc in self.accounts:
            if acc.get("worker_id") == account:
                limit = acc.get("monthly_credits", 200)
                break
        rem = max(0.0, round(limit - used, 2))
        cd_exp = self.account_cooldowns.get(account)
        cd_iso = cd_exp.strftime("%Y-%m-%dT%H:%M:%SZ") if cd_exp else None

        actual_status = status
        if cd_exp and datetime.now(timezone.utc) < cd_exp:
            actual_status = "cooldown"
        elif current_task_id is None:
            actual_status = "idle"

        data = {
            "account": account,
            "status": actual_status,
            "current_task_id": current_task_id,
            "credits_used": used,
            "credits_remaining": rem,
            "monthly_credits": limit,
            "cooldown_until": cd_iso,
            "heartbeat_at": _now_iso(),
            "note": note,
        }
        try:
            tmp_file = status_file.with_suffix(f".tmp.{os.getpid()}")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_file, status_file)
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
            )
            return res.returncode == 0 and "true" in res.stdout.lower()
        except Exception:
            return False

    async def provision_worktree(self, task_id: str, branch_name: str) -> Path:
        """
        Auto-provisions an isolated Git worktree:
        `git worktree add -b task/<task_id> <worktree_dir> HEAD`
        Falls back to creating an isolated directory if not in a git repository or during dry-run.
        """
        worktree_dir = self.worktree_root / task_id
        if self.dry_run or not self.auto_worktrees or not self._is_git_repo(self.repo_root):
            worktree_dir.mkdir(parents=True, exist_ok=True)
            return worktree_dir

        self.worktree_root.mkdir(parents=True, exist_ok=True)

        if worktree_dir.exists():
            await self.teardown_worktree(worktree_dir, branch_name=None, commit=False)

        # Check if branch already exists
        check_proc = await asyncio.create_subprocess_exec(
            "git", "branch", "--list", branch_name,
            cwd=str(self.repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
            cwd=str(self.repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
    ) -> str | None:
        """
        Automatically commits changes inside the worktree (if any),
        records the commit SHA, and cleans up the worktree.
        """
        commit_sha = None
        if not worktree_dir.exists():
            return None

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
                )
                status_out, _ = await status_proc.communicate()
                has_changes = bool(status_out.strip())

                if has_changes:
                    add_proc = await asyncio.create_subprocess_exec(
                        "git", "add", "-A",
                        cwd=str(worktree_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await add_proc.communicate()

                    msg = f"feat({task_id or 'copilot'}): automated implementation"
                    commit_proc = await asyncio.create_subprocess_exec(
                        "git", "commit", "-m", msg,
                        cwd=str(worktree_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await commit_proc.communicate()

                sha_proc = await asyncio.create_subprocess_exec(
                    "git", "rev-parse", "HEAD",
                    cwd=str(worktree_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
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
                    cwd=str(self.repo_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await rm_proc.communicate()

                prune_proc = await asyncio.create_subprocess_exec(
                    "git", "worktree", "prune",
                    cwd=str(self.repo_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
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
                    )
                    await p.communicate()
                except Exception:
                    pass

        return commit_sha

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

        adapter = CopilotCLIAdapter(
            worker_id=account["worker_id"],
            nickname=account["name"],
            worktree=str(target_worktree) if target_worktree else None,
            model=None,  # STRICT: Omits --model for provider auto-routing
            github_token=account.get("token") or None,
            copilot_home=account.get("state_dir") or None,
            allow_custom_instructions=has_customizations,
        )

        logger.info(f"Executing {task_id} via Copilot CLI (Worker: {account['worker_id']}, Worktree: {target_worktree})...")
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
        worktree_dir = await self.provision_worktree(task_id, branch_name)

        try:
            result = await self.execute_task(claimed_task, account, worktree_dir=worktree_dir)

            # Telemetry & Quota handling
            credits_used = float(result.get("credits_used", 1.0 if result.get("success") else 0.0))
            self.record_credit_usage(account["worker_id"], credits_used)

            if result.get("quota_exhausted"):
                self.mark_cooldown(account["worker_id"], minutes=60 * 24 * 30, reason="Copilot CLI quota exhausted")

            # Commit changes and cleanup worktree
            commit_sha = await self.teardown_worktree(
                worktree_dir,
                branch_name=branch_name,
                task_id=task_id,
                commit=result.get("success", False),
            )

            summary = result.get("summary") or f"Implemented task {task_id}"
            sha = commit_sha or result.get("commit_sha") or "HEAD"

            if result.get("success"):
                self.submit_checkpoint_and_complete(
                    task_id=task_id,
                    account=account,
                    summary=summary,
                    branch_name=branch_name,
                    commit_sha=sha,
                )
                return True
            else:
                error_msg = result.get("error") or "Execution failed"
                self._mark_task_blocked(task_id, account, error_msg)
                return False

        except Exception as e:
            logger.error(f"Execution error on task {task_id}: {e}")
            await self.teardown_worktree(worktree_dir, branch_name=branch_name, task_id=task_id, commit=False)
            self._mark_task_blocked(task_id, account, str(e))
            return False

    async def run(self, once: bool = False, target_task_id: str | None = None) -> None:
        """Main queue worker loop supporting concurrent task execution."""
        self._running = True
        logger.info(
            f"Copilot Queue Worker started | State Dir: {self.state_dir} | "
            f"Ready Accounts: {len(self.ready_accounts)} | Concurrency: {self.concurrency} | "
            f"Poll Interval: {self.poll_interval}s"
        )

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

    await worker.run(once=args.once, target_task_id=args.task_id)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
