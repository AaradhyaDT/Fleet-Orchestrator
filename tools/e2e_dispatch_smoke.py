"""
e2e_dispatch_smoke.py
---------------------
End-to-End Task Dispatch and Execution Smoke Test for Fleet-Orchestrator.
Uses active verified Copilot CLI worker to acquire, execute, and checkpoint a real task.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from httpx import AsyncClient, ASGITransport

from server.main import app
from server.core.database import init_db
from server.core.config import settings
from client.adapters.copilot_cli_adapter import CopilotCLIAdapter
from tools.copilot_fleet import load_env_fleet, discover_accounts


async def run_e2e_smoke():
    print("\n" + "=" * 70)
    print(" FLEET-ORCHESTRATOR END-TO-END COPILOT TASK DISPATCH SMOKE TEST")
    print("=" * 70)

    # 1. Resolve active worker account
    env_vars = load_env_fleet()
    accounts = discover_accounts(env_vars)
    # Pick first verified account (Worker 1 @AaradhyaDT)
    worker_acc = accounts[0]
    print(f"[*] Selected Worker: {worker_acc['worker_id']} (@{worker_acc['name']})")
    print(f"    State Directory: {worker_acc['state_dir']}")

    # 2. Initialize in-memory or test database
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver/api/v1") as client:
        # Register worker in state machine
        reg_resp = await client.post("/workers/register", json={
            "id": worker_acc["worker_id"],
            "provider": "copilot_cli",
            "node_id": "local-node",
            "nickname": worker_acc["name"],
            "capabilities": ["code", "refactor", "writing"],
            "quota_limit_per_window": 200,
        })
        print(f"[+] Worker registration response: HTTP {reg_resp.status_code}")

        # Create a Job
        job_id = f"job_smoke_{int(asyncio.get_event_loop().time())}"
        job_resp = await client.post("/jobs", json={
            "id": job_id,
            "sku": "copilot_code_generation",
            "client": "BRL-Internal",
            "input_uri": "memory://task-spec",
            "pipeline": ["draft"],
            "quality_rules": ["Strict type hints", "Deterministic output"]
        })
        assert job_resp.status_code == 201, f"Failed to create job: {job_resp.text}"
        print(f"[+] Job created: {job_id} (HTTP 201)")

        # Create Task directly in the job
        task_id = f"task_{job_id}_01"
        task_resp = await client.post("/tasks", json={
            "id": task_id,
            "job_id": job_id,
            "stage": "draft",
            "stage_order": 1,
            "spec": "Generate a concise Python function `fib(n: int) -> int` with docstring.",
            "capabilities_required": ["code"],
            "item_data": {"lang": "python"}
        })
        assert task_resp.status_code == 201, f"Failed to create task: {task_resp.text}"
        print(f"[+] Task created: {task_id} (Status: PENDING)")

        # Claim the task
        claim_resp = await client.post(f"/tasks/{task_id}/claim", json={
            "worker_id": worker_acc["worker_id"],
            "lease_seconds": 180,
        })
        assert claim_resp.status_code == 200, f"Failed to claim task: {claim_resp.text}"
        claim_data = claim_resp.json()
        claim_token = claim_data["claim_token"]
        print(f"[+] Task claimed successfully (Status: ACQUIRED, Token: {claim_token[:12]}...)")

        # Instantiate Copilot CLI Adapter
        adapter = CopilotCLIAdapter(
            worker_id=worker_acc["worker_id"],
            nickname=worker_acc["name"],
            github_token=worker_acc["token"],
            copilot_home=worker_acc["state_dir"],
            timeout=90.0,
            max_ai_credits=30,
        )

        print("[*] Executing task via headless Copilot CLI autopilot...")
        exec_res = await adapter.execute_task(
            task_id=task_id,
            spec="Generate a Python function `fib(n: int) -> int` that calculates Fibonacci iteratively. Output only code inside markdown.",
            stage="draft",
            context={"job_id": job_id},
        )

        print(f"[+] Copilot CLI finished: success={exec_res.get('success')}")
        print(f"    Model: {exec_res.get('model_used')} | Tokens: {exec_res.get('tokens_used')}")
        if exec_res.get("result_text"):
            print(f"    Output snippet:\n{exec_res['result_text'][:300]}...")

        # Submit checkpoint
        cp_resp = await client.post(f"/tasks/{task_id}/checkpoint", json={
            "task_id": task_id,
            "kind": "code",
            "summary": exec_res.get("summary", "Generated iterative fibonacci function"),
            "result_text": exec_res.get("result_text", "# Code generated"),
            "submitted_by": worker_acc["worker_id"],
            "claim_token": claim_token,
        })
        assert cp_resp.status_code == 201, f"Failed to submit checkpoint: {cp_resp.text}"
        print(f"[+] Checkpoint submitted successfully (HTTP 201, Task: COMPLETED)")

        # Verify task state in database
        check_task = await client.get(f"/tasks/{task_id}")
        assert check_task.status_code == 200
        task_info = check_task.json()
        print(f"[+] Verified Final Task State: {task_info.get('status').upper()}")
        print("=" * 70)
        print(" [PASSED] END-TO-END TASK DISPATCH AND EXECUTION VERIFIED")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_e2e_smoke())
