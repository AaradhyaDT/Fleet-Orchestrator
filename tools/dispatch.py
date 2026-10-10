#!/usr/bin/env python3
"""
tools/dispatch.py
-----------------
Lightweight 1-command Fleet Orchestrator Task Dispatcher.
Callable directly from VS Code terminal, PowerShell, or Antigravity:

Usage:
    python tools/dispatch.py "Refactor rate limiting tests" --repo Fleet-Orchestrator
    python tools/dispatch.py "Add telemetry logging" --repo brainstorm --tier balance
"""

import argparse
import json
import logging
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from client.antigravity_bridge import harvest_chat_context, harvest_antigravity_customizations

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dispatch")

TASKS_DIR = ROOT / "orchestrator-state" / "tasks"

def query_local_brain(prompt: str) -> dict:
    """Queries local fleet-master-3b at port 1234 for sub-50ms intent & duration routing."""
    import urllib.request
    try:
        payload = {
            "model": "fleet-master-3b",
            "messages": [
                {
                    "role": "system",
                    "content": "You are the high-speed Intent, Skill, and Task Time Allocation Router for the Aaradhya development ecosystem. Classify the incoming user intent into the exact lifecycle archetype, tier, 2D matrix cell, primary skill, auto_tier, and task time allocation in strict JSON format."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 150
        }
        req = urllib.request.Request(
            "http://127.0.0.1:1234/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as e:
        logger.warning(f"Local brain fallback (heuristic): {e}")
        return {
            "archetype": "ENGINEERING_DEV",
            "tier": "Tier 1",
            "matrix_cell": "(V0, R1)",
            "policy": "BRANCH_GUARD",
            "auto_tier": "balance",
            "time_allocation": 45
        }

def main():
    parser = argparse.ArgumentParser(description="Fleet Orchestrator Quick Dispatcher")
    parser.add_argument("spec", help="Task specification / instructions")
    parser.add_argument("--repo", default="Fleet-Orchestrator", help="Target repository name")
    parser.add_argument("--tier", choices=["efficiency", "balance", "intelligence"], default=None, help="Copilot worker tier")
    args = parser.parse_args()

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    print(f"\n[FLEET DISPATCHER] Enqueuing task: {task_id}")
    print(f"Spec: {args.spec}")

    # 1. Consult local silicon router
    routing = query_local_brain(args.spec)
    auto_tier = args.tier or routing.get("auto_tier", "balance")
    timeout_s = routing.get("time_allocation", 60)
    print(f"[LOCAL BRAIN 1234] Auto-Tier: {auto_tier} | Policy: {routing.get('policy')} | Timeout: {timeout_s}s")

    # 2. Package Antigravity context & customizations
    chat_ctx = harvest_chat_context()
    customizations = harvest_antigravity_customizations()

    task_payload = {
        "id": task_id,
        "kind": "code",
        "spec": args.spec,
        "repo": args.repo,
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "auto_tier": auto_tier,
        "timeout_ceiling_s": timeout_s * 2.2 if isinstance(timeout_s, (int, float)) else 120,
        "routing": routing,
        "antigravity_scope": {
            "chat_context": chat_ctx,
            "antigravity_customizations": customizations
        }
    }

    out_file = TASKS_DIR / f"{task_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(task_payload, f, indent=2)

    print(f"[ENQUEUED] Saved to: {out_file.relative_to(ROOT)}")
    print(f"[STATUS] Ready for headless worker execution across 27-worker pool.\n")

if __name__ == "__main__":
    main()
