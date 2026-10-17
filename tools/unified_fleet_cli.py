#!/usr/bin/env python3
"""
Unified Zero-Distraction Fleet CLI.
Provides high-density, sub-50ms execution from the integrated terminal without opening external GUIs.
Commands:
  fleet status              - Instant ASCII/JSON telemetry of Gemini & Copilot pools
  fleet submit --spec "..." - Non-blocking task dispatch to swarm queue
  fleet tasks               - List active queue, running tasks, and completed checkpoints
  fleet reconcile           - Synchronize credit ledgers with session logs
  fleet watch               - Live in-terminal status monitor (no popups)
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from client.adapters.gemini_fleet_rotator import get_gemini_rotator
from tools.copilot_fleet import (
    discover_accounts,
    get_fleet_quota_metrics,
    initialize_fleet_ledgers,
    load_env_fleet,
    create_task_payload,
)
from tools.copilot_queue_worker import resolve_state_dir

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass


def get_full_status_dict(state_dir: Path | None = None) -> dict[str, Any]:
    """Assembles unified status dictionary across Gemini and Copilot fleets."""
    resolved_state = resolve_state_dir(str(state_dir) if state_dir else None)
    tasks_dir = resolved_state / "tasks"

    # 1. Gemini Fleet Status
    rotator = get_gemini_rotator()
    gemini_data = rotator.get_status()

    # 2. Copilot Fleet Status
    copilot_data = {}
    try:
        copilot_data = get_fleet_quota_metrics(resolved_state)
    except Exception as e:
        copilot_data = {"error": str(e)}

    # 3. Tasks overview
    task_counts = {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0, "total": 0}
    recent_tasks = []
    if tasks_dir.exists():
        for tf in sorted(tasks_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            task_counts["total"] += 1
            try:
                with open(tf, "r", encoding="utf-8", errors="replace") as f:
                    t = json.load(f)
                st = t.get("status", "pending")
                task_counts[st] = task_counts.get(st, 0) + 1
                if len(recent_tasks) < 5:
                    recent_tasks.append({
                        "id": t.get("id", tf.stem),
                        "status": st,
                        "kind": t.get("kind", "code"),
                        "assigned_to": t.get("assigned_to"),
                        "spec": (t.get("spec", "")[:60] + "...") if len(t.get("spec", "")) > 60 else t.get("spec", ""),
                    })
            except Exception:
                pass

    # 4. Tri-Hardware Silicon Status
    hw_data = {}
    try:
        from tools.npu_engine import TriHardwareEngine
        hw_data = TriHardwareEngine.get_hardware_status()
    except Exception as e:
        hw_data = {"error": str(e)}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gemini_fleet": gemini_data,
        "copilot_fleet": copilot_data,
        "tri_hardware": hw_data,
        "tasks": {
            "counts": task_counts,
            "recent": recent_tasks,
        },
    }


def render_ascii_status(status_data: dict[str, Any]) -> None:
    """Renders a clean, high-density ASCII table to terminal."""
    g = status_data.get("gemini_fleet", {})
    c = status_data.get("copilot_fleet", {})
    t = status_data.get("tasks", {}).get("counts", {})

    print("\n" + "=" * 78)
    print(" FLEET-ORCHESTRATOR SWARM TELEMETRY (IN-TERMINAL MONITOR)")
    print("=" * 78)

    # Gemini Section
    g_keys = g.get("total_keys", 0)
    g_healthy = g.get("healthy_keys", 0)
    g_rpm = g.get("pooled_rpm_capacity", 0)
    g_rpd = g.get("pooled_rpd_capacity", 0)
    g_calls = g.get("total_calls_served", 0)
    g_tokens = g.get("total_tokens_served", 0)

    print(f"[*] GEMINI API FLEET:  {g_healthy}/{g_keys} Healthy Keys | Pooled: {g_rpm} RPM, {g_rpd} RPD")
    print(f"                       Served: {g_calls:,} requests | {g_tokens:,} tokens")

    # Copilot Section
    fleet_meta = c.get("fleet", {})
    c_ready = fleet_meta.get("ready_accounts", 0)
    c_total = fleet_meta.get("total_registered_accounts", 0)
    c_used = fleet_meta.get("total_credits_used", 0)
    c_monthly = fleet_meta.get("total_monthly_credits", 0)
    burn_pct = fleet_meta.get("burn_rate_pct", 0.0)

    print(f"[*] COPILOT SWARM:     {c_ready}/{c_total} Workers Online | Burn: {c_used:,.1f}/{c_monthly:,} credits ({burn_pct:.1f}%)")

    # Meteor Lake Hardware Section
    hw = status_data.get("tri_hardware", {})
    if hw and "devices_detected" in hw:
        devs = ", ".join(hw.get("devices_detected", []))
        npu_ok = "Online (11 TOPS, ~2W)" if hw.get("intel_ai_boost_npu", {}).get("available") else "Offline"
        tgt = hw.get("runtimes", {}).get("active_priority_target", "CPU")
        print(f"[*] METEOR LAKE SILICON: Devices: [{devs}] | Target: {tgt} | NPU: {npu_ok}")

    # Task Queue Section
    print(f"[*] TASK QUEUE:        Pending: {t.get('pending', 0)} | Running: {t.get('in_progress', 0)} | Done: {t.get('done', 0)} | Total: {t.get('total', 0)}")
    print("-" * 78)

    recent = status_data.get("tasks", {}).get("recent", [])
    if recent:
        print(" RECENT ACTIVE TASKS:")
        for r in recent:
            st_badge = f"[{r['status'].upper()}]".ljust(14)
            assigned = f"({r['assigned_to'] or 'unassigned'})".ljust(18)
            print(f"  - {st_badge} {assigned} {r['id'][:20]} | {r['spec']}")
    else:
        print(" No active tasks in queue. Dispatch using: fleet submit --spec \"...\"")
    print("=" * 78 + "\n")


def cmd_submit(args: argparse.Namespace) -> None:
    """Submits task payload into SQLite / filesystem queue."""
    state_dir = resolve_state_dir(args.state_dir)
    tasks_dir = state_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    antigravity_scope = None
    if not getattr(args, "no_antigravity", False):
        try:
            from client.antigravity_bridge import build_antigravity_scope
            antigravity_scope = build_antigravity_scope(conversation_id=getattr(args, "conversation_id", None))
        except Exception:
            pass

    task = create_task_payload(spec=args.spec, kind=args.kind, antigravity_scope=antigravity_scope)

    # Dynamic routing for auto-tier and time allocation if not explicitly specified
    auto_tier = getattr(args, "auto_tier", None)
    model = getattr(args, "model", None)
    try:
        from tools.fast_intent_router import route_intent
        r_info = route_intent(args.spec)
        if not auto_tier:
            auto_tier = r_info.get("auto_tier", "balance")
        if not model:
            model = r_info.get("recommended_copilot_model")
        task["time_allocation"] = r_info.get("time_allocation", {})
        task["execution_route"] = r_info.get("time_allocation", {}).get("execution_route")
    except Exception:
        pass

    task["auto_tier"] = auto_tier or "balance"
    task["model"] = model
    task["recommended_model"] = model
    if getattr(args, "kind", None):
        task["stage"] = args.kind

    # Tier-aware timeout floor escalation (mirrors cmd_run_task)
    _TIER_FLOOR_S = {"efficiency": 120, "balance": 300, "intelligence": 600}
    effective_tier = task["auto_tier"]
    ta = task.get("time_allocation", {})
    current_ceiling = ta.get("timeout_ceiling_s", 0)
    floor = _TIER_FLOOR_S.get(effective_tier, 120)
    if current_ceiling < floor:
        ta["timeout_ceiling_s"] = floor
        task["time_allocation"] = ta

    if getattr(args, "target_repo", None):
        task["target_repo"] = str(Path(args.target_repo).resolve())

    tid = task["id"]
    task_path = tasks_dir / f"{tid}.json"
    with open(task_path, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=2)

    print(f"[OK] Dispatched task {tid} ({args.kind}) | Auto-Tier: {task['auto_tier']} | Model: {task.get('model') or 'auto'}")
    print(f"     Spec: {args.spec}")
    if task.get("target_repo"):
        print(f"     Target Repo: {task['target_repo']}")
    print(f"     Queue: {task_path}")


def cmd_run_task(args: argparse.Namespace) -> None:
    """Atomic task submit & immediate unbuffered worker execution for Antigravity 2.0 background tasks."""
    state_dir = resolve_state_dir(args.state_dir)
    tasks_dir = state_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    # Fast synchronous pre-flight canary (<200ms)
    if not args.dry_run:
        from client.adapters.copilot_cli_adapter import CopilotCLIAdapter
        copilot_bin = CopilotCLIAdapter._resolve_copilot_binary()
        if not shutil.which(copilot_bin) and not Path(copilot_bin).exists():
            print(f"[!] Pre-flight Error: copilot binary not found ({copilot_bin}). Install GitHub Copilot CLI or use --dry-run.", file=sys.stderr)
            sys.exit(1)

        env_vars = load_env_fleet()
        accounts = discover_accounts(env_vars)
        ready = [a for a in accounts if a.get("has_token")]
        if not ready:
            print("[!] Pre-flight Error: No ready accounts with COPILOT_GITHUB_TOKEN found in .env.fleet.copilot. Run: python tools/copilot_fleet.py canary", file=sys.stderr)
            sys.exit(1)

    antigravity_scope = None
    if not getattr(args, "no_antigravity", False):
        try:
            from client.antigravity_bridge import build_antigravity_scope
            repo_root_target = Path(args.target_repo).resolve() if getattr(args, "target_repo", None) else None
            antigravity_scope = build_antigravity_scope(
                conversation_id=getattr(args, "conversation_id", None),
                repo_root=repo_root_target,
            )
        except Exception:
            pass

    task = create_task_payload(spec=args.spec, kind=args.kind, antigravity_scope=antigravity_scope)

    if getattr(args, "target_repo", None):
        task["target_repo"] = str(Path(args.target_repo).resolve())

    auto_tier = getattr(args, "auto_tier", None)
    model = getattr(args, "model", None)
    try:
        from tools.fast_intent_router import route_intent
        r_info = route_intent(args.spec)
        if not auto_tier:
            auto_tier = r_info.get("auto_tier", "balance")
        if not model:
            model = r_info.get("recommended_copilot_model")
        task["time_allocation"] = r_info.get("time_allocation", {})
        task["execution_route"] = r_info.get("time_allocation", {}).get("execution_route")
    except Exception:
        pass

    task["auto_tier"] = auto_tier or "balance"
    task["model"] = model
    task["recommended_model"] = model

    # Tier-aware timeout floor escalation: when the user explicitly overrides
    # auto-tier via CLI, ensure the SLM's computed ceiling is escalated to match.
    _TIER_FLOOR_S = {"efficiency": 120, "balance": 300, "intelligence": 600}
    effective_tier = task["auto_tier"]
    ta = task.get("time_allocation", {})
    current_ceiling = ta.get("timeout_ceiling_s", 0)
    floor = _TIER_FLOOR_S.get(effective_tier, 120)
    if current_ceiling < floor:
        ta["timeout_ceiling_s"] = floor
        task["time_allocation"] = ta

    tid = task["id"]
    task_path = tasks_dir / f"{tid}.json"
    with open(task_path, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=2)

    print(f"[DISPATCH] Task {tid} ({args.kind}) enqueued. Auto-Tier: {task['auto_tier']} | Model: {task.get('model') or 'auto'}", flush=True)
    if task.get("target_repo"):
        print(f"           Target Repo: {task['target_repo']}", flush=True)

    # Launch queue worker for targeted task
    from tools.copilot_queue_worker import CopilotQueueWorker
    worker = CopilotQueueWorker(
        state_dir=state_dir,
        dry_run=args.dry_run,
        repo_root=task.get("target_repo"),
    )
    timeout_sec = getattr(args, "timeout", 300.0)
    asyncio.run(worker.run(once=True, target_task_id=tid, timeout=timeout_sec))


def cmd_tasks(args: argparse.Namespace) -> None:
    """Lists queue tasks."""
    state_dir = resolve_state_dir(args.state_dir)
    tasks_dir = state_dir / "tasks"
    if not tasks_dir.exists():
        print("No tasks found in queue.")
        return

    print("\n" + "=" * 80)
    print(f"{'STATUS':<12} {'KIND':<8} {'ASSIGNED TO':<18} {'TASK ID':<22} {'SPEC':<20}")
    print("=" * 80)
    count = 0
    for tf in sorted(tasks_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        count += 1
        if count > args.limit:
            break
        try:
            with open(tf, "r", encoding="utf-8") as f:
                d = json.load(f)
            st = d.get("status", "pending")
            kind = d.get("kind", "code")
            assigned = str(d.get("assigned_to") or "-")
            spec = (d.get("spec", "")[:30] + "...") if len(d.get("spec", "")) > 30 else d.get("spec", "")
            print(f"{st.upper():<12} {kind:<8} {assigned:<18} {tf.stem:<22} {spec}")
        except Exception:
            pass
    print("=" * 80 + "\n")


def cmd_daemon(args: argparse.Namespace) -> None:
    """Runs standing background queue worker daemon."""
    state_dir = resolve_state_dir(args.state_dir)
    from tools.copilot_queue_worker import CopilotQueueWorker

    concurrency = getattr(args, "concurrency", 1)
    dry_run = getattr(args, "dry_run", False)
    exit_when_empty = getattr(args, "exit_when_empty", False)
    idle_timeout = getattr(args, "idle_timeout", None)
    worker = CopilotQueueWorker(
        state_dir=state_dir,
        concurrency=concurrency,
        dry_run=dry_run,
    )
    print(f"[DAEMON] Starting Copilot Queue Worker (Concurrency: {concurrency}, Dry-run: {dry_run}, Drain: {exit_when_empty}, IdleTimeout: {idle_timeout}s)...", flush=True)
    asyncio.run(worker.run(exit_when_empty=exit_when_empty, idle_timeout=idle_timeout))


def cmd_watch(args: argparse.Namespace) -> None:
    """Live updating terminal HUD without external windows."""
    print("Starting Fleet Swarm live monitor (Press Ctrl+C to stop)...")
    try:
        while True:
            # Clear terminal screen
            os.system("cls" if os.name == "nt" else "clear")
            status_data = get_full_status_dict(args.state_dir)
            render_ascii_status(status_data)
            print("Refreshing every 2 seconds... (Ctrl+C to exit)")
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


def main():
    parser = argparse.ArgumentParser(description="Fleet-Orchestrator Zero-Distraction Terminal CLI")
    parser.add_argument("--state-dir", type=str, default=None, help="Path to orchestrator state directory")
    subparsers = parser.add_subparsers(dest="command")

    # Status
    p_status = subparsers.add_parser("status", help="Show fleet status and telemetry")
    p_status.add_argument("--json", action="store_true", help="Output raw JSON")

    # Submit
    p_submit = subparsers.add_parser("submit", help="Submit task to swarm queue")
    p_submit.add_argument("--spec", type=str, required=True, help="Task specification")
    p_submit.add_argument("--kind", type=str, default="code", choices=["code", "text", "qa", "research"], help="Task kind")
    p_submit.add_argument("--target-repo", type=str, default=None, help="Root path of target repository for worktree")
    p_submit.add_argument("--no-antigravity", action="store_true", help="Disable Antigravity context harvest")
    p_submit.add_argument("--conversation-id", type=str, default=None, help="Target Antigravity conversation ID")
    p_submit.add_argument("--model", type=str, default=None, help="Explicit Copilot model (e.g. gemini-3.8-flash)")
    p_submit.add_argument("--auto-tier", type=str, default=None, choices=["efficiency", "balance", "intelligence"], help="Copilot auto-tier preference")

    # Run-Task (Atomic Dispatch & Immediate Worker Execution)
    p_run = subparsers.add_parser("run-task", help="Atomic task submit & immediate unbuffered background worker execution")
    p_run.add_argument("--spec", type=str, required=True, help="Task specification")
    p_run.add_argument("--kind", type=str, default="code", choices=["code", "text", "qa", "research"], help="Task kind")
    p_run.add_argument("--target-repo", type=str, default=None, help="Root path of target repository for worktree")
    p_run.add_argument("--no-antigravity", action="store_true", help="Disable Antigravity context harvest")
    p_run.add_argument("--conversation-id", type=str, default=None, help="Target Antigravity conversation ID")
    p_run.add_argument("--model", type=str, default=None, help="Explicit Copilot model (e.g. gemini-3.8-flash)")
    p_run.add_argument("--auto-tier", type=str, default=None, choices=["efficiency", "balance", "intelligence"], help="Copilot auto-tier preference")
    p_run.add_argument("--dry-run", action="store_true", help="Simulate execution without spawning copilot.exe")
    p_run.add_argument("--timeout", type=float, default=300.0, help="Timeout in seconds for execution")

    # Tasks
    p_tasks = subparsers.add_parser("tasks", help="List recent tasks in queue")
    p_tasks.add_argument("--limit", type=int, default=15, help="Max tasks to show")

    # Reconcile
    subparsers.add_parser("reconcile", help="Reconcile Copilot and Gemini quota ledgers")

    # Watch
    subparsers.add_parser("watch", help="Live in-terminal status monitor")

    # Daemon (Continuous background queue worker)
    p_daemon = subparsers.add_parser("daemon", help="Run background queue worker")
    p_daemon.add_argument("--concurrency", type=int, default=1, help="Number of concurrent worker tasks (default: 1)")
    p_daemon.add_argument("--dry-run", action="store_true", help="Simulate execution without spawning copilot.exe")
    p_daemon.add_argument(
        "--drain",
        "--exit-when-empty",
        dest="exit_when_empty",
        action="store_true",
        help="Process all queued tasks and exit once the queue is empty",
    )
    p_daemon.add_argument(
        "--idle-timeout",
        type=float,
        default=None,
        help="Exit after being idle with empty queue for specified seconds",
    )

    # Submit-DAG
    p_dag = subparsers.add_parser("submit-dag", help="Submit topological DAG task bundle using CPM scheduler")
    p_dag.add_argument("file", type=str, help="Path to JSON file containing DAG tasks")
    p_dag.add_argument("--dry-run", action="store_true", help="Simulate submission without writing task files")

    args = parser.parse_args()

    if not args.command or args.command == "status":
        status_data = get_full_status_dict(args.state_dir)
        if getattr(args, "json", False):
            print(json.dumps(status_data, indent=2))
        else:
            render_ascii_status(status_data)
    elif args.command == "submit":
        cmd_submit(args)
    elif args.command == "run-task":
        cmd_run_task(args)
    elif args.command == "tasks":
        cmd_tasks(args)
    elif args.command == "reconcile":
        count = initialize_fleet_ledgers(args.state_dir)
        print(f"[OK] Reconciled {count} worker ledgers successfully.")
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "daemon":
        cmd_daemon(args)
    elif args.command == "submit-dag":
        from tools.dag_planner import submit_dag_bundle
        res = submit_dag_bundle(args.file, state_dir=Path(args.state_dir) if args.state_dir else None, dry_run=args.dry_run)
        print("===========================================================================")
        print(f"  DAG TASK BUNDLE SUBMITTED: {res['bundle_id']}")
        print("===========================================================================")
        print(f"  Enqueued Tasks   : {res['enqueued_count']}")
        print(f"  Project Duration : {res['project_duration']:.2f} time units")
        print(f"  Critical Path    : {' -> '.join(res['critical_path'])}")
        print(f"  Parallel Slack   : {', '.join(res['parallel_slack']) if res['parallel_slack'] else 'None'}")
        print(f"  Dry-Run Mode     : {res['dry_run']}")
        print("===========================================================================")


if __name__ == "__main__":
    main()
