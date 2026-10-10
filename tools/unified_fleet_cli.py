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
from datetime import datetime, timezone
import json
import os
from pathlib import Path
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

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
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

    tid = task["id"]
    task_path = tasks_dir / f"{tid}.json"
    with open(task_path, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=2)

    print(f"[OK] Dispatched task {tid} ({args.kind}) | Auto-Tier: {task['auto_tier']} | Model: {task.get('model') or 'auto'}")
    print(f"     Spec: {args.spec}")
    print(f"     Queue: {task_path}")


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
    p_submit.add_argument("--no-antigravity", action="store_true", help="Disable Antigravity context harvest")
    p_submit.add_argument("--conversation-id", type=str, default=None, help="Target Antigravity conversation ID")
    p_submit.add_argument("--model", type=str, default=None, help="Explicit Copilot model (e.g. gemini-3.8-flash)")
    p_submit.add_argument("--auto-tier", type=str, default=None, choices=["efficiency", "balance", "intelligence"], help="Copilot auto-tier preference")

    # Tasks
    p_tasks = subparsers.add_parser("tasks", help="List recent tasks in queue")
    p_tasks.add_argument("--limit", type=int, default=15, help="Max tasks to show")

    # Reconcile
    subparsers.add_parser("reconcile", help="Reconcile Copilot and Gemini quota ledgers")

    # Watch
    subparsers.add_parser("watch", help="Live in-terminal status monitor")

    args = parser.parse_args()

    if not args.command or args.command == "status":
        status_data = get_full_status_dict(args.state_dir)
        if getattr(args, "json", False):
            print(json.dumps(status_data, indent=2))
        else:
            render_ascii_status(status_data)
    elif args.command == "submit":
        cmd_submit(args)
    elif args.command == "tasks":
        cmd_tasks(args)
    elif args.command == "reconcile":
        count = initialize_fleet_ledgers(args.state_dir)
        print(f"[OK] Reconciled {count} worker ledgers successfully.")
    elif args.command == "watch":
        cmd_watch(args)


if __name__ == "__main__":
    main()
