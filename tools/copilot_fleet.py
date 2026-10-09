#!/usr/bin/env python3
"""
Copilot Fleet Controller CLI:
Discovers pooled accounts from .env.fleet, provides live status auditing,
real-time quota & monthly credit burn rate dashboard, concurrent canary checks,
autonomous task submission, and standalone batch execution independent of Claude Desktop.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import httpx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("copilot_fleet")

from client.adapters.copilot_cli_adapter import CopilotCLIAdapter


def load_env_fleet(env_path: Path | None = None) -> dict[str, str]:
    """Parses .env.fleet file into key-value pairs."""
    path = env_path or (PROJECT_ROOT / ".env.fleet")
    if not path.exists():
        # Fallback to .env.fleet in parent or current working directory
        cwd_fleet = Path(".env.fleet")
        if cwd_fleet.exists():
            path = cwd_fleet
        else:
            return {}

    values = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                values[k] = v
                os.environ[k] = v
    return values


def discover_accounts(env_vars: dict[str, str]) -> list[dict[str, Any]]:
    """Discovers configured accounts from environment variables."""
    accounts = []
    i = 1
    while True:
        token_key = f"COPILOT_ACCOUNT_{i}_TOKEN"
        name_key = f"COPILOT_ACCOUNT_{i}_NAME"
        credits_key = f"COPILOT_ACCOUNT_{i}_MONTHLY_CREDITS"

        token = env_vars.get(token_key, os.getenv(token_key, "")).strip()
        name = env_vars.get(name_key, os.getenv(name_key, f"account_{i}")).strip()
        credits_str = env_vars.get(credits_key, os.getenv(credits_key, "200")).strip()

        if not token and not name_key in env_vars and not name_key in os.environ:
            if i > 2:
                break

        monthly_credits = int(credits_str) if credits_str.isdigit() else 200
        has_token = bool(token and not token.startswith("github_pat_REPLACE"))

        accounts.append({
            "index": i,
            "worker_id": f"copilot-w{i}",
            "name": name,
            "token": token if has_token else "",
            "has_token": has_token,
            "monthly_credits": monthly_credits,
            "state_dir": Path.home() / ".copilot-workers" / f"worker_{i}_{name}",
        })
        i += 1

    return accounts


def initialize_fleet_ledgers(state_dir: Path | str | None = None) -> int:
    """Ensures all discovered accounts have an initialized live-status file in orchestrator-state."""
    from tools.copilot_queue_worker import resolve_state_dir

    resolved_state = resolve_state_dir(str(state_dir) if state_dir else None)
    live_status_dir = resolved_state / "live-status"
    live_status_dir.mkdir(parents=True, exist_ok=True)

    env_vars = load_env_fleet()
    accounts = discover_accounts(env_vars)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    created = 0
    for acc in accounts:
        wid = acc["worker_id"]
        status_file = live_status_dir / f"{wid}.json"
        if not status_file.exists():
            limit = acc["monthly_credits"]
            payload = {
                "account": wid,
                "name": acc["name"],
                "status": "idle" if acc["has_token"] else "offline",
                "current_task_id": None,
                "credits_used": 0.0,
                "credits_remaining": float(limit),
                "monthly_credits": limit,
                "cooldown_until": None,
                "heartbeat_at": now_str,
                "note": "Ready (Initialized)" if acc["has_token"] else "No Token",
            }
            try:
                tmp = status_file.with_suffix(f".tmp.{os.getpid()}")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                os.replace(tmp, status_file)
                created += 1
            except Exception:
                pass
    return created


def get_fleet_quota_metrics(state_dir: Path | str | None = None) -> dict[str, Any]:
    """Computes real-time fleet quota capacity, monthly credit burn rate, and worker states."""
    from tools.copilot_queue_worker import resolve_state_dir

    resolved_state = resolve_state_dir(str(state_dir) if state_dir else None)
    live_status_dir = resolved_state / "live-status"
    tasks_dir = resolved_state / "tasks"
    checkpoints_dir = resolved_state / "checkpoints"

    # Auto-initialize missing worker ledgers if needed
    initialize_fleet_ledgers(resolved_state)

    env_vars = load_env_fleet()
    accounts = discover_accounts(env_vars)

    total_registered = len(accounts)
    ready_workers = 0
    total_monthly_credits = 0
    total_credits_used = 0.0

    worker_metrics = []
    status_counts = {"idle": 0, "busy": 0, "cooldown": 0, "offline": 0}

    now_dt = datetime.now(timezone.utc)

    for acc in accounts:
        wid = acc["worker_id"]
        limit = acc["monthly_credits"]
        total_monthly_credits += limit
        has_token = acc["has_token"]
        if has_token:
            ready_workers += 1

        used = 0.0
        current_task = None
        note = "Ready" if has_token else "No Token"
        heartbeat = None
        cooldown_until = None
        worker_status = "idle" if has_token else "offline"

        status_file = live_status_dir / f"{wid}.json"
        if status_file.exists():
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                raw_used = data.get("credits_used", 0.0)
                used = round(float(raw_used), 2)
                current_task = data.get("current_task_id")
                note = data.get("note", "")
                heartbeat = data.get("heartbeat_at")
                cooldown_until = data.get("cooldown_until")

                if cooldown_until:
                    exp = datetime.fromisoformat(cooldown_until.replace("Z", "+00:00"))
                    if now_dt < exp:
                        worker_status = "cooldown"
                    elif current_task:
                        worker_status = "busy"
                    elif has_token:
                        worker_status = "idle"
                elif current_task:
                    worker_status = "busy"
                elif has_token:
                    worker_status = data.get("status", "idle")
            except Exception:
                pass

        total_credits_used = round(total_credits_used + used, 2)
        status_counts[worker_status] = status_counts.get(worker_status, 0) + 1

        remaining = max(0.0, round(limit - used, 2))
        worker_metrics.append({
            "index": acc["index"],
            "worker_id": wid,
            "name": acc["name"],
            "has_token": has_token,
            "status": worker_status,
            "monthly_credits": limit,
            "credits_used": used,
            "credits_remaining": remaining,
            "current_task_id": current_task,
            "cooldown_until": cooldown_until,
            "heartbeat_at": heartbeat,
            "note": note,
        })

    total_remaining = max(0.0, round(total_monthly_credits - total_credits_used, 2))
    burn_pct = round((total_credits_used / total_monthly_credits * 100.0), 2) if total_monthly_credits > 0 else 0.0

    pending_count = len(list(tasks_dir.glob("task_*.json"))) if tasks_dir.exists() else 0
    checkpoints_count = len(list(checkpoints_dir.glob("task_*.json"))) if checkpoints_dir.exists() else 0

    return {
        "fleet": {
            "total_registered_accounts": total_registered,
            "ready_accounts": ready_workers,
            "total_monthly_credits": total_monthly_credits,
            "total_credits_used": total_credits_used,
            "total_credits_remaining": total_remaining,
            "burn_rate_pct": burn_pct,
            "status_counts": status_counts,
        },
        "tasks": {
            "total_tasks_tracked": pending_count,
            "completed_checkpoints": checkpoints_count,
        },
        "workers": worker_metrics,
    }


def create_task_payload(
    spec: str,
    kind: str = "code",
    task_id: str | None = None,
    parent_id: str | None = None,
    antigravity_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generates a task JSON payload conforming to orchestrator-state/SCHEMA.md."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tid = task_id or f"task_{date_str}_{os.urandom(3).hex()}"
    payload: dict[str, Any] = {
        "id": tid,
        "parent_id": parent_id,
        "kind": kind,
        "spec": spec,
        "status": "pending",
        "owner_account": None,
        "branch_name": None,
        "blocked_reason": None,
        "created_by": "fleet_cli",
        "created_at": now,
        "updated_at": now,
    }
    if antigravity_scope:
        payload["antigravity_scope"] = antigravity_scope
    return payload


async def cmd_status(args: argparse.Namespace) -> None:
    """Displays fleet account topology, token readiness, and monthly credit headroom."""
    env_vars = load_env_fleet()
    accounts = discover_accounts(env_vars)

    print("\n" + "=" * 70)
    print(" GITHUB COPILOT MULTI-ACCOUNT CLI FLEET STATUS")
    print("=" * 70)

    total_credits = 0
    active_workers = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        for acc in accounts:
            status_str = "[NO TOKEN SET]"
            if acc["has_token"]:
                try:
                    resp = await client.get(
                        "https://api.github.com/user",
                        headers={
                            "Authorization": f"token {acc['token']}",
                            "Accept": "application/vnd.github.v3+json",
                            "User-Agent": "Fleet-Orchestrator",
                        },
                    )
                    if resp.status_code == 200:
                        gh_login = resp.json().get("login", "")
                        status_str = f"[VERIFIED: @{gh_login}]"
                    elif resp.status_code == 401:
                        status_str = "[INVALID / EXPIRED TOKEN (401)]"
                    else:
                        status_str = f"[API HTTP {resp.status_code}]"
                except Exception:
                    status_str = "[READY (Offline check)]"

            token_hint = f"{acc['token'][:14]}...{acc['token'][-4:]}" if acc["has_token"] else "(empty / placeholder)"
            print(f"\nWorker {acc['index']}: {acc['worker_id']} ({acc['name']})")
            print(f"  Status:       {status_str}")
            print(f"  Token:        {token_hint}")
            print(f"  Quota Pool:   {acc['monthly_credits']} AI credits/mo")
            print(f"  Session Home: {acc['state_dir']}")

            if acc["has_token"]:
                total_credits += acc["monthly_credits"]
                active_workers += 1

    print("\n" + "-" * 70)
    print(f"Active Ready Workers: {active_workers} / {len(accounts)}")
    print(f"Pooled Monthly Capacity: {total_credits} AI credits")
    print("=" * 70 + "\n")


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Surfaces real-time quota telemetry and credit burn rate dashboard."""
    metrics = get_fleet_quota_metrics(state_dir=args.state_dir)

    if getattr(args, "json", False):
        print(json.dumps(metrics, indent=2))
        return

    f = metrics["fleet"]
    t = metrics["tasks"]

    print("\n" + "=" * 80)
    print(" GITHUB COPILOT MULTI-ACCOUNT CLI FLEET QUOTA & BURN-RATE DASHBOARD")
    print("=" * 80)

    bar_width = 30
    filled = int(round(bar_width * (f["burn_rate_pct"] / 100.0)))
    bar = "=" * filled + "-" * (bar_width - filled)

    print(f" Pooled Monthly Capacity: {f['total_monthly_credits']:,} AI Credits ({f['total_registered_accounts']} accounts)")
    print(f" Consumed Credits:        {f['total_credits_used']:,.2f} credits ({f['burn_rate_pct']:.2f}% burn rate)")
    print(f" Remaining Quota:         {f['total_credits_remaining']:,.2f} credits")
    print(f" Monthly Burn Bar:        [{bar}] {f['burn_rate_pct']:.2f}%")
    print(
        f" Fleet Worker Topology:   {f['ready_accounts']} Ready | {f['status_counts'].get('idle', 0)} Idle | "
        f"{f['status_counts'].get('busy', 0)} Busy | {f['status_counts'].get('cooldown', 0)} Cooldown | "
        f"{f['status_counts'].get('offline', 0)} Offline"
    )
    print(f" State Pipeline:          {t['total_tasks_tracked']} Tasks Tracked | {t['completed_checkpoints']} Checkpoints Complete")
    print("-" * 80)

    print(f" {'WORKER':<12} {'NICKNAME':<16} {'STATUS':<10} {'CREDITS USED / POOL':<24} {'TASK / NOTE'}")
    print(f" {'-'*12} {'-'*16} {'-'*10} {'-'*24} {'-'*18}")

    for w in metrics["workers"]:
        stat = w["status"].upper()
        used_str = f"{w['credits_used']:.2f} / {w['monthly_credits']} ({w['credits_remaining']:.2f} left)"
        note_str = w["current_task_id"] or (w["note"][:22] if w["note"] else "-")
        if w["cooldown_until"]:
            note_str = f"Cooldown until {w['cooldown_until'][11:19]}"
        print(f" {w['worker_id']:<12} {w['name'][:15]:<16} {stat:<10} {used_str:<24} {note_str}")

    print("=" * 80 + "\n")


def cmd_submit(args: argparse.Namespace) -> None:
    """Submits one or more tasks directly to orchestrator-state/tasks/ without Claude Desktop."""
    from tools.copilot_queue_worker import resolve_state_dir

    state_dir = resolve_state_dir(args.state_dir)
    tasks_dir = state_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    specs = []
    if args.file:
        file_path = Path(args.file)
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    for item in content:
                        specs.append(item if isinstance(item, str) else item.get("spec", ""))
                elif isinstance(content, dict) and "tasks" in content:
                    for item in content["tasks"]:
                        specs.append(item if isinstance(item, str) else item.get("spec", ""))
    if args.spec:
        specs.append(args.spec)

    if not specs:
        print("[!] No task spec provided. Use --spec '...' or --file tasks.json")
        return

    antigravity_scope = None
    if not getattr(args, "no_antigravity", False):
        try:
            from client.antigravity_bridge import build_antigravity_scope
            antigravity_scope = build_antigravity_scope(conversation_id=getattr(args, "conversation_id", None))
            if antigravity_scope.get("chat_context", {}).get("conversation_id"):
                cid = antigravity_scope["chat_context"]["conversation_id"]
                print(f"[*] Inherited Antigravity chat context from conversation: {cid}")
        except Exception as e:
            logger.debug(f"Could not harvest Antigravity scope: {e}")

    created_ids = []
    for s in specs:
        task = create_task_payload(
            spec=s,
            kind=args.kind,
            task_id=args.task_id if len(specs) == 1 else None,
            antigravity_scope=antigravity_scope,
        )
        tid = task["id"]
        task_path = tasks_dir / f"{tid}.json"
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2)
        created_ids.append(tid)
        print(f"[+] Enqueued task {tid} -> {task_path.name}")

    print(f"[*] Total {len(created_ids)} task(s) enqueued in {tasks_dir}")


async def cmd_batch(args: argparse.Namespace) -> None:
    """Executes a standalone batch of tasks autonomously and prints completion report."""
    from tools.copilot_queue_worker import CopilotQueueWorker, resolve_state_dir

    state_dir = resolve_state_dir(args.state_dir)
    tasks_dir = state_dir / "tasks"
    checkpoints_dir = state_dir / "checkpoints"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    specs = []
    if args.file:
        file_path = Path(args.file)
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    for item in content:
                        specs.append(item if isinstance(item, str) else item.get("spec", ""))
                elif isinstance(content, dict) and "tasks" in content:
                    for item in content["tasks"]:
                        specs.append(item if isinstance(item, str) else item.get("spec", ""))
    if args.specs:
        specs.extend(args.specs)

    if not specs:
        print("[!] No task specs provided. Use --specs 'Task 1' 'Task 2' or --file tasks.json")
        return

    antigravity_scope = None
    if not getattr(args, "no_antigravity", False):
        try:
            from client.antigravity_bridge import build_antigravity_scope
            antigravity_scope = build_antigravity_scope(conversation_id=getattr(args, "conversation_id", None))
            if antigravity_scope.get("chat_context", {}).get("conversation_id"):
                cid = antigravity_scope["chat_context"]["conversation_id"]
                print(f"[*] Inherited Antigravity chat context from conversation: {cid}")
        except Exception as e:
            logger.debug(f"Could not harvest Antigravity scope: {e}")

    submitted_ids = []
    for spec in specs:
        task = create_task_payload(spec=spec, kind="code", antigravity_scope=antigravity_scope)
        tid = task["id"]
        task_path = tasks_dir / f"{tid}.json"
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2)
        submitted_ids.append(tid)

    print(f"\n[*] Submitted {len(submitted_ids)} tasks into {tasks_dir.name}/:")
    for tid in submitted_ids:
        print(f"    - {tid}")

    # Launch worker runner
    worker = CopilotQueueWorker(
        state_dir=state_dir,
        dry_run=args.dry_run,
        concurrency=args.concurrency,
        poll_interval=1.0,
    )

    print(f"\n[*] Starting autonomous batch execution (Concurrency: {args.concurrency}, Dry-run: {args.dry_run})...")

    async def _monitor_loop():
        while True:
            all_finished = True
            for tid in submitted_ids:
                tp = tasks_dir / f"{tid}.json"
                if tp.exists():
                    try:
                        with open(tp, "r", encoding="utf-8") as f:
                            d = json.load(f)
                        if d.get("status") not in ("done", "blocked"):
                            all_finished = False
                            break
                    except Exception:
                        all_finished = False
                        break
                else:
                    all_finished = False
                    break

            if all_finished:
                worker.stop()
                break
            await asyncio.sleep(0.5)

    await asyncio.gather(
        worker.run(),
        _monitor_loop(),
    )

    # Print summary report
    print("\n" + "=" * 80)
    print(" STANDALONE AUTONOMOUS BATCH EXECUTION REPORT")
    print("=" * 80)
    for tid in submitted_ids:
        cp_path = checkpoints_dir / f"{tid}.json"
        if cp_path.exists():
            with open(cp_path, "r", encoding="utf-8") as f:
                cp = json.load(f)
            print(f"[DONE] {tid}")
            print(f"       Worker:     {cp.get('submitted_by')}")
            print(f"       Branch:     {cp.get('branch_name')}")
            print(f"       Commit SHA: {cp.get('commit_sha')}")
            print(f"       Summary:    {cp.get('summary')}")
        else:
            tp = tasks_dir / f"{tid}.json"
            status = "UNKNOWN"
            reason = ""
            if tp.exists():
                with open(tp, "r", encoding="utf-8") as f:
                    t = json.load(f)
                status = t.get("status", "UNKNOWN")
                reason = t.get("blocked_reason", "")
            print(f"[{status.upper()}] {tid} - {reason}")
    print("=" * 80 + "\n")


async def cmd_canary(args: argparse.Namespace) -> None:
    """Executes concurrent non-interactive verification across all ready accounts."""
    env_vars = load_env_fleet()
    accounts = discover_accounts(env_vars)
    ready = [a for a in accounts if a["has_token"]]

    if not ready:
        print("[!] No ready accounts found with active tokens in .env.fleet.")
        print("    Please paste your Fine-Grained PATs into .env.fleet first.")
        return

    print(f"[*] Running concurrent canary tests across {len(ready)} accounts...")

    async def _test_worker(acc: dict[str, Any]) -> dict[str, Any]:
        adapter = CopilotCLIAdapter(
            worker_id=acc["worker_id"],
            nickname=acc["name"],
            github_token=acc["token"],
            copilot_home=acc["state_dir"],
            timeout=60.0,
            max_ai_credits=30,
        )
        res = await adapter.execute_task(
            task_id=f"canary_{acc['worker_id']}",
            spec="echo 'Fleet Canary Active'",
            stage="canary",
            context={},
        )
        return {"account": acc, "result": res}

    results = await asyncio.gather(*[_test_worker(a) for a in ready], return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            print(f"[-] Exception: {r}")
        else:
            acc = r["account"]
            res = r["result"]
            if res.get("success"):
                print(f"[+] {acc['worker_id']} ({acc['name']}): PASS | Model: {res.get('model_used')} | Tokens: {res.get('tokens_used')}")
            else:
                print(f"[-] {acc['worker_id']} ({acc['name']}): FAIL | Error: {res.get('error')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Copilot Multi-Account Fleet Controller")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show fleet account status and credit headroom")
    subparsers.add_parser("canary", help="Run concurrent canary ping across ready accounts")

    # Dashboard subparser
    dash_parser = subparsers.add_parser("dashboard", help="Show real-time credit burn rate and quota telemetry dashboard")
    dash_parser.add_argument("--json", action="store_true", help="Output dashboard metrics as JSON")
    dash_parser.add_argument("--state-dir", type=str, default=None, help="Path to orchestrator-state directory")

    # Submit task subparser
    submit_parser = subparsers.add_parser("submit", help="Enqueue task(s) into orchestrator-state/tasks/")
    submit_parser.add_argument("--spec", type=str, default=None, help="Task specification description")
    submit_parser.add_argument("--file", type=str, default=None, help="JSON file containing task specifications")
    submit_parser.add_argument("--kind", type=str, default="code", choices=["code", "text"], help="Task kind (default: code)")
    submit_parser.add_argument("--task-id", type=str, default=None, help="Custom task ID")
    submit_parser.add_argument("--state-dir", type=str, default=None, help="Path to orchestrator-state directory")
    submit_parser.add_argument("--conversation-id", type=str, default=None, help="Explicit Antigravity conversation ID")
    submit_parser.add_argument("--no-antigravity", action="store_true", help="Disable Antigravity context inheritance")

    # Autonomous Batch execution subparser
    batch_parser = subparsers.add_parser("batch", help="Submit and execute a batch of tasks autonomously")
    batch_parser.add_argument("--specs", nargs="+", default=[], help="List of task specifications")
    batch_parser.add_argument("--file", type=str, default=None, help="JSON file containing task specifications")
    batch_parser.add_argument("--concurrency", type=int, default=2, help="Number of concurrent workers (default: 2)")
    batch_parser.add_argument("--dry-run", action="store_true", help="Execute in dry-run simulation mode")
    batch_parser.add_argument("--state-dir", type=str, default=None, help="Path to orchestrator-state directory")
    batch_parser.add_argument("--conversation-id", type=str, default=None, help="Explicit Antigravity conversation ID")
    batch_parser.add_argument("--no-antigravity", action="store_true", help="Disable Antigravity context inheritance")

    args = parser.parse_args()
    if args.command == "status":
        asyncio.run(cmd_status(args))
    elif args.command == "canary":
        asyncio.run(cmd_canary(args))
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "submit":
        cmd_submit(args)
    elif args.command == "batch":
        asyncio.run(cmd_batch(args))


if __name__ == "__main__":
    main()
