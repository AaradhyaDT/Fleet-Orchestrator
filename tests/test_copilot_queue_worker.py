from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
import pytest

from tools.copilot_queue_worker import CopilotQueueWorker, resolve_state_dir


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Path:
    state_dir = tmp_path / "orchestrator-state"
    state_dir.mkdir(parents=True)
    (state_dir / "tasks").mkdir()
    (state_dir / "checkpoints").mkdir()
    (state_dir / "live-status").mkdir()
    return state_dir


def test_resolve_state_dir_explicit(temp_state_dir: Path):
    resolved = resolve_state_dir(str(temp_state_dir))
    assert resolved == temp_state_dir


def test_round_robin_account_selection(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    worker.ready_accounts = [
        {"worker_id": "copilot-w1", "name": "acc1", "token": "tok1", "has_token": True},
        {"worker_id": "copilot-w2", "name": "acc2", "token": "tok2", "has_token": True},
    ]

    acc1 = worker.get_next_account()
    acc2 = worker.get_next_account()
    acc3 = worker.get_next_account()

    assert acc1["worker_id"] == "copilot-w1"
    assert acc2["worker_id"] == "copilot-w2"
    assert acc3["worker_id"] == "copilot-w1"


def test_persistent_round_robin_across_worker_instances(temp_state_dir: Path):
    """Verifies that separate worker processes/invocations maintain circular round-robin rotation."""
    accounts = [
        {"worker_id": "copilot-w1", "name": "acc1", "token": "tok1", "has_token": True},
        {"worker_id": "copilot-w2", "name": "acc2", "token": "tok2", "has_token": True},
        {"worker_id": "copilot-w3", "name": "acc3", "token": "tok3", "has_token": True},
    ]

    # Process 1
    w1 = CopilotQueueWorker(state_dir=temp_state_dir)
    w1.ready_accounts = accounts
    acc1 = w1.get_next_account()

    # Process 2 (separate instance simulating separate CLI run)
    w2 = CopilotQueueWorker(state_dir=temp_state_dir)
    w2.ready_accounts = accounts
    acc2 = w2.get_next_account()

    # Process 3
    w3 = CopilotQueueWorker(state_dir=temp_state_dir)
    w3.ready_accounts = accounts
    acc3 = w3.get_next_account()

    # Process 4 (wrap around circularly)
    w4 = CopilotQueueWorker(state_dir=temp_state_dir)
    w4.ready_accounts = accounts
    acc4 = w4.get_next_account()

    assert acc1["worker_id"] == "copilot-w1"
    assert acc2["worker_id"] == "copilot-w2"
    assert acc3["worker_id"] == "copilot-w3"
    assert acc4["worker_id"] == "copilot-w1"



def test_find_pending_code_tasks(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)

    # 1. Pending code task (should be picked up)
    t1 = {
        "id": "task_2026-10-08_001",
        "kind": "code",
        "spec": "Write unit tests",
        "status": "pending",
        "owner_account": None,
    }
    # 2. Text pending task (should NOT be picked up by copilot code worker)
    t2 = {
        "id": "task_2026-10-08_002",
        "kind": "text",
        "spec": "Write architecture overview",
        "status": "pending",
        "owner_account": None,
    }
    # 3. Already claimed code task (should NOT be picked up)
    t3 = {
        "id": "task_2026-10-08_003",
        "kind": "code",
        "spec": "Refactor router",
        "status": "claimed",
        "owner_account": "copilot-w1",
    }
    # 4. Completed code task (should NOT be picked up)
    t4 = {
        "id": "task_2026-10-08_004",
        "kind": "code",
        "spec": "Done task",
        "status": "done",
        "owner_account": "copilot-w2",
    }

    for t in [t1, t2, t3, t4]:
        with open(temp_state_dir / "tasks" / f"{t['id']}.json", "w", encoding="utf-8") as f:
            json.dump(t, f)

    pending = worker.find_pending_code_tasks()
    assert len(pending) == 1
    assert pending[0]["id"] == "task_2026-10-08_001"


def test_claim_task_optimistic_locking(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    account = {"worker_id": "copilot-w5", "name": "worker5"}

    t1 = {
        "id": "task_2026-10-08_005",
        "kind": "code",
        "spec": "Add helper function",
        "status": "pending",
        "owner_account": None,
    }
    task_file = temp_state_dir / "tasks" / "task_2026-10-08_005.json"
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(t1, f)

    claimed = worker.claim_task("task_2026-10-08_005", account)
    assert claimed is not None
    assert claimed["status"] == "claimed"
    assert claimed["owner_account"] == "copilot-w5"
    assert claimed["claim_token"]
    assert claimed["branch_name"] == "task/task_2026-10-08_005"

    # Verify disk state
    with open(task_file, "r", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["status"] == "claimed"
    assert on_disk["owner_account"] == "copilot-w5"

    # Verify live-status written
    status_file = temp_state_dir / "live-status" / "copilot-w5.json"
    assert status_file.exists()
    with open(status_file, "r", encoding="utf-8") as f:
        status_data = json.load(f)
    assert status_data["current_task_id"] == "task_2026-10-08_005"

    # Attempting to claim again should fail (optimistic lock rejection)
    another_account = {"worker_id": "copilot-w6", "name": "worker6"}
    re_claimed = worker.claim_task("task_2026-10-08_005", another_account)
    assert re_claimed is None


@pytest.mark.parametrize("pid_field", ["missing", "null"])
def test_legacy_claim_without_pid_waits_for_timeout_and_grace(temp_state_dir: Path, pid_field: str):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = f"task_legacy_pid_{pid_field}"
    task = {
        "id": task_id,
        "kind": "code",
        "spec": "Recover old legacy claim",
        "status": "claimed",
        "owner_account": "copilot-w1",
        "timeout": 30,
        "updated_at": (datetime.now(timezone.utc) - timedelta(seconds=149)).isoformat(),
    }
    if pid_field == "null":
        task["owner_pid"] = None
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")

    assert worker.find_pending_code_tasks() == []

    task["updated_at"] = (datetime.now(timezone.utc) - timedelta(seconds=151)).isoformat()
    task_file.write_text(json.dumps(task), encoding="utf-8")
    pending = worker.find_pending_code_tasks()

    assert [item["id"] for item in pending] == [task_id]
    assert pending[0]["owner_account"] is None
    assert pending[0]["owner_pid"] is None


def test_legacy_claim_without_timestamp_uses_file_mtime(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "task_legacy_mtime"
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task_file.write_text(
        json.dumps({
            "id": task_id,
            "kind": "code",
            "status": "claimed",
            "owner_account": "copilot-w1",
            "owner_pid": None,
            "timeout": 30,
        }),
        encoding="utf-8",
    )

    os.utime(task_file, (datetime.now().timestamp() - 151, datetime.now().timestamp() - 151))
    pending = worker.find_pending_code_tasks()

    assert [item["id"] for item in pending] == [task_id]


def test_legacy_claim_uses_claimed_at_when_updated_at_is_missing(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "task_legacy_claimed_at"
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task_file.write_text(
        json.dumps({
            "id": task_id,
            "kind": "code",
            "status": "claimed",
            "owner_account": "copilot-w1",
            "owner_pid": None,
            "timeout": 30,
            "claimed_at": (datetime.now(timezone.utc) - timedelta(seconds=151)).isoformat(),
        }),
        encoding="utf-8",
    )

    assert [item["id"] for item in worker.find_pending_code_tasks()] == [task_id]


def test_legacy_claim_without_timeout_uses_600_second_default(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "task_legacy_default_timeout"
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task = {
        "id": task_id,
        "kind": "code",
        "status": "claimed",
        "owner_account": "copilot-w1",
        "owner_pid": None,
    }
    task["updated_at"] = (datetime.now(timezone.utc) - timedelta(seconds=719)).isoformat()
    task_file.write_text(json.dumps(task), encoding="utf-8")

    assert worker.find_pending_code_tasks() == []

    task["updated_at"] = (datetime.now(timezone.utc) - timedelta(seconds=721)).isoformat()
    task_file.write_text(json.dumps(task), encoding="utf-8")
    assert [item["id"] for item in worker.find_pending_code_tasks()] == [task_id]


def test_intelligence_timeout_floor_applies_to_legacy_claim(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "task_legacy_intelligence_floor"
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task = {
        "id": task_id,
        "kind": "code",
        "status": "claimed",
        "owner_account": "copilot-w1",
        "owner_pid": None,
        "timeout": 30,
        "auto_tier": "intelligence",
    }
    task["updated_at"] = (datetime.now(timezone.utc) - timedelta(seconds=719)).isoformat()
    task_file.write_text(json.dumps(task), encoding="utf-8")

    assert worker.find_pending_code_tasks() == []

    task["updated_at"] = (datetime.now(timezone.utc) - timedelta(seconds=721)).isoformat()
    task_file.write_text(json.dumps(task), encoding="utf-8")
    assert [item["id"] for item in worker.find_pending_code_tasks()] == [task_id]


def test_claim_token_fences_old_completion_and_failure(temp_state_dir: Path, monkeypatch):
    import tools.copilot_queue_worker as queue_worker_module

    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "task_stale_claim_fence"
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task_file.write_text(
        json.dumps({
            "id": task_id,
            "kind": "code",
            "spec": "Do not overwrite a newer claim",
            "status": "pending",
            "owner_account": None,
        }),
        encoding="utf-8",
    )
    first_account = {"worker_id": "copilot-w1", "name": "worker1"}

    old_claim = worker.claim_task(task_id, first_account)
    assert old_claim is not None
    old_token = old_claim["claim_token"]
    old_claim["owner_pid"] = 99999999
    task_file.write_text(json.dumps(old_claim), encoding="utf-8")
    monkeypatch.setattr(queue_worker_module, "is_pid_alive", lambda _pid: False)

    assert [item["id"] for item in worker.find_pending_code_tasks()] == [task_id]
    new_claim = worker.claim_task(task_id, first_account)
    assert new_claim is not None
    assert new_claim["claim_token"] != old_token

    assert not worker.submit_checkpoint_and_complete(
        task_id=task_id,
        account=first_account,
        summary="Late checkpoint",
        claim_token=old_token,
    )
    worker._mark_task_blocked(task_id, first_account, "Late failure", claim_token=old_token)

    current = json.loads(task_file.read_text(encoding="utf-8"))
    assert current["status"] == "claimed"
    assert current["owner_account"] == "copilot-w1"
    assert current["claim_token"] == new_claim["claim_token"]
    assert not (temp_state_dir / "checkpoints" / f"{task_id}.json").exists()
    second_status = json.loads(
        (temp_state_dir / "live-status" / "copilot-w1.json").read_text(encoding="utf-8")
    )
    assert second_status["current_task_id"] == task_id


def test_stale_claim_sentinel_does_not_prevent_claim(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "task_stale_claim_sentinel"
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task_file.write_text(
        json.dumps({"id": task_id, "kind": "code", "status": "pending", "owner_account": None}),
        encoding="utf-8",
    )
    task_file.with_suffix(f".claim_{task_id}").touch()

    claimed = worker.claim_task(task_id, {"worker_id": "copilot-w1", "name": "worker1"})

    assert claimed is not None


def test_concurrent_claim_recovery_returns_single_new_claim(temp_state_dir: Path, monkeypatch):
    import tools.copilot_queue_worker as queue_worker_module

    worker1 = CopilotQueueWorker(state_dir=temp_state_dir)
    worker2 = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "task_concurrent_reclaim"
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task_file.write_text(
        json.dumps({
            "id": task_id,
            "kind": "code",
            "status": "claimed",
            "owner_account": "copilot-w-old",
            "owner_pid": 99999999,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(queue_worker_module, "is_pid_alive", lambda _pid: False)
    both_scans_complete = threading.Barrier(2)

    def recover_and_claim(worker, worker_id):
        candidates = worker.find_pending_code_tasks()
        both_scans_complete.wait()
        if not candidates:
            return None
        return worker.claim_task(task_id, {"worker_id": worker_id, "name": worker_id})

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(
            lambda args: recover_and_claim(*args),
            [(worker1, "copilot-w1"), (worker2, "copilot-w2")],
        ))

    successful = [claim for claim in claims if claim is not None]
    assert len(successful) == 1
    assert successful[0]["claim_token"]
    on_disk = json.loads(task_file.read_text(encoding="utf-8"))
    assert on_disk["claim_token"] == successful[0]["claim_token"]
    assert on_disk["owner_account"] == successful[0]["owner_account"]


def test_submit_checkpoint_and_complete(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    account = {"worker_id": "copilot-w1", "name": "worker1"}
    task_id = "task_2026-10-08_006"

    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump({
            "id": task_id,
            "kind": "code",
            "spec": "Implement feature X",
            "status": "claimed",
            "owner_account": "copilot-w1",
        }, f)

    worker.submit_checkpoint_and_complete(
        task_id=task_id,
        account=account,
        summary="Successfully implemented feature X and verified tests.",
        branch_name=f"task/{task_id}",
        commit_sha="c0ffee1",
    )

    # Checkpoint verification
    cp_file = temp_state_dir / "checkpoints" / f"{task_id}.json"
    assert cp_file.exists()
    with open(cp_file, "r", encoding="utf-8") as f:
        cp_data = json.load(f)
    assert cp_data["task_id"] == task_id
    assert cp_data["kind"] == "code"
    assert cp_data["commit_sha"] == "c0ffee1"
    assert cp_data["submitted_by"] == "copilot-w1"
    assert cp_data["result_text"] is None

    # Task status verification
    with open(task_file, "r", encoding="utf-8") as f:
        task_data = json.load(f)
    assert task_data["status"] == "done"

    # Live-status cleared verification
    status_file = temp_state_dir / "live-status" / "copilot-w1.json"
    with open(status_file, "r", encoding="utf-8") as f:
        status_data = json.load(f)
    assert status_data["current_task_id"] is None


@pytest.mark.asyncio
async def test_end_to_end_process_one_task(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir, dry_run=True)
    worker.ready_accounts = [
        {"worker_id": "copilot-w1", "name": "tester", "token": "dummy_token", "has_token": True}
    ]

    task_id = "task_2026-10-08_007"
    with open(temp_state_dir / "tasks" / f"{task_id}.json", "w", encoding="utf-8") as f:
        json.dump({
            "id": task_id,
            "kind": "code",
            "spec": "Add sum(a, b) function",
            "status": "pending",
            "owner_account": None,
        }, f)

    processed = await worker.process_one_task()
    assert processed is True

    # Confirm task is done
    with open(temp_state_dir / "tasks" / f"{task_id}.json", "r", encoding="utf-8") as f:
        task_data = json.load(f)
    assert task_data["status"] == "done"
    assert task_data["owner_account"] == "copilot-w1"

    # Confirm checkpoint was written
    cp_file = temp_state_dir / "checkpoints" / f"{task_id}.json"
    assert cp_file.exists()


def test_cooldown_tracking_and_rotation(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    worker.ready_accounts = [
        {"worker_id": "copilot-w1", "name": "acc1", "token": "tok1", "has_token": True, "monthly_credits": 10},
        {"worker_id": "copilot-w2", "name": "acc2", "token": "tok2", "has_token": True, "monthly_credits": 200},
    ]
    worker.accounts = list(worker.ready_accounts)

    # Initial round-robin picks w1
    assert worker.get_next_account()["worker_id"] == "copilot-w1"

    # Consume credits to trigger quota exhaustion on w1
    worker.record_credit_usage("copilot-w1", 10)
    assert worker.is_in_cooldown("copilot-w1") is True

    # Next account selection must bypass w1 and pick w2
    next_acc = worker.get_next_account()
    assert next_acc is not None
    assert next_acc["worker_id"] == "copilot-w2"

    # Check live status recorded cooldown
    status_file = temp_state_dir / "live-status" / "copilot-w1.json"
    assert status_file.exists()
    with open(status_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["status"] == "cooldown"
    assert data["credits_used"] >= 10
    assert data["credits_remaining"] == 0
    assert data["cooldown_until"] is not None


def test_credit_telemetry_persistence_and_reload(temp_state_dir: Path):
    # Setup live status with pre-existing credit usage
    status_file = temp_state_dir / "live-status" / "copilot-w3.json"
    status_file.write_text(
        json.dumps({
            "account": "copilot-w3",
            "status": "idle",
            "credits_used": 45,
            "monthly_credits": 200,
            "credits_remaining": 155,
        }),
        encoding="utf-8",
    )

    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    worker.accounts = [{"worker_id": "copilot-w3", "name": "w3", "has_token": True, "monthly_credits": 200}]
    worker._load_live_status_telemetry()

    assert worker.account_credits.get("copilot-w3") == 45


@pytest.mark.asyncio
async def test_git_worktree_provision_and_teardown(tmp_path: Path):
    import subprocess

    # 1. Initialize dummy git repo
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)

    dummy_file = repo_dir / "README.md"
    dummy_file.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "tasks").mkdir()
    (state_dir / "checkpoints").mkdir()
    (state_dir / "live-status").mkdir()

    worktree_root = tmp_path / ".worktrees"
    worker = CopilotQueueWorker(
        state_dir=state_dir,
        repo_root=repo_dir,
        worktree_root=worktree_root,
        dry_run=False,
    )

    task_id = "task_worktree_test_01"
    branch_name = f"task/{task_id}"

    # Provision worktree
    wt_dir = await worker.provision_worktree(task_id, branch_name)
    assert wt_dir.exists()
    assert (wt_dir / "README.md").exists()

    # Simulate code generation by creating a new file
    new_code = wt_dir / "feature.py"
    new_code.write_text("def hello(): return 'world'\n", encoding="utf-8")

    # Teardown worktree and commit
    sha = await worker.teardown_worktree(wt_dir, branch_name=branch_name, task_id=task_id, commit=True)
    assert sha is not None
    assert len(sha) >= 7

    # Verify worktree directory was cleaned up
    assert not wt_dir.exists()

    # Verify commit exists on branch
    branch_commit = subprocess.run(
        ["git", "rev-parse", branch_name],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    assert branch_commit.stdout.strip() == sha


@pytest.mark.asyncio
async def test_multi_process_claim_concurrency(temp_state_dir: Path):
    worker1 = CopilotQueueWorker(state_dir=temp_state_dir, dry_run=True)
    worker1.ready_accounts = [{"worker_id": "copilot-w1", "name": "acc1", "token": "tok1", "has_token": True}]

    worker2 = CopilotQueueWorker(state_dir=temp_state_dir, dry_run=True)
    worker2.ready_accounts = [{"worker_id": "copilot-w2", "name": "acc2", "token": "tok2", "has_token": True}]

    t1 = {
        "id": "task_concurrent_001",
        "kind": "code",
        "spec": "Module A",
        "status": "pending",
        "owner_account": None,
    }
    t2 = {
        "id": "task_concurrent_002",
        "kind": "code",
        "spec": "Module B",
        "status": "pending",
        "owner_account": None,
    }

    for t in [t1, t2]:
        with open(temp_state_dir / "tasks" / f"{t['id']}.json", "w", encoding="utf-8") as f:
            json.dump(t, f)

    # Worker 1 claims task 1
    c1 = worker1.claim_task("task_concurrent_001", worker1.ready_accounts[0])
    assert c1 is not None

    # Worker 2 process_one_task should skip already claimed task 1 and process task 2
    res2 = await worker2.process_one_task()
    assert res2 is True

    # Check task 2 completed by worker 2
    with open(temp_state_dir / "tasks" / "task_concurrent_002.json", "r", encoding="utf-8") as f:
        t2_data = json.load(f)
    assert t2_data["status"] == "done"
    assert t2_data["owner_account"] == "copilot-w2"


@pytest.mark.asyncio
async def test_in_process_concurrency_execution(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir, dry_run=True, concurrency=2)
    worker.ready_accounts = [
        {"worker_id": "copilot-w1", "name": "acc1", "token": "tok1", "has_token": True},
        {"worker_id": "copilot-w2", "name": "acc2", "token": "tok2", "has_token": True},
    ]

    t1 = {
        "id": "task_pool_001",
        "kind": "code",
        "spec": "Subtask 1",
        "status": "pending",
        "owner_account": None,
    }
    t2 = {
        "id": "task_pool_002",
        "kind": "code",
        "spec": "Subtask 2",
        "status": "pending",
        "owner_account": None,
    }

    for t in [t1, t2]:
        with open(temp_state_dir / "tasks" / f"{t['id']}.json", "w", encoding="utf-8") as f:
            json.dump(t, f)

    # Process tasks concurrently
    res1, res2 = await asyncio.gather(
        worker.process_one_task(),
        worker.process_one_task(),
    )

    assert res1 is True
    assert res2 is True

    # Both tasks must be done
    for tid in ["task_pool_001", "task_pool_002"]:
        with open(temp_state_dir / "tasks" / f"{tid}.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "done"
        assert data["owner_account"] in ["copilot-w1", "copilot-w2"]


@pytest.mark.asyncio
async def test_teardown_worktree_prune_branch(tmp_path: Path):
    import subprocess
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    (repo_dir / "README.md").write_text("# Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "tasks").mkdir()
    (state_dir / "checkpoints").mkdir()
    (state_dir / "live-status").mkdir()

    worker = CopilotQueueWorker(
        state_dir=state_dir,
        repo_root=repo_dir,
        worktree_root=tmp_path / ".worktrees",
        dry_run=False,
    )

    task_id = "task_prune_test_01"
    branch_name = f"task/{task_id}"

    wt_dir = await worker.provision_worktree(task_id, branch_name)
    assert wt_dir.exists()

    # Teardown with prune_branch=True
    sha = await worker.teardown_worktree(wt_dir, branch_name=branch_name, task_id=task_id, commit=True, prune_branch=True)
    assert sha is not None
    assert not wt_dir.exists()

    # Verify branch was deleted
    check_branch = subprocess.run(
        ["git", "branch", "--list", branch_name],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
    )
    assert check_branch.stdout.strip() == ""


def test_prune_completed_task_branches(tmp_path: Path):
    import subprocess
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    (repo_dir / "README.md").write_text("# Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

    # Create dummy branch
    branch_name = "task/task_done_test_99"
    subprocess.run(["git", "branch", branch_name], cwd=str(repo_dir), check=True)

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    tasks_dir = state_dir / "tasks"
    tasks_dir.mkdir()
    (state_dir / "checkpoints").mkdir()
    (state_dir / "live-status").mkdir()

    # Create completed task file
    task_file = tasks_dir / "task_done_test_99.json"
    task_file.write_text(json.dumps({"id": "task_done_test_99", "status": "done"}), encoding="utf-8")

    worker = CopilotQueueWorker(
        state_dir=state_dir,
        repo_root=repo_dir,
        worktree_root=tmp_path / ".worktrees",
    )

    pruned = worker.prune_completed_task_branches()
    assert pruned == 1

    # Verify branch no longer exists
    check = subprocess.run(["git", "branch", "--list", branch_name], cwd=str(repo_dir), capture_output=True, text=True)
    assert check.stdout.strip() == ""


@pytest.mark.asyncio
async def test_worker_drain_exit_when_empty_immediate(temp_state_dir: Path):
    """Verifies that with empty queue and exit_when_empty=True, worker terminates promptly."""
    worker = CopilotQueueWorker(state_dir=temp_state_dir, poll_interval=0.05)
    await asyncio.wait_for(worker.run(exit_when_empty=True), timeout=2.0)
    assert not worker._running or worker.in_flight_tasks == 0


@pytest.mark.asyncio
async def test_worker_drain_with_concurrency(temp_state_dir: Path):
    """Verifies that concurrent workers exit cleanly when queue is drained."""
    worker = CopilotQueueWorker(state_dir=temp_state_dir, concurrency=3, poll_interval=0.05)
    await asyncio.wait_for(worker.run(exit_when_empty=True), timeout=2.0)
    assert not worker._running


@pytest.mark.asyncio
async def test_worker_idle_timeout(temp_state_dir: Path):
    """Verifies that worker exits automatically once idle_timeout elapses."""
    worker = CopilotQueueWorker(state_dir=temp_state_dir, poll_interval=0.05)
    t0 = asyncio.get_event_loop().time()
    await asyncio.wait_for(worker.run(idle_timeout=0.15), timeout=2.0)
    elapsed = asyncio.get_event_loop().time() - t0
    assert elapsed >= 0.1


def test_legacy_claim_with_non_finite_timeout_uses_default(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "task_legacy_non_finite_timeout"
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task_file.write_text(
        json.dumps({
            "id": task_id,
            "kind": "code",
            "status": "claimed",
            "owner_account": "copilot-w1",
            "owner_pid": None,
            "timeout": "Infinity",
            "updated_at": (datetime.now(timezone.utc) - timedelta(seconds=721)).isoformat(),
        }),
        encoding="utf-8",
    )

    assert [item["id"] for item in worker.find_pending_code_tasks()] == [task_id]


def test_stale_claim_id_cannot_escape_tasks_directory(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "../../escaped-lock"
    task_file = temp_state_dir / "tasks" / "task_traversal.json"
    task_file.write_text(
        json.dumps({
            "id": task_id,
            "kind": "code",
            "status": "claimed",
            "owner_account": "copilot-w-old",
            "owner_pid": 99999999,
        }),
        encoding="utf-8",
    )

    assert [item["id"] for item in worker.find_pending_code_tasks()] == [task_id]
    assert not (temp_state_dir.parent / "escaped-lock.lock").exists()


def test_task_claim_refuses_symlinked_lock_file(temp_state_dir: Path):
    worker = CopilotQueueWorker(state_dir=temp_state_dir)
    task_id = "task_symlink_lock"
    task_file = temp_state_dir / "tasks" / f"{task_id}.json"
    task_file.write_text(
        json.dumps({"id": task_id, "kind": "code", "status": "pending", "owner_account": None}),
        encoding="utf-8",
    )
    outside_target = temp_state_dir.parent / "outside-lock-target"
    try:
        os.symlink(outside_target, worker._task_lock_path(task_id))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"file symlinks unavailable: {exc}")

    claimed = worker.claim_task(task_id, {"worker_id": "copilot-w1", "name": "worker1"})

    assert claimed is None
    assert not outside_target.exists()
    assert json.loads(task_file.read_text(encoding="utf-8"))["status"] == "pending"
