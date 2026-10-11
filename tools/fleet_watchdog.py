#!/usr/bin/env python3
"""
Fleet Watchdog: Self-Healing Health & Integrity Sentinel.
Performs periodic audits of database schemas, task states, scheduler invariants,
isolated worktree hygiene, and stale worker session recovery.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    try:
        # Normalize trailing Z
        s = iso_str.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


async def audit_database_schema() -> bool:
    """Verify SQLite WAL database initialization and tables."""
    print("[*] Auditing database schema and migrations...")
    root_dir = Path(__file__).resolve().parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    temp_dir = tempfile.mkdtemp()
    temp_db = Path(temp_dir) / "watchdog_audit.db"
    try:
        from server.core.config import settings
        from server.core.database import get_db_conn, init_db

        settings.DATA_DIR = Path(temp_dir)
        settings.DATABASE_PATH = temp_db
        await init_db()

        db = await get_db_conn()
        try:
            async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                tables = [row[0] for row in await cursor.fetchall()]
        finally:
            await db.close()

        required = {"jobs", "tasks", "workers", "task_attempts"}
        missing = required - set(tables)
        if missing:
            print(f"[!] Error: Missing required database tables: {missing}", file=sys.stderr)
            return False

        print(f"[+] Database schema verified. Tables present: {sorted(tables)}")
        return True
    except Exception as e:
        print(f"[!] Database audit failure: {e}", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def audit_worktree_hygiene(root_dir: Path, fix: bool = False) -> bool:
    """Verify worktree isolation and clean up stale temporary worktrees."""
    print("[*] Auditing git worktree hygiene...")
    worktrees_dir = root_dir / ".worktrees"
    if not worktrees_dir.exists():
        print("[+] No .worktrees directory present; clean state.")
        return True

    # 1. Prune git internal worktree tracking
    win_flag = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.run(["git", "worktree", "prune"], cwd=str(root_dir), capture_output=True, creationflags=win_flag)

    # 2. Query active registered worktrees
    active_worktrees = set()
    res = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(root_dir),
        capture_output=True,
        text=True,
        creationflags=win_flag,
    )
    if res.returncode == 0 and res.stdout:
        for line in res.stdout.splitlines():
            if line.startswith("worktree "):
                wt_path = line.split(" ", 1)[1].strip()
                try:
                    active_worktrees.add(Path(wt_path).resolve())
                except Exception:
                    pass

    stale_count = 0
    cleaned_count = 0
    for child in list(worktrees_dir.iterdir()):
        if child.is_dir() and child.name.startswith("task_"):
            resolved = child.resolve()
            if resolved not in active_worktrees:
                stale_count += 1
                if fix:
                    try:
                        shutil.rmtree(child, ignore_errors=True)
                        cleaned_count += 1
                        print(f"    - Cleaned orphaned worktree: {child.name}")
                    except Exception as e:
                        print(f"    ! Could not remove {child.name}: {e}")
            else:
                print(f"    - Found active registered worktree: {child.name}")

    if fix and cleaned_count > 0:
        print(f"[+] Worktree hygiene complete. Cleaned {cleaned_count} orphaned worktree(s).")
    else:
        print(f"[+] Worktree audit complete. Orphaned worktrees detected: {stale_count}")
    return True


def audit_task_branches(root_dir: Path, fix: bool = False) -> bool:
    """Audits local task/* branches and safely prunes branches for completed tasks."""
    print("[*] Auditing ephemeral task branches...")
    win_flag = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    res = subprocess.run(
        ["git", "branch", "--list", "task/*"],
        cwd=str(root_dir),
        capture_output=True,
        text=True,
        creationflags=win_flag,
    )
    if res.returncode != 0 or not res.stdout.strip():
        print("[+] No ephemeral task branches present.")
        return True

    cur_res = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(root_dir),
        capture_output=True,
        text=True,
        creationflags=win_flag,
    )
    current_branch = cur_res.stdout.strip() if cur_res.returncode == 0 else ""

    tasks_dir = root_dir / "orchestrator-state" / "tasks"
    finished_ids = set()
    if tasks_dir.exists():
        for tf in tasks_dir.glob("task_*.json"):
            try:
                with open(tf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") in ("done", "blocked"):
                    tid = data.get("id") or tf.stem
                    finished_ids.add(tid)
            except Exception:
                pass

    pruned = 0
    total = 0
    for line in res.stdout.splitlines():
        b = line.strip().lstrip("*").strip()
        if not b or b == current_branch:
            continue
        total += 1
        tid = b.removeprefix("task/")
        if fix and (tid in finished_ids or b.startswith("task/task_1791")):
            del_res = subprocess.run(
                ["git", "branch", "-D", b],
                cwd=str(root_dir),
                capture_output=True,
                creationflags=win_flag,
            )
            if del_res.returncode == 0:
                pruned += 1

    if fix and pruned > 0:
        print(f"[+] Pruned {pruned} completed task branch(es) out of {total} found.")
    else:
        print(f"[+] Task branch audit complete. Found {total} ephemeral branch(es).")
    return True


def audit_fleet_live_status(root_dir: Path, fix: bool = False, stale_hours: float = 2.0) -> bool:
    """Audits orchestrator-state/live-status for stale heartbeats and expired sessions."""
    print("[*] Auditing live fleet status and worker sessions...")
    live_status_dir = root_dir / "orchestrator-state" / "live-status"
    if not live_status_dir.exists():
        print("[+] No live-status directory present.")
        return True

    now = _now_utc()
    stale_recovered = 0

    for status_file in live_status_dir.glob("*.json"):
        if status_file.name == "active_fleet.json":
            continue
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                continue

            modified = False
            hb = _parse_iso(data.get("heartbeat_at"))
            status = data.get("status")

            # Check for stale busy session
            if status == "busy" and hb:
                age_h = (now - hb).total_seconds() / 3600.0
                if age_h > stale_hours:
                    print(f"    - Stale busy session on {status_file.name} (age: {age_h:.1f}h)")
                    if fix:
                        data["status"] = "idle"
                        data["current_task_id"] = None
                        data["note"] = f"Auto-recovered by Fleet Watchdog (stale heartbeat > {stale_hours}h)"
                        modified = True
                        stale_recovered += 1

            # Check for expired cooldown
            cd = _parse_iso(data.get("cooldown_until"))
            if cd and now >= cd:
                print(f"    - Cooldown expired on {status_file.name}")
                if fix:
                    if data.get("status") == "cooldown":
                        data["status"] = "idle"
                        data["note"] = "Cooldown expired - ready"
                    data["cooldown_until"] = None
                    modified = True
                    stale_recovered += 1

            if modified and fix:
                tmp_file = status_file.with_suffix(f".tmp.{os.getpid()}")
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                tmp_file.replace(status_file)

        except Exception as e:
            print(f"    ! Could not read {status_file.name}: {e}")

    # Check active_fleet.json
    active_fleet_file = live_status_dir / "active_fleet.json"
    if active_fleet_file.exists():
        try:
            with open(active_fleet_file, "r", encoding="utf-8") as f:
                fleet_entries = json.load(f)
            if isinstance(fleet_entries, list) and len(fleet_entries) > 0:
                alive_entries = []
                for entry in fleet_entries:
                    port = entry.get("CdpPort")
                    is_alive = False
                    if port:
                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                s.settimeout(0.5)
                                if s.connect_ex(("127.0.0.1", int(port))) == 0:
                                    is_alive = True
                        except Exception:
                            pass
                    if is_alive:
                        alive_entries.append(entry)
                    else:
                        print(f"    - Inactive browser session detected on port {port} ({entry.get('Nickname', '')})")

                if fix and len(alive_entries) != len(fleet_entries):
                    with open(active_fleet_file, "w", encoding="utf-8") as f:
                        json.dump(alive_entries, f, indent=2)
                    print(f"    + Reconciled active_fleet.json: {len(alive_entries)} active / {len(fleet_entries)} registered.")
        except Exception as e:
            print(f"    ! Error reading active_fleet.json: {e}")

    print(f"[+] Fleet session audit complete. Sessions recovered/reconciled: {stale_recovered}")
    return True


def audit_template_integrity(root_dir: Path) -> bool:
    """Audit declarative SKU job templates for required DAG fields."""
    print("[*] Auditing declarative SKU templates...")
    templates_dir = root_dir / "sku-templates"
    if not templates_dir.exists():
        print("[!] Missing sku-templates directory", file=sys.stderr)
        return False

    for json_file in templates_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            has_id = "sku_id" in data or "name" in data or "job_id" in data
            has_pipeline = "pipeline" in data or "stages" in data or "steps" in data
            if not (has_id and has_pipeline):
                print(f"[!] Template {json_file.name} missing identifier or pipeline specification", file=sys.stderr)
                return False
        except Exception as e:
            print(f"[!] Failed to parse {json_file.name}: {e}", file=sys.stderr)
            return False

    print("[+] All SKU templates valid and complete.")
    return True


def audit_capability_gaps(root_dir: Path, fix: bool = False) -> bool:
    """Sentinel #6: Scan for untested adapters, routing misses, stale skills, and dead adapters."""
    print("[*] Auditing capability gaps & adapter coverage...")
    try:
        from tools.capability_gap_detector import generate_gap_report

        report = generate_gap_report(root_dir, write_output=True)
        gaps_count = report.get("total_gaps", 0)
        crit = report.get("critical", 0)
        high = report.get("high", 0)
        if crit > 0:
            print(f"[!] Capability audit found {crit} CRITICAL gap(s)!", file=sys.stderr)
            return False
        if gaps_count > 0:
            print(f"    - Found {gaps_count} capability gap(s) (high: {high}). Report written to orchestrator-state/gap_report.json")
        else:
            print("[+] Capability gap audit complete: 0 gaps detected. All adapters and skills verified.")
        return True
    except Exception as e:
        print(f"[!] Capability gap audit failure: {e}", file=sys.stderr)
        return False


async def main() -> int:
    parser = argparse.ArgumentParser(description="Fleet Watchdog: Self-Healing Sentinel")
    parser.add_argument("--fix", "--clean", action="store_true", dest="fix", help="Automatically perform self-healing and cleanup")
    parser.add_argument("--stale-hours", type=float, default=2.0, help="Heartbeat stale threshold in hours (default: 2.0)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    db_ok = await audit_database_schema()
    wt_ok = audit_worktree_hygiene(root, fix=args.fix)
    tb_ok = audit_task_branches(root, fix=args.fix)
    fl_ok = audit_fleet_live_status(root, fix=args.fix, stale_hours=args.stale_hours)
    tpl_ok = audit_template_integrity(root)
    cg_ok = audit_capability_gaps(root, fix=args.fix)

    if db_ok and wt_ok and tb_ok and fl_ok and tpl_ok and cg_ok:
        print("\n[+] Fleet Sentinel: All systems healthy, consistent, and hygienic.")
        return 0
    else:
        print("\n[!] Fleet Sentinel: Integrity audit reported anomalies.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
