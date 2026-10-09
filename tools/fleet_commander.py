#!/usr/bin/env python3
"""
Fleet Commander: High-level process-boundary orchestrator for Copilot Fleet.
Enforces the Context Firebreak Invariant (INV-CTX-FIREBREAK):
- Redirects noisy child execution output to an isolated log file.
- Computes fleet health ratio H = (N_idle + N_busy) / N_total, warning if H < 0.35.
- Measures authentic pre/post credit usage deltas on the ledger.
- Emits ONLY a compact, structured manifest strictly <= 300 words to stdout.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.credit_ledger import resolve_state_dir
from tools.copilot_fleet import get_fleet_quota_metrics, cmd_batch, discover_accounts, load_env_fleet

logger = logging.getLogger("fleet_commander")


class FleetCommander:
    """Orchestrates batch tasks with context-firebreak isolation and quota accounting."""

    def __init__(self, state_dir: Path | str | None = None):
        self.state_dir = resolve_state_dir(state_dir)
        self.logs_dir = self.state_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def compute_health_ratio(self, metrics: dict[str, Any]) -> float:
        """
        Computes the fleet health ratio:
        H = (N_idle + N_busy) / N_total
        Returns 0.0 if N_total == 0.
        """
        fleet_info = metrics.get("fleet", {})
        counts = fleet_info.get("status_counts", {})
        n_total = fleet_info.get("total_registered_accounts", 0)
        if n_total == 0:
            return 0.0
        n_idle = counts.get("idle", 0)
        n_busy = counts.get("busy", 0)
        return round((n_idle + n_busy) / float(n_total), 4)

    def format_manifest(
        self,
        batch_id: str,
        h_ratio: float,
        pre_metrics: dict[str, Any],
        post_metrics: dict[str, Any],
        task_results: list[dict[str, Any]],
        log_file_path: Path | str | None = None,
        max_words: int = 300,
    ) -> str:
        """
        Generates a concise manifest of the completed batch run.
        Strictly enforces the <= max_words cap by word-splitting.
        """
        lines: list[str] = []
        lines.append(f"=== FLEET COMMANDER BATCH MANIFEST [{batch_id}] ===")

        if h_ratio < 0.35:
            lines.append(f"WARNING: Low fleet health H={h_ratio:.2f} (<0.35). Workers in cooldown or offline.")
        else:
            lines.append(f"Fleet Health: H={h_ratio:.2f} (Healthy)")

        pre_used = pre_metrics.get("fleet", {}).get("total_credits_used", 0.0)
        post_used = post_metrics.get("fleet", {}).get("total_credits_used", 0.0)
        credit_delta = max(0.0, round(post_used - pre_used, 2))
        rem = post_metrics.get("fleet", {}).get("total_credits_remaining", 0.0)
        burn_pct = post_metrics.get("fleet", {}).get("burn_rate_pct", 0.0)

        lines.append(
            f"Credits: Delta: {credit_delta:.2f} | Remaining: {rem:.2f} | Burn: {burn_pct:.2f}% "
            f"(Total Observed: {post_used:.2f})"
        )

        n_done = sum(1 for t in task_results if t.get("status") == "done")
        n_blocked = sum(1 for t in task_results if t.get("status") == "blocked")
        n_other = len(task_results) - n_done - n_blocked
        lines.append(f"Tasks: {len(task_results)} total ({n_done} done, {n_blocked} blocked, {n_other} other)")

        for t in task_results:
            tid = t.get("id", "unknown")
            stat = t.get("status", "unknown").upper()
            worker = t.get("worker", "-")
            summary = (t.get("summary") or t.get("spec") or "-")[:50]
            lines.append(f" - [{stat}] {tid} ({worker}): {summary}")

        if log_file_path:
            lines.append(f"Full logs: {log_file_path}")

        text = "\n".join(lines)
        words = text.split()
        if len(words) > max_words:
            # Enforce hard cap
            truncated_words = words[: max_words - 4] + ["[TRUNCATED", "TO", "300", "WORDS]"]
            text = " ".join(truncated_words)

        return text

    async def run_batch(
        self,
        specs: list[str],
        concurrency: int = 2,
        dry_run: bool = False,
        task_file: str | None = None,
        conversation_id: str | None = None,
        no_antigravity: bool = False,
    ) -> str:
        """
        Executes a batch of tasks, redirecting all child output to a log file,
        and returns a concise manifest string.
        """
        batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        log_path = self.logs_dir / f"commander_{batch_id}.log"

        pre_metrics = get_fleet_quota_metrics(self.state_dir)
        h_ratio = self.compute_health_ratio(pre_metrics)

        # Prepare batch args for cmd_batch
        args = argparse.Namespace(
            specs=specs,
            file=task_file,
            concurrency=concurrency,
            dry_run=dry_run,
            state_dir=str(self.state_dir),
            conversation_id=conversation_id,
            no_antigravity=no_antigravity,
        )

        # Redirect child output to log file
        with open(log_path, "w", encoding="utf-8") as log_f:
            with contextlib.redirect_stdout(log_f), contextlib.redirect_stderr(log_f):
                await cmd_batch(args)

        post_metrics = get_fleet_quota_metrics(self.state_dir)

        # Harvest task results from checkpoints and tasks dirs
        tasks_dir = self.state_dir / "tasks"
        checkpoints_dir = self.state_dir / "checkpoints"
        task_results: list[dict[str, Any]] = []

        # Find checkpoints created or updated
        if checkpoints_dir.exists():
            for cp_file in sorted(checkpoints_dir.glob("task_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    with open(cp_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    task_results.append({
                        "id": data.get("task_id", cp_file.stem),
                        "status": "done",
                        "worker": data.get("submitted_by", "-"),
                        "summary": data.get("summary", ""),
                    })
                    if len(task_results) >= len(specs):
                        break
                except Exception:
                    pass

        manifest = self.format_manifest(
            batch_id=batch_id,
            h_ratio=h_ratio,
            pre_metrics=pre_metrics,
            post_metrics=post_metrics,
            task_results=task_results,
            log_file_path=log_path,
            max_words=300,
        )
        return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Fleet Commander: Context-Firebreak Task Orchestrator")
    parser.add_argument("--specs", nargs="+", default=[], help="Task specifications to execute")
    parser.add_argument("--file", type=str, default=None, help="JSON file containing task specifications")
    parser.add_argument("--concurrency", type=int, default=2, help="Number of concurrent workers (default: 2)")
    parser.add_argument("--dry-run", action="store_true", help="Execute in dry-run simulation mode")
    parser.add_argument("--state-dir", type=str, default=None, help="Path to orchestrator-state directory")
    parser.add_argument("--conversation-id", type=str, default=None, help="Explicit Antigravity conversation ID")
    parser.add_argument("--no-antigravity", action="store_true", help="Disable Antigravity context inheritance")

    args = parser.parse_args()
    if not args.specs and not args.file:
        print("[!] No tasks specified. Use --specs '...' or --file tasks.json")
        sys.exit(1)

    commander = FleetCommander(state_dir=args.state_dir)
    manifest = asyncio.run(
        commander.run_batch(
            specs=args.specs,
            concurrency=args.concurrency,
            dry_run=args.dry_run,
            task_file=args.file,
            conversation_id=args.conversation_id,
            no_antigravity=args.no_antigravity,
        )
    )
    # Output ONLY the manifest to stdout
    print(manifest)


if __name__ == "__main__":
    main()
