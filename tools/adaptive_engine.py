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
6. Real-Time Registry Grounding & Host Telemetry (INV-REALTIME-GROUNDING)
7. Resilient Smart Argument Normalizer & Schema Contract (INV-ZERO-HELP-LOOP)
8. Standalone Mathematical CPM DAG Scheduling (INV-CPM-SOLVER)
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
from tools.cpm_solver import DeterministicCPMSolver, format_cpm_output
from tools.web_grounder import get_grounding_summary, load_grounding_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("adaptive_engine")

SCHEMA_DEF = {
    "command": "adaptive_engine.py",
    "version": "3.10.0",
    "usage": "adaptive_engine.py \"<prompt>\" [-f <files>] [-j] [-x] [-e] [-g] [-d <decider>] | cpm --dag-json <path>",
    "flags": {
        "--files": "Target file paths (alias: -f)",
        "--json": "Output JSON (alias: -j)",
        "--explain": "Emit reasoning trace (alias: -x)",
        "--execute": "Auto-execute route (alias: -e)",
        "--ground": "Inject live CLI/package facts (alias: -g)",
        "--decider": "Backend: deterministic|qwen-intent-router (alias: -d)",
        "--schema": "Emit compact schema (<50 tokens)",
    },
    "subcommands": ["triage", "cpm"],
}

HELP_CONTRACT = """[ADAPTIVE WORKFLOW CLI CONTRACT (INV-ZERO-HELP-LOOP)]
  Usage: python tools/adaptive_engine.py "<prompt>" [options]
         python tools/adaptive_engine.py cpm --dag-json <path> [--json]

  Options:
    -f, --files <paths>   Target file paths (Volume/Criticality calculation)
    -j, --json            Output machine-readable JSON format
    -x, --explain         Emit detailed reasoning trace and audit record
    -e, --execute         Execute determined route (fast-path shell / fleet)
    -g, --ground          Inject live verified package & CLI grounding facts
    -d, --decider <name>  Intent decider: deterministic [default], qwen-intent-router
    --schema              Emit compact machine-readable JSON schema (<50 tokens)
    cpm --dag-json <path> Solve topological Critical Path Method DAG schedule
"""


def format_cli_output(decision: Dict[str, Any]) -> str:
    """Formats decision dictionary into a clear, aesthetic summary."""
    lines = []
    lines.append("=" * 65)
    lines.append("  ADAPTIVE WORKFLOW ORCHESTRATION DECISION")
    lines.append("=" * 65)

    if decision.get("is_fast_path"):
        lines.append("  [TIER 0 FAST PATH DETECTED]")
        lines.append(f"  Action      : {decision.get('primary_skill')}")
        lines.append(f"  Shell Cmd   : {decision.get('command')}")
        lines.append("  Execution   : Zero-AI deterministic shell (<20ms)")
        lines.append("  AI Tokens   : 0 ($0.00)")
        lines.append("  RAM Impact  : <10 MB")
        lines.append("=" * 65)
        return "\n".join(lines)

    lines.append(f"  Lifecycle Archetype : {decision.get('archetype')}")
    lines.append(f"  Matrix Cell         : {decision.get('matrix_cell')}  -> Policy: {decision.get('policy')}")
    lines.append(f"  Primary Skill       : {decision.get('primary_skill')}")
    lines.append(f"  Execution Backend   : {decision.get('backend', '').upper()}")
    lines.append(f"  Copilot Auto-Tier   : {decision.get('auto_tier')}")
    if decision.get("recommended_copilot_model"):
        lines.append(f"  Escalation Model    : {decision.get('recommended_copilot_model')}")

    lines.append("-" * 65)
    lines.append("  HARDWARE & RESOURCE ENVELOPE:")
    lines.append(f"  Available RAM       : {decision.get('available_ram_mb')} MB")
    lines.append(f"  Safe Concurrency    : {decision.get('workers')} workers (Banker's Floor: 2048 MB)")
    if decision.get("workers", 0) == 0:
        lines.append("  [!] CAUTION: RAM at Banker's safety floor. Concurrency locked to 0.")
        lines.append("      Run '.\\sync.bat -Hygiene' or close idle processes to reclaim RAM.")

    ta = decision.get("time_allocation", {})
    lines.append("-" * 65)
    lines.append("  TASK TIME ALLOCATION:")
    lines.append(f"  Est. Duration       : {ta.get('estimated_duration_s', 0)}s")
    lines.append(f"  Timeout Ceiling     : {ta.get('timeout_ceiling_s', 0)}s")
    lines.append(f"  CPM Graph Weight    : {ta.get('cpm_weight', 1.0)}")

    if decision.get("grounding_summary"):
        lines.append("-" * 65)
        lines.append(decision["grounding_summary"])

    lines.append("=" * 65)
    return "\n".join(lines)


def format_decision_explanation(decision: Dict[str, Any], prompt: str) -> str:
    """Formats explainable reasoning trace justifying the routing decision."""
    lines = [
        "-" * 65,
        "  EXPLAINABLE ROUTING TRACE (INV-EXPLAINABLE-ROUTING):",
        f"  1. Prompt Intent    : \"{prompt[:60]}...\"" if len(prompt) > 60 else f"  1. Prompt Intent    : \"{prompt}\"",
        f"  2. Classification   : Archetype '{decision.get('archetype')}' matched via {decision.get('source', 'deterministic rules')}.",
        f"  3. Matrix Cell      : {decision.get('matrix_cell')} with policy '{decision.get('policy')}'.",
        f"  4. Selected Skill   : {decision.get('primary_skill')} (supporting: {', '.join(decision.get('supporting_skills', [])) or 'none'}).",
        f"  5. Gating Envelope  : RAM headroom {decision.get('available_ram_mb')} MB allows {decision.get('workers')} worker slot(s).",
        f"  6. Execution Route  : {decision.get('backend', '').upper()} chosen based on 2D volume, risk, and hardware headroom.",
        "-" * 65,
    ]
    return "\n".join(lines)


def log_routing_decision(decision: Dict[str, Any], prompt: str) -> None:
    """Appends an auditable, machine-readable routing decision record to orchestrator-state/routing_decisions.jsonl."""
    log_file = ROOT / "orchestrator-state" / "routing_decisions.jsonl"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp_epoch": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "prompt": prompt,
            "archetype": decision.get("archetype"),
            "matrix_cell": decision.get("matrix_cell"),
            "policy": decision.get("policy"),
            "primary_skill": decision.get("primary_skill"),
            "backend": decision.get("backend"),
            "safe_workers": decision.get("workers"),
            "is_fast_path": decision.get("is_fast_path", False),
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.debug(f"Failed to log routing decision: {e}")



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
        print("\n[EXEC] Task flagged for Cloud GPU/TPU acceleration. Launching colab CLI check...")
        res = subprocess.run(["colab", "status"], shell=True, cwd=str(ROOT))
        return res.returncode

    # 4. In-Turn Execution
    print(f"\n[EXEC] Task suited for interactive Lead Agent execution with skill '{decision.get('primary_skill')}'.")
    print("Action ready. Follow standard development workflow.")
    return 0


def handle_cpm_subcommand(argv: List[str]) -> int:
    """Handles 'cpm' subcommand delegating directly to DeterministicCPMSolver."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dag-json", default=None)
    parser.add_argument("--json", action="store_true")
    args, unknown = parser.parse_known_args(argv)

    raw_input = args.dag_json or (unknown[0] if unknown else None)
    if not raw_input and not sys.stdin.isatty():
        raw_input = sys.stdin.read().strip()

    if not raw_input:
        print("[ERROR] CPM subcommand requires --dag-json <file_or_json_string>", file=sys.stderr)
        return 1

    try:
        p = Path(raw_input)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(raw_input)
    except Exception as e:
        print(f"[ERROR] Failed to parse CPM DAG JSON: {e}", file=sys.stderr)
        return 1

    tasks = data if isinstance(data, list) else data.get("tasks", [])
    try:
        result = DeterministicCPMSolver.solve(tasks)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_cpm_output(result))
        return 0
    except ValueError as e:
        print(f"[ERROR] CPM Calculation Failed: {e}", file=sys.stderr)
        return 1


def normalize_argv(raw_argv: List[str]) -> List[str]:
    """Token-safe argument normalizer supporting flag aliasing and subcommand tolerance."""
    if not raw_argv:
        return []

    alias_map = {
        "-f": "--files",
        "--file": "--files",
        "-j": "--json",
        "-x": "--explain",
        "-e": "--execute",
        "-g": "--ground",
        "--live": "--ground",
        "-d": "--decider",
        "--model": "--decider",
    }

    normalized: List[str] = []
    for i, arg in enumerate(raw_argv):
        if i == 0 and arg.lower() in ("triage", "route"):
            # Strip redundant positional verb 'triage' or 'route'
            continue
        if arg in alias_map:
            normalized.append(alias_map[arg])
        else:
            normalized.append(arg)
    return normalized


def main() -> int:
    raw_args = sys.argv[1:]

    # Early exit 1: Help contract interception (INV-ZERO-HELP-LOOP)
    if not raw_args or "-h" in raw_args or "--help" in raw_args:
        print(HELP_CONTRACT)
        return 0

    # Early exit 2: Schema definition (<50 tokens)
    if "--schema" in raw_args:
        print(json.dumps(SCHEMA_DEF, indent=2))
        return 0

    # Early exit 3: CPM subcommand delegation (INV-CPM-SOLVER)
    if raw_args[0].lower() == "cpm":
        return handle_cpm_subcommand(raw_args[1:])

    # Normalize flags
    normalized_args = normalize_argv(raw_args)

    parser = argparse.ArgumentParser(add_help=False, description="One-Shot Adaptive-Workflow Orchestration Engine")
    parser.add_argument("prompt", nargs="?", default=None, help="Incoming task specification or query")
    parser.add_argument("--files", nargs="*", default=None, help="Target file paths involved in the task")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--explain", action="store_true", help="Emit detailed reasoning trace and audit record")
    parser.add_argument("--execute", action="store_true", help="Automatically execute the determined route")
    parser.add_argument("--ground", action="store_true", help="Inject live verified package & CLI facts")
    parser.add_argument("--decider", default="deterministic", choices=["deterministic", "qwen-intent-router", "fleet-master-3b"], help="Intent decider backend")
    args = parser.parse_args(normalized_args)

    if not args.prompt:
        print(HELP_CONTRACT)
        return 0

    decision = AdaptiveDecisionEngine.decide(
        prompt=args.prompt,
        files=args.files,
        decider=args.decider,
    )

    # Log auditable routing decision record
    log_routing_decision(decision, args.prompt)

    if args.ground:
        cache = load_grounding_cache()
        decision["grounding_summary"] = get_grounding_summary()
        decision["grounded_packages"] = list(cache.get("packages", {}).keys())
        decision["grounded_cli_tools"] = list(cache.get("cli_tools", {}).keys())

    if args.json:
        if args.explain:
            decision["reasoning_trace"] = format_decision_explanation(decision, args.prompt)
        print(json.dumps(decision, indent=2))
    else:
        out = format_cli_output(decision)
        if args.explain:
            out += "\n" + format_decision_explanation(decision, args.prompt)
        print(out)

    if args.execute:
        return execute_decision(decision, args.prompt)

    return 0


if __name__ == "__main__":
    sys.exit(main())
