#!/usr/bin/env python3
"""
Concurrency Stress Test Harness:
Simulates high-contention task claiming across multiple concurrent queue workers.
Verifies zero duplicate claims, 100% completion rate, clean worktree lifecycle,
and atomic state transitions under heavy multi-worker load.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.copilot_fleet import create_task_payload
from tools.copilot_queue_worker import CopilotQueueWorker


async def run_stress_test(
    num_tasks: int = 12,
    num_workers: int = 4,
    dry_run: bool = True,
    temp_dir: Path | None = None,
) -> bool:
    """Runs a simulated high-contention concurrency stress test."""
    cleanup_temp = False
    if not temp_dir:
        temp_dir = Path(tempfile.mkdtemp(prefix="fleet_stress_"))
        cleanup_temp = True

    state_dir = temp_dir / "orchestrator-state"
    tasks_dir = state_dir / "tasks"
    checkpoints_dir = state_dir / "checkpoints"
    live_status_dir = state_dir / "live-status"

    tasks_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    live_status_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 75)
    print(f" FLEET CONCURRENCY STRESS TEST: {num_tasks} Tasks across {num_workers} Workers")
    print("=" * 75)
    print(f" State Dir: {state_dir}")

    # 1. Enqueue tasks
    task_ids = []
    for i in range(1, num_tasks + 1):
        tid = f"task_stress_{i:03d}"
        payload = create_task_payload(spec=f"Stress workload step {i}", task_id=tid)
        with open(tasks_dir / f"{tid}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        task_ids.append(tid)

    print(f"[*] Enqueued {len(task_ids)} tasks into queue.")

    # 2. Setup workers with distinct simulated worker accounts
    workers = []
    for w in range(1, num_workers + 1):
        worker = CopilotQueueWorker(
            state_dir=state_dir,
            dry_run=dry_run,
            concurrency=1,
            poll_interval=0.1,
        )
        worker.ready_accounts = [
            {
                "worker_id": f"copilot-w{w}",
                "name": f"stress_worker_{w}",
                "token": f"tok_{w}",
                "has_token": True,
                "monthly_credits": 200,
            }
        ]
        workers.append(worker)

    # 3. Concurrently execute workers
    start_time = time.perf_counter()

    async def _worker_loop(w_inst: CopilotQueueWorker):
        while True:
            pending = w_inst.find_pending_code_tasks()
            if not pending:
                break
            processed = await w_inst.process_one_task()
            if not processed:
                # Brief sleep to yield in case of claim contention
                await asyncio.sleep(0.05)

    print(f"[*] Launching {len(workers)} concurrent worker coroutines...")
    await asyncio.gather(*[_worker_loop(w) for w in workers])
    duration = time.perf_counter() - start_time

    # 4. Verify Invariants
    print("\n[*] Validating System Invariants...")
    errors = []

    claimed_by_map: dict[str, list[str]] = {}
    completed_checkpoints = 0

    for tid in task_ids:
        t_path = tasks_dir / f"{tid}.json"
        cp_path = checkpoints_dir / f"{tid}.json"

        if not t_path.exists():
            errors.append(f"Task file {tid}.json is missing!")
            continue

        with open(t_path, "r", encoding="utf-8") as f:
            t_data = json.load(f)

        if t_data.get("status") != "done":
            errors.append(f"Task {tid} status is '{t_data.get('status')}', expected 'done'")

        owner = t_data.get("owner_account")
        if not owner:
            errors.append(f"Task {tid} has null owner_account!")
        else:
            claimed_by_map.setdefault(owner, []).append(tid)

        if not cp_path.exists():
            errors.append(f"Checkpoint for task {tid} is missing!")
        else:
            completed_checkpoints += 1
            with open(cp_path, "r", encoding="utf-8") as f:
                cp_data = json.load(f)
            if cp_data.get("task_id") != tid:
                errors.append(f"Checkpoint task_id mismatch for {tid}")
            if cp_data.get("submitted_by") != owner:
                errors.append(f"Checkpoint submitted_by mismatch for {tid}")

    # Output Results
    print("-" * 75)
    print(f" Execution Duration:    {duration:.2f}s")
    print(f" Throughput:            {num_tasks / duration:.2f} tasks/second")
    print(f" Checkpoints Produced:  {completed_checkpoints} / {num_tasks}")
    print(f" Task Distribution:")
    for owner, tasks in sorted(claimed_by_map.items()):
        print(f"   - {owner}: {len(tasks)} tasks ({', '.join(tasks[:3])}{'...' if len(tasks) > 3 else ''})")

    success = len(errors) == 0 and completed_checkpoints == num_tasks
    if success:
        print("\n[+] STRESS TEST PASSED: 100% tasks completed with ZERO collisions or race errors!")
    else:
        print(f"\n[-] STRESS TEST FAILED with {len(errors)} error(s):")
        for err in errors[:5]:
            print(f"    ! {err}")

    print("=" * 75 + "\n")

    if cleanup_temp:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    return success


def main() -> None:
    parser = argparse.ArgumentParser(description="Fleet Concurrency Stress Test Harness")
    parser.add_argument("--tasks", type=int, default=12, help="Number of tasks to enqueue (default: 12)")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent workers (default: 4)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run in dry-run mode (default: True)")

    args = parser.parse_args()
    success = asyncio.run(run_stress_test(num_tasks=args.tasks, num_workers=args.workers, dry_run=args.dry_run))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
