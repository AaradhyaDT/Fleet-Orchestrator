#!/usr/bin/env python3
"""tools/adaptive_engine.py
-------------------------
Authoritative CLI Entrypoint for /adaptive-workflow.
Unifies:
1. Tier 0 Zero-AI Fast Paths (<20ms execution)
2. 2D Orthogonal Matrix Triage (Volume x Criticality)
3. 9-Archetype Intent & Skill Routing
4. Live Host RAM Headroom & Banker's Concurrency Guard
5. Dynamic Delegation (in-turn, fleet-copilot, colab, shell)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.adaptive_decision_harness import AdaptiveDecisionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("adaptive_engine")


def format_cli_output(decision: Dict[str, Any]) -> str:
    """Formats decision dictionary into a clear, aesthetic summary."""
    lines = []
    lines.append("=" * 65)
    lines.append("  ADAPTIVE WORKFLOW ORCHESTRATION DECISION")
    lines.append("=" * 65)

    if decision.get("is_fast_path"):
        lines.append(f"  [TIER 0 FAST PATH DETECTED]")
        lines.append(f"  Action      : {decision.get('primary_skill')}")
        lines.append(f"  Shell Cmd   : {decision.get('command')}")
        lines.append(f"  Execution   : Zero-AI deterministic shell (<20ms)")
        lines.append(f"  AI Tokens   : 0 ($0.00)")
        lines.append(f"  RAM Impact  : <10 MB")
        lines.append("=" * 65)
        return "\n".join(lines)

    lines.append(f"  Lifecycle Archetype : {decision.get('archetype')}")
    lines.append(f"  Matrix Cell         : {decision.get('matrix_cell')}  -> Policy: {decision.get('policy')}")
    lines.append(f"  Primary Skill       : {decision.get('primary_skill')}")
    lines.append(f"  Execution Backend   : {decision.get('backend').upper()}")
    lines.append(f"  Copilot Auto-Tier   : {decision.get('auto_tier')}")
    if decision.get("recommended_copilot_model"):
        lines.append(f"  Escalation Model    : {decision.get('recommended_copilot_model')}")

    lines.append("-" * 65)
    lines.append("  HARDWARE & RESOURCE ENVELOPE:")
    lines.append(f"  Available RAM       : {decision.get('available_ram_mb')} MB")
    lines.append(f"  Safe Concurrency    : {decision.get('workers')} workers (Banker's Floor: 2048 MB)")

    ta = decision.get("time_allocation", {})
    lines.append("-" * 65)
    lines.append("  TASK TIME ALLOCATION:")
    lines.append(f"  Est. Duration       : {ta.get('estimated_duration_s', 0)}s")
    lines.append(f"  Timeout Ceiling     : {ta.get('timeout_ceiling_s', 0)}s")
    lines.append(f"  CPM Graph Weight    : {ta.get('cpm_weight', 1.0)}")
    lines.append("=" * 65)
    return "\n".join(lines)


def execute_decision(decision: Dict[str, Any], prompt: str) -> int:
    """Executes the action decided by the pipeline."""
    # 1. Tier 0 Fast Path Execution
    if decision.get("is_fast_path"):
        cmd = decision.get("command")
        print(f"\n[EXEC] Running Tier 0 fast-path command: {cmd}")
        res = subprocess.run(cmd, shell=True, cwd=str(ROOT))
        return res.returncode

    backend = decision.get("backend")

    # 2. Fleet Swarm Delegation
    if backend == "fleet-copilot":
        workers = decision.get("workers", 1)
        auto_tier = decision.get("auto_tier", "balance")
        model = decision.get("recommended_copilot_model")
        print(f"\n[EXEC] Delegating batch to Fleet-Orchestrator ({workers} workers, auto-tier: {auto_tier})...")
        fleet_cmd = [
            sys.executable,
            str(ROOT / "tools" / "copilot_fleet.py"),
            "submit",
            "--spec",
            prompt,
            "--auto-tier",
            auto_tier,
        ]
        if model:
            fleet_cmd.extend(["--model", model])
        res = subprocess.run(fleet_cmd, cwd=str(ROOT))
        return res.returncode

    # 3. Colab Cloud Acceleration
    if backend == "colab":
        print(f"\n[EXEC] Task flagged for Cloud GPU/TPU acceleration. Launching colab CLI check...")
        res = subprocess.run(["colab", "status"], shell=True, cwd=str(ROOT))
        return res.returncode

    # 4. In-Turn Execution
    print(f"\n[EXEC] Task suited for interactive Lead Agent execution with skill '{decision.get('primary_skill')}'.")
    print("Action ready. Follow standard development workflow.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="One-Shot Adaptive-Workflow Orchestration Engine")
    parser.add_argument("prompt", nargs="?", default=None, help="Incoming task specification or query")
    parser.add_argument("--files", nargs="*", default=None, help="Target file paths involved in the task")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--execute", action="store_true", help="Automatically execute the determined route")
    parser.add_argument("--decider", default="deterministic", choices=["deterministic", "qwen-intent-router", "fleet-master-3b"], help="Intent decider backend")
    args = parser.parse_args()

    if not args.prompt:
        parser.print_help()
        return 0

    decision = AdaptiveDecisionEngine.decide(
        prompt=args.prompt,
        files=args.files,
        decider=args.decider,
    )

    if args.json:
        print(json.dumps(decision, indent=2))
    else:
        print(format_cli_output(decision))

    if args.execute:
        return execute_decision(decision, args.prompt)

    return 0


if __name__ == "__main__":
    sys.exit(main())
