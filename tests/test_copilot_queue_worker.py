from __future__ import annotations

import json
from pathlib import Path
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
