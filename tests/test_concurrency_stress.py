"""
test_concurrency_stress.py
--------------------------
High-contention concurrency stress tests for Copilot queue workers:
- Verifies zero duplicate claims across concurrent workers.
- Verifies 100% completion rate and checkpoint generation.
- Verifies atomic claim token collision resolution.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from tools.copilot_queue_worker import CopilotQueueWorker
from tools.stress_test_concurrency import run_stress_test


@pytest.mark.asyncio
async def test_high_contention_concurrent_claims(tmp_path: Path):
    """Stress tests 12 tasks across 4 concurrent workers under heavy claim contention."""
    success = await run_stress_test(
        num_tasks=12,
        num_workers=4,
        dry_run=True,
        temp_dir=tmp_path,
    )
    assert success is True


@pytest.mark.asyncio
async def test_atomic_claim_token_collision_rejection(tmp_path: Path):
    """Verifies that if a claim lock exists, another worker immediately rejects the claim."""
    state_dir = tmp_path / "orchestrator-state"
    tasks_dir = state_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (state_dir / "checkpoints").mkdir()
    (state_dir / "live-status").mkdir()

    task_id = "task_collision_001"
    task_file = tasks_dir / f"{task_id}.json"
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump({
            "id": task_id,
            "kind": "code",
            "spec": "Simulate race",
            "status": "pending",
            "owner_account": None,
        }, f)

    worker1 = CopilotQueueWorker(state_dir=state_dir, dry_run=True)
    worker2 = CopilotQueueWorker(state_dir=state_dir, dry_run=True)

    acc1 = {"worker_id": "copilot-w1", "name": "w1"}
    acc2 = {"worker_id": "copilot-w2", "name": "w2"}

    # Simulate another worker actively holding the atomic claim gate
    lock_path = task_file.with_suffix(f".claim_{task_id}")
    lock_path.write_text("locked", encoding="utf-8")

    # Worker 2 attempts to claim while locked -> must immediately return None
    claim_res = worker2.claim_task(task_id, acc2)
    assert claim_res is None

    # Release lock
    lock_path.unlink()

    # Now Worker 1 can claim normally
    claimed = worker1.claim_task(task_id, acc1)
    assert claimed is not None
    assert claimed["owner_account"] == "copilot-w1"
