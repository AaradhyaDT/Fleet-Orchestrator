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
from tools.fast_intent_router import route_intent

TASKS_DIR = ROOT / "orchestrator-state" / "tasks"

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
    routing = route_intent(args.spec)
    auto_tier = args.tier or routing.get("auto_tier", "balance")
    time_alloc = routing.get("time_allocation")
    if isinstance(time_alloc, dict):
        timeout_ceiling_s = time_alloc.get("timeout_ceiling_s", 120)
        duration_s = time_alloc.get("estimated_duration_s", 45)
    elif isinstance(time_alloc, (int, float)):
        duration_s = time_alloc
        timeout_ceiling_s = min(1200, max(30, int(time_alloc * 2.2)))
    else:
        duration_s = 45
        timeout_ceiling_s = 120

    print(f"[LOCAL BRAIN] Source: {routing.get('source')} | Auto-Tier: {auto_tier} | Policy: {routing.get('policy')} | Est: {duration_s}s (Ceiling: {timeout_ceiling_s}s)")

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
        "timeout_ceiling_s": timeout_ceiling_s,
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
