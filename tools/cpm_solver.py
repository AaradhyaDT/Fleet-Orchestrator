#!/usr/bin/env python3
"""tools/cpm_solver.py
-------------------
Mathematical Critical Path Method (CPM) DAG Solver for /adaptive-workflow.

Exact topological DAG solver computing Early Start (ES), Early Finish (EF),
Late Start (LS), Late Finish (LF), Total Slack (TS), and Free Slack (FS) with
zero prompt arithmetic (INV-CPM-SOLVER).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cpm_solver")


class DeterministicCPMSolver:
    """Exact topological DAG scheduler computing CPM metrics in pure Python."""

    @staticmethod
    def _extract_duration(task: Dict[str, Any]) -> float:
        """Extracts task duration/weight from common field aliases."""
        for key in ["duration_s", "duration", "cpm_weight", "weight"]:
            if key in task and task[key] is not None:
                try:
                    return float(task[key])
                except (ValueError, TypeError):
                    pass
        ta = task.get("time_allocation", {})
        if isinstance(ta, dict):
            for key in ["estimated_duration_s", "cpm_weight", "duration"]:
                if key in ta and ta[key] is not None:
                    try:
                        return float(ta[key])
                    except (ValueError, TypeError):
                        pass
        return 1.0

    @classmethod
    def solve(cls, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates exact CPM schedule for a list of task specifications."""
        if not tasks:
            return {"makespan": 0.0, "critical_path": [], "schedule": {}}

        nodes: Set[str] = set()
        durations: Dict[str, float] = {}
        preds: Dict[str, List[str]] = {}
        succs: Dict[str, List[str]] = {}

        for t in tasks:
            tid = str(t.get("id") or t.get("name") or t.get("task_id"))
            nodes.add(tid)
            durations[tid] = max(0.0, cls._extract_duration(t))
            preds[tid] = [str(p) for p in (t.get("dependencies") or t.get("preds") or t.get("predecessors") or [])]
            succs[tid] = []

        # Validate nodes & construct succs
        for tid, pred_list in preds.items():
            for p in pred_list:
                if p not in nodes:
                    nodes.add(p)
                    durations[p] = 1.0
                    preds[p] = []
                    succs[p] = []
                succs[p].append(tid)

        # Topological sorting via Kahn's algorithm
        in_degree = {n: len(preds[n]) for n in nodes}
        zero_in = [n for n in nodes if in_degree[n] == 0]
        topo_order: List[str] = []

        while zero_in:
            curr = zero_in.pop(0)
            topo_order.append(curr)
            for s in succs[curr]:
                in_degree[s] -= 1
                if in_degree[s] == 0:
                    zero_in.append(s)

        if len(topo_order) < len(nodes):
            raise ValueError("Cycle detected in CPM DAG; cannot compute topological critical path.")

        # Forward Pass: ES, EF
        es: Dict[str, float] = {}
        ef: Dict[str, float] = {}
        for n in topo_order:
            if not preds[n]:
                es[n] = 0.0
            else:
                es[n] = max(ef[p] for p in preds[n])
            ef[n] = round(es[n] + durations[n], 2)

        makespan = max(ef.values()) if ef else 0.0

        # Backward Pass: LS, LF
        ls: Dict[str, float] = {}
        lf: Dict[str, float] = {}
        for n in reversed(topo_order):
            if not succs[n]:
                lf[n] = makespan
            else:
                lf[n] = min(ls[s] for s in succs[n])
            ls[n] = round(lf[n] - durations[n], 2)

        # Slacks: TS, FS
        ts: Dict[str, float] = {}
        fs: Dict[str, float] = {}
        critical_path: List[str] = []

        for n in topo_order:
            t_slack = round(lf[n] - ef[n], 2)
            ts[n] = t_slack
            if succs[n]:
                f_slack = round(min(es[s] for s in succs[n]) - ef[n], 2)
            else:
                f_slack = round(makespan - ef[n], 2)
            fs[n] = f_slack
            if abs(t_slack) < 1e-4:
                critical_path.append(n)

        schedule: Dict[str, Dict[str, Any]] = {}
        for n in topo_order:
            schedule[n] = {
                "duration": durations[n],
                "ES": es[n],
                "EF": ef[n],
                "LS": ls[n],
                "LF": lf[n],
                "TS": ts[n],
                "FS": fs[n],
                "is_critical": abs(ts[n]) < 1e-4,
            }

        return {
            "makespan": round(makespan, 2),
            "critical_path": critical_path,
            "tasks_count": len(nodes),
            "schedule": schedule,
        }


def format_cpm_output(result: Dict[str, Any]) -> str:
    """Formats CPM schedule into a high-density, readable report."""
    lines = []
    lines.append("=" * 65)
    lines.append("  MATHEMATICAL CPM DAG SCHEDULE (INV-CPM-SOLVER)")
    lines.append("=" * 65)
    lines.append(f"  Project Makespan : {result.get('makespan')}s")
    lines.append(f"  Critical Path    : {' -> '.join(result.get('critical_path', []))}")
    lines.append(f"  Total Tasks      : {result.get('tasks_count')}")
    lines.append("-" * 65)
    lines.append(f"  {'Task ID':<15} {'Dur':<6} {'ES':<6} {'EF':<6} {'LS':<6} {'LF':<6} {'TS':<6} {'Crit'}")
    lines.append("-" * 65)
    for tid, s in result.get("schedule", {}).items():
        crit_mark = "*" if s.get("is_critical") else " "
        lines.append(
            f"  {tid:<15} {s.get('duration', 0):<6.1f} {s.get('ES', 0):<6.1f} {s.get('EF', 0):<6.1f} "
            f"{s.get('LS', 0):<6.1f} {s.get('LF', 0):<6.1f} {s.get('TS', 0):<6.1f} {crit_mark}"
        )
    lines.append("=" * 65)
    lines.append("  (* = Critical Path Task [TS == 0.0])")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic Topological CPM DAG Scheduler")
    parser.add_argument("--dag-json", help="Path to DAG JSON file or raw JSON string")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")

    args = parser.parse_args()

    raw_input = args.dag_json
    if not raw_input and not sys.stdin.isatty():
        raw_input = sys.stdin.read().strip()

    if not raw_input:
        parser.print_help()
        return 1

    try:
        p = Path(raw_input)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(raw_input)
    except Exception as e:
        print(f"[ERROR] Failed to parse DAG JSON: {e}", file=sys.stderr)
        return 1

    tasks = data if isinstance(data, list) else data.get("tasks", [])
    if not isinstance(tasks, list):
        print("[ERROR] DAG JSON must be a list of tasks or contain a 'tasks' array.", file=sys.stderr)
        return 1

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


if __name__ == "__main__":
    sys.exit(main())
