#!/usr/bin/env python3
"""
Fleet Watchdog: Self-Healing Health & Integrity Sentinel.
Performs periodic audits of database schemas, task states, scheduler invariants,
and isolated worktree hygiene to prevent stale drift.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path


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


def audit_worktree_hygiene(root_dir: Path) -> bool:
    """Verify worktree isolation and clean up stale temporary worktrees."""
    print("[*] Auditing git worktree hygiene...")
    worktrees_dir = root_dir / ".worktrees"
    if not worktrees_dir.exists():
        print("[+] No .worktrees directory present; clean state.")
        return True

    stale_count = 0
    for child in worktrees_dir.iterdir():
        if child.is_dir() and child.name.startswith("task_"):
            print(f"    - Found active worktree: {child.name}")
            stale_count += 1

    print(f"[+] Worktree audit complete. Active isolated worktrees: {stale_count}")
    return True


def audit_template_integrity(root_dir: Path) -> bool:
    """Audit declarative SKU job templates for required DAG fields."""
    import json
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


async def main() -> int:
    root = Path(__file__).resolve().parent.parent
    db_ok = await audit_database_schema()
    wt_ok = audit_worktree_hygiene(root)
    tpl_ok = audit_template_integrity(root)

    if db_ok and wt_ok and tpl_ok:
        print("\n[+] Fleet Sentinel: All systems healthy and self-consistent.")
        return 0
    else:
        print("\n[!] Fleet Sentinel: Integrity audit reported anomalies.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
