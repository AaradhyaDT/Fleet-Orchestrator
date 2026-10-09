#!/usr/bin/env python3
import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.copilot_fleet import load_env_fleet, discover_accounts
from client.adapters.copilot_cli_adapter import CopilotCLIAdapter

async def audit_all_accounts():
    accs = discover_accounts(load_env_fleet())
    sem = asyncio.Semaphore(5)
    results = []

    async def test_worker(acc):
        async with sem:
            wid = acc["worker_id"]
            name = acc["name"]
            adapter = CopilotCLIAdapter(
                worker_id=wid,
                nickname=name,
                github_token=acc["token"],
                copilot_home=acc["state_dir"],
                timeout=45.0,
            )
            try:
                res = await adapter.execute_task(
                    task_id=f"audit_{wid}",
                    spec="Reply OK",
                    stage="canary",
                    context={},
                )
                success = res.get("success", False)
                model = res.get("model_used")
                credits_val = res.get("credits_used", 0.0)
                err = res.get("error") or ""
                quota_ex = res.get("quota_exhausted", False)
                return {
                    "worker_id": wid,
                    "name": name,
                    "success": success,
                    "model": model,
                    "credits": credits_val,
                    "error": err[:150] if err else "",
                    "quota_exhausted": quota_ex,
                }
            except Exception as e:
                return {
                    "worker_id": wid,
                    "name": name,
                    "success": False,
                    "model": None,
                    "credits": 0.0,
                    "error": str(e)[:150],
                    "quota_exhausted": False,
                }

    tasks = [test_worker(a) for a in accs]
    results = await asyncio.gather(*tasks)

    print("\n" + "=" * 80)
    print(" FLEET COPILOT HEALTH & QUOTA PROBE REPORT")
    print("=" * 80)
    passed = 0
    failed = 0
    quota_hits = 0
    for r in results:
        status = "PASS" if r["success"] else "FAIL"
        if r["success"]:
            passed += 1
        else:
            failed += 1
            if r["quota_exhausted"] or "quota" in r["error"].lower() or "credit" in r["error"].lower():
                quota_hits += 1
        print(f"[{status}] {r['worker_id']:<12} {r['name']:<22} | credits={r['credits']:<5} | model={r['model'] or 'None':<18} | err={r['error']}")
    print("-" * 80)
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed} | Quota Hits: {quota_hits}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(audit_all_accounts())
