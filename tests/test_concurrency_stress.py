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
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
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
    """An OS-lock waiter rechecks ownership after a different process claims."""
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

    worker2 = CopilotQueueWorker(state_dir=state_dir, dry_run=True)

    acc2 = {"worker_id": "copilot-w2", "name": "w2"}

    lock_path = worker2._task_lock_path(task_id)
    holder_code = """
import json, sys
from pathlib import Path
from tools.credit_ledger import FileLock, atomic_write_json
with FileLock(Path(sys.argv[1])):
    print('LOCKED', flush=True)
    sys.stdin.readline()
    path = Path(sys.argv[2])
    task = json.loads(path.read_text())
    task.update(status='claimed', owner_account='copilot-w1', **{'claim_token': 'other-claim'})
    atomic_write_json(path, task)
"""
    holder = subprocess.Popen(
        [sys.executable, "-c", holder_code, str(lock_path), str(task_file)],
        cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    entered = threading.Event()
    try:
        assert holder.stdout.readline().strip() == "LOCKED"
        def contend():
            entered.set()
            return worker2.claim_task(task_id, acc2)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(contend)
            assert entered.wait(timeout=2)
            assert not future.done()
            _, errors = holder.communicate(input="\n", timeout=10)
            assert holder.returncode == 0, errors
            assert future.result(timeout=10) is None
        assert json.loads(task_file.read_text())["owner_account"] == "copilot-w1"
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.communicate(timeout=5)
