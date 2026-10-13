"""
Automated Test Suite for Antigravity 2.0 Background Task Handoff & Telemetry.
Validates:
- Targeted task polling wait and timeout.
- Pre-flight worktree self-healing against orphaned worktrees and stale branches.
- Dynamic target_repo cross-repository worktree provisioning.
- Fast PID-anchored zombie lease recovery from terminated processes.
- Atomic run-task command dispatch in dry-run mode.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
import pytest

from tools.copilot_queue_worker import CopilotQueueWorker, is_pid_alive
from tools.unified_fleet_cli import cmd_run_task


@pytest.fixture
def temp_env(tmp_path: Path):
    """Sets up an isolated orchestrator-state and mock git repo."""
    state_dir = tmp_path / "orchestrator-state"
    state_dir.mkdir(parents=True)
    (state_dir / "tasks").mkdir()
    (state_dir / "checkpoints").mkdir()
    (state_dir / "live-status").mkdir()

    repo_dir = tmp_path / "target_repo"
    repo_dir.mkdir(parents=True)

    # Initialize a valid git repository
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    
    # Create initial commit so HEAD exists
    init_file = repo_dir / "README.md"
    init_file.write_text("# Target Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

    return {
        "state_dir": state_dir,
        "repo_dir": repo_dir,
    }


def test_is_pid_alive_current_and_invalid():
    """Confirms PID liveness check works for current process and dead PID."""
    assert is_pid_alive(os.getpid()) is True
    # 99999999 is extraordinarily unlikely to exist as a process
    assert is_pid_alive(99999999) is False
    assert is_pid_alive(0) is False
    assert is_pid_alive(None) is False


def test_fast_zombie_lease_recovery(temp_env):
    """Verifies claimed tasks from dead PIDs are automatically reclaimed on scan."""
    state_dir = temp_env["state_dir"]
    tasks_dir = state_dir / "tasks"
    worker = CopilotQueueWorker(state_dir=state_dir, dry_run=True)

    # Task claimed by a dead PID (e.g. 99999999)
    zombie_task = {
        "id": "task_zombie_001",
        "kind": "code",
        "spec": "Fix flaky test",
        "status": "claimed",
        "owner_account": "copilot-w1",
        "owner_pid": 99999999,
    }
    with open(tasks_dir / "task_zombie_001.json", "w", encoding="utf-8") as f:
        json.dump(zombie_task, f)

    # Scanning pending tasks should reclaim the zombie task immediately
    pending = worker.find_pending_code_tasks()
    assert len(pending) == 1
    assert pending[0]["id"] == "task_zombie_001"
    assert pending[0]["status"] == "pending"
    assert pending[0]["owner_account"] is None


def test_live_pid_with_reused_process_identity_is_recovered(temp_env, monkeypatch):
    import tools.copilot_queue_worker as queue_worker_module

    state_dir = temp_env["state_dir"]
    tasks_dir = state_dir / "tasks"
    worker = CopilotQueueWorker(state_dir=state_dir, dry_run=True)
    monkeypatch.setattr(queue_worker_module, "_process_identity", lambda _pid: "current-process-identity")
    task_id = "task_reused_pid_001"
    (tasks_dir / f"{task_id}.json").write_text(
        json.dumps({
            "id": task_id,
            "kind": "code",
            "spec": "Recover lease from prior process instance",
            "status": "claimed",
            "owner_account": "copilot-w1",
            "owner_pid": os.getpid(),
            "owner_process_identity": "prior-process-creation-identity",
        }),
        encoding="utf-8",
    )

    pending = worker.find_pending_code_tasks()

    assert [task["id"] for task in pending] == [task_id]
    assert pending[0]["owner_account"] is None


@pytest.mark.asyncio
async def test_targeted_task_polling_wait(temp_env):
    """Verifies run() with target_task_id waits for task arrival and executes cleanly."""
    state_dir = temp_env["state_dir"]
    tasks_dir = state_dir / "tasks"
    repo_dir = temp_env["repo_dir"]
    worker = CopilotQueueWorker(state_dir=state_dir, dry_run=True, repo_root=repo_dir)

    target_id = "task_targeted_async_001"

    async def _delayed_task_write():
        await asyncio.sleep(0.5)
        task = {
            "id": target_id,
            "kind": "code",
            "spec": "Scaffold edge sensor",
            "status": "pending",
            "target_repo": str(repo_dir),
        }
        with open(tasks_dir / f"{target_id}.json", "w", encoding="utf-8") as f:
            json.dump(task, f)

    write_task = asyncio.create_task(_delayed_task_write())
    # Worker runs with once=True, waiting for target_id
    await worker.run(once=True, target_task_id=target_id, timeout=10.0)
    await write_task

    # Verify task was claimed, executed and completed
    with open(tasks_dir / f"{target_id}.json", "r", encoding="utf-8") as f:
        finished = json.load(f)
    assert finished["status"] == "done"

    # Verify checkpoint exists
    checkpoint_file = state_dir / "checkpoints" / f"{target_id}.json"
    assert checkpoint_file.exists()


@pytest.mark.asyncio
async def test_preflight_worktree_self_healing(temp_env):
    """Verifies worktree self-healing when stale branch or orphaned worktree exists."""
    state_dir = temp_env["state_dir"]
    repo_dir = temp_env["repo_dir"]
    worker = CopilotQueueWorker(state_dir=state_dir, dry_run=False, repo_root=repo_dir)

    task_id = "task_self_heal_001"
    branch_name = f"task/{task_id}"

    # Manually create branch first (simulating interrupted run)
    subprocess.run(["git", "branch", branch_name], cwd=str(repo_dir), check=True)

    # provision_worktree should heal and succeed without error
    wt_dir = await worker.provision_worktree(task_id, branch_name, target_repo=repo_dir)
    assert wt_dir.exists()
    assert (wt_dir / ".git").exists()

    # Clean up worktree
    await worker.teardown_worktree(wt_dir, branch_name=branch_name, task_id=task_id, commit=False, repo_root=repo_dir)
    assert not wt_dir.exists()


@pytest.mark.asyncio
async def test_dynamic_target_repo_routing(temp_env):
    """Verifies worktree is provisioned inside target_repo instead of default repo."""
    state_dir = temp_env["state_dir"]
    repo_dir = temp_env["repo_dir"]
    worker = CopilotQueueWorker(state_dir=state_dir, dry_run=False)

    task_id = "task_cross_repo_001"
    branch_name = f"task/{task_id}"

    wt_dir = await worker.provision_worktree(task_id, branch_name, target_repo=repo_dir)
    # Worktree should be inside repo_dir/.worktrees/
    expected_parent = repo_dir / ".worktrees"
    assert wt_dir.parent == expected_parent
    assert wt_dir.exists()

    # Teardown with target_repo
    await worker.teardown_worktree(wt_dir, branch_name=branch_name, task_id=task_id, commit=False, repo_root=repo_dir)
    assert not wt_dir.exists()


def test_cmd_run_task_dry_run_e2e(temp_env, capsys):
    """Tests cmd_run_task end-to-end in dry-run mode."""
    state_dir = temp_env["state_dir"]
    repo_dir = temp_env["repo_dir"]

    args = argparse.Namespace(
        spec="Test E2E Background Task",
        kind="code",
        state_dir=str(state_dir),
        target_repo=str(repo_dir),
        no_antigravity=True,
        conversation_id=None,
        model=None,
        auto_tier="balance",
        dry_run=True,
        timeout=10.0,
    )

    cmd_run_task(args)

    captured = capsys.readouterr()
    assert "[DISPATCH]" in captured.out
    assert "[CLAIMED]" in captured.out
    assert "[WORKTREE]" in captured.out
    assert "[COMPLETED]" in captured.out
