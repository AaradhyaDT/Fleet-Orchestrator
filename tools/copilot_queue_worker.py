#!/usr/bin/env python3
"""
Copilot Queue Worker:
Headless background worker connecting GitHub Copilot CLI to orchestrator-state/.
Polls orchestrator-state/tasks/ for kind: "code" and status: "pending",
claims the task using round-robin account rotation across the 27 Copilot workers,
executes non-interactively in an isolated worktree via CopilotCLIAdapter (without --model),
writes orchestrator-state/checkpoints/<task_id>.json, and marks the task "done".
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
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
    ):
        self.state_dir = resolve_state_dir(str(state_dir) if state_dir else None)
        self.tasks_dir = self.state_dir / "tasks"
        self.checkpoints_dir = self.state_dir / "checkpoints"
        self.live_status_dir = self.state_dir / "live-status"
        self.poll_interval = poll_interval
        self.dry_run = dry_run
        self.worktree_root = Path(worktree_root).resolve() if worktree_root else None

        self._ensure_dirs()
        self.env_vars = load_env_fleet()
        self.accounts = discover_accounts(self.env_vars)
        self.ready_accounts = [a for a in self.accounts if a.get("has_token")]
        self._current_account_idx = 0
        self._running = False

    def _ensure_dirs(self) -> None:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.live_status_dir.mkdir(parents=True, exist_ok=True)

    def get_next_account(self) -> dict[str, Any]:
        """Round-robin selection across ready Copilot accounts."""
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

        acc = self.ready_accounts[self._current_account_idx % len(self.ready_accounts)]
        self._current_account_idx += 1
        return acc

    def find_pending_code_tasks(self) -> list[dict[str, Any]]:
        """Scans orchestrator-state/tasks for pending code tasks."""
        if not self.tasks_dir.exists():
            return []

        pending_tasks = []
        for task_file in sorted(self.tasks_dir.glob("task_*.json")):
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if (
                    isinstance(data, dict)
                    and data.get("kind") == "code"
                    and data.get("status") == "pending"
                ):
                    pending_tasks.append(data)
            except Exception as e:
                logger.warning(f"Error reading task file {task_file.name}: {e}")

        return pending_tasks

    def claim_task(self, task_id: str, account: dict[str, Any]) -> dict[str, Any] | None:
        """
        Optimistically claims a task according to SCHEMA.md contract.
        Re-reads file immediately before writing to avoid claim races.
        """
        task_path = self.tasks_dir / f"{task_id}.json"
        if not task_path.exists():
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

            with open(task_path, "w", encoding="utf-8") as f:
                json.dump(task, f, indent=2)

            # Update live-status for the account
            self._update_live_status(
                account=account["worker_id"],
                current_task_id=task_id,
                note=f"Executing code task {task_id}",
            )

            logger.info(f"Successfully claimed {task_id} for worker {account['worker_id']} ({account['name']})")
            return task
        except Exception as e:
            logger.error(f"Failed to claim task {task_id}: {e}")
            return None

    def _update_live_status(
        self,
        account: str,
        current_task_id: str | None,
        note: str,
    ) -> None:
        """Updates live status light in orchestrator-state/live-status/<account>.json."""
        status_file = self.live_status_dir / f"{account}.json"
        data = {
            "account": account,
            "current_task_id": current_task_id,
            "heartbeat_at": _now_iso(),
            "note": note,
        }
        try:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not update live-status for {account}: {e}")

    async def execute_task(
        self,
        task: dict[str, Any],
        account: dict[str, Any],
    ) -> dict[str, Any]:
        """Executes task spec via CopilotCLIAdapter without --model (auto-routing)."""
        task_id = task["id"]
        spec = task.get("spec", "")

        if self.dry_run:
            logger.info(f"[DRY-RUN] Simulating code generation for {task_id}...")
            await asyncio.sleep(0.5)
            return {
                "success": True,
                "summary": f"Simulated implementation of {task_id} ({spec[:60]}...)",
                "commit_sha": "dryrun0001",
                "branch_name": f"task/{task_id}",
            }

        adapter = CopilotCLIAdapter(
            worker_id=account["worker_id"],
            nickname=account["name"],
            worktree=str(self.worktree_root) if self.worktree_root else None,
            model=None,  # STRICT: Omits --model for provider auto-routing
            github_token=account.get("token") or None,
            copilot_home=account.get("state_dir") or None,
        )

        logger.info(f"Executing {task_id} via Copilot CLI (Worker: {account['worker_id']})...")
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
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)

        # Update task file to status: "done"
        task_path = self.tasks_dir / f"{task_id}.json"
        if task_path.exists():
            try:
                with open(task_path, "r", encoding="utf-8") as f:
                    task = json.load(f)
                task["status"] = "done"
                task["updated_at"] = now
                with open(task_path, "w", encoding="utf-8") as f:
                    json.dump(task, f, indent=2)
            except Exception as e:
                logger.error(f"Error updating task {task_id} to done: {e}")

        # Clear live-status
        self._update_live_status(
            account=account["worker_id"],
            current_task_id=None,
            note="Idle - completed task",
        )
        logger.info(f"Task {task_id} marked DONE. Checkpoint written to {checkpoint_file.name}")

    async def process_one_task(self) -> bool:
        """Picks up, claims, and executes a single pending code task. Returns True if a task was processed."""
        pending = self.find_pending_code_tasks()
        if not pending:
            return False

        task_to_run = pending[0]
        account = self.get_next_account()

        claimed_task = self.claim_task(task_to_run["id"], account)
        if not claimed_task:
            return False

        task_id = claimed_task["id"]
        try:
            result = await self.execute_task(claimed_task, account)
            summary = result.get("summary") or f"Implemented task {task_id}"
            branch = result.get("branch_name") or f"task/{task_id}"
            sha = result.get("commit_sha") or "HEAD"
            self.submit_checkpoint_and_complete(
                task_id=task_id,
                account=account,
                summary=summary,
                branch_name=branch,
                commit_sha=sha,
            )
            return True
        except Exception as e:
            logger.error(f"Execution error on task {task_id}: {e}")
            # Mark task blocked per SCHEMA.md
            task_path = self.tasks_dir / f"{task_id}.json"
            if task_path.exists():
                try:
                    with open(task_path, "r", encoding="utf-8") as f:
                        task = json.load(f)
                    task["status"] = "blocked"
                    task["blocked_reason"] = str(e)
                    task["updated_at"] = _now_iso()
                    with open(task_path, "w", encoding="utf-8") as f:
                        json.dump(task, f, indent=2)
                except Exception:
                    pass
            self._update_live_status(
                account=account["worker_id"],
                current_task_id=None,
                note=f"Error executing {task_id}: {e}",
            )
            return False

    async def run(self, once: bool = False) -> None:
        """Main queue worker loop."""
        self._running = True
        logger.info(
            f"Copilot Queue Worker started | State Dir: {self.state_dir} | "
            f"Ready Accounts: {len(self.ready_accounts)} | Poll Interval: {self.poll_interval}s"
        )

        while self._running:
            processed = await self.process_one_task()
            if once:
                break
            if not processed:
                await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        self._running = False


async def main() -> None:
    parser = argparse.ArgumentParser(description="Copilot Queue Worker for orchestrator-state/")
    parser.add_argument("--state-dir", type=str, default=None, help="Path to orchestrator-state directory")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Poll interval in seconds (default: 5.0)")
    parser.add_argument("--worktree-root", type=str, default=None, help="Root path for git worktrees")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without spawning copilot.exe")
    parser.add_argument("--once", action="store_true", help="Process at most one task and exit")

    args = parser.parse_args()

    worker = CopilotQueueWorker(
        state_dir=args.state_dir,
        poll_interval=args.poll_interval,
        dry_run=args.dry_run,
        worktree_root=args.worktree_root,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except (NotImplementedError, RuntimeError):
            # Windows may not support add_signal_handler for all signals
            pass

    await worker.run(once=args.once)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
