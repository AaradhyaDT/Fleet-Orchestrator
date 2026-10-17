#!/usr/bin/env python3
"""
tools/dag_planner.py
Deterministic Critical Path Method (CPM) DAG Planner & Topological Scheduler.

Provides:
- Exact topological DAG solver using Kahn's algorithm and DFS cycle detection.
- Mathematical Early Start (ES), Early Finish (EF), Late Start (LS), Late Finish (LF).
- Total Float (TF) / Slack and Free Float (FF) calculations (zero token arithmetic).
- Critical path derivation (tasks with TF == 0.0).
- Automatic predecessor satisfaction and dependency gating verification.
- Batch submission of DAG task bundles into orchestrator-state/tasks/.
- CLI interface: --plan <file.json>, --submit <file.json>, --status <bundle_id>.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure Fleet-Orchestrator root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.copilot_queue_worker import resolve_state_dir
from tools.credit_ledger import atomic_write_json

logger = logging.getLogger("dag_planner")


class DAGCycleError(ValueError):
    """Raised when a task DAG contains a directed cycle."""

    def __init__(self, cycle: List[str], unresolved_tasks: List[str], remediation: str):
        self.cycle = cycle
        self.unresolved_tasks = unresolved_tasks
        self.remediation = remediation
        cycle_str = " -> ".join(cycle)
        super().__init__(
            f"Directed cycle detected: {cycle_str}. "
            f"Unresolved tasks: {unresolved_tasks}. "
            f"Remediation: {remediation}"
        )


def find_directed_cycle(adj: Dict[str, Set[str]], nodes: List[str]) -> Optional[List[str]]:
    """Finds one directed cycle in the graph using iterative DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}

    for start in sorted(nodes):
        if color[start] != WHITE:
            continue
        stack: List[Tuple[str, Any]] = [(start, iter(sorted(adj.get(start, set()))))]
        color[start] = GRAY

        while stack:
            u, neighbors = stack[-1]
            try:
                v = next(neighbors)
            except StopIteration:
                color[u] = BLACK
                stack.pop()
                continue

            if color[v] == GRAY:
                cycle = [v]
                for frame_node, _ in reversed(stack):
                    cycle.append(frame_node)
                    if frame_node == v:
                        break
                cycle.reverse()
                return cycle
            elif color[v] == WHITE:
                color[v] = GRAY
                stack.append((v, iter(sorted(adj.get(v, set())))))

    return None


class DeterministicCPMSolver:
    """Exact topological DAG solver in pure Python with zero prompt arithmetic."""

    @classmethod
    def calculate_schedule(cls, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes Early Start (ES), Early Finish (EF), Late Start (LS), Late Finish (LF),
        Total Float/Slack (TS), and Free Slack (FS) for all tasks.
        """
        if not tasks:
            return {
                "project_duration": 0.0,
                "critical_path": [],
                "parallel_slack": [],
                "tasks": {},
            }

        task_dict = {t["id"]: t for t in tasks}
        preds = {t["id"]: set(t.get("predecessors", [])) for t in tasks}
        succs: Dict[str, Set[str]] = {t["id"]: set() for t in tasks}

        for tid, plist in preds.items():
            for p in plist:
                if p not in task_dict:
                    raise ValueError(f"Task '{tid}' references unknown predecessor '{p}'")
                succs[p].add(tid)

        in_degree = {tid: len(plist) for tid, plist in preds.items()}
        zero_in = sorted([tid for tid, deg in in_degree.items() if deg == 0])
        topo_order: List[str] = []

        while zero_in:
            u = zero_in.pop(0)
            topo_order.append(u)
            for s in sorted(succs[u]):
                in_degree[s] -= 1
                if in_degree[s] == 0:
                    zero_in.append(s)

        if len(topo_order) != len(tasks):
            unresolved = sorted([tid for tid in task_dict if tid not in set(topo_order)])
            cycle = find_directed_cycle(succs, list(task_dict.keys()))
            if cycle is None:
                cycle = unresolved[:2] + [unresolved[0]] if len(unresolved) >= 2 else unresolved

            if len(cycle) >= 3:
                edge_to_break = f"Remove dependency '{cycle[-2]}' -> '{cycle[-1]}'"
            else:
                edge_to_break = f"Review mutual dependencies among: {unresolved}"

            raise DAGCycleError(cycle=cycle, unresolved_tasks=unresolved, remediation=edge_to_break)

        def _get_task_duration(t: Dict[str, Any]) -> float:
            if "duration" in t:
                return float(t["duration"])
            if "cpm_weight" in t:
                return float(t["cpm_weight"])
            if "estimated_duration_s" in t:
                return float(t["estimated_duration_s"])
            if "time_allocation" in t and isinstance(t["time_allocation"], dict):
                ta = t["time_allocation"]
                if "cpm_weight" in ta:
                    return float(ta["cpm_weight"])
                if "estimated_duration_s" in ta:
                    return float(ta["estimated_duration_s"])
            return 1.0

        # Forward Pass: ES and EF
        es: Dict[str, float] = {}
        ef: Dict[str, float] = {}
        for u in topo_order:
            duration = _get_task_duration(task_dict[u])
            u_preds = preds[u]
            es[u] = max([ef[p] for p in u_preds], default=0.0)
            ef[u] = round(es[u] + duration, 4)

        project_duration = max(ef.values()) if ef else 0.0

        # Backward Pass: LF and LS
        ls: Dict[str, float] = {}
        lf: Dict[str, float] = {}
        for u in reversed(topo_order):
            duration = _get_task_duration(task_dict[u])
            u_succs = succs[u]
            lf[u] = min([ls[s] for s in u_succs], default=project_duration)
            ls[u] = round(lf[u] - duration, 4)

        ts: Dict[str, float] = {}
        fs: Dict[str, float] = {}
        critical_path: List[str] = []
        parallel_slack: List[str] = []

        for u in topo_order:
            total_float = round(lf[u] - ef[u], 4)
            ts[u] = total_float
            u_succs = succs[u]
            free_float = round(min([es[s] for s in u_succs], default=project_duration) - ef[u], 4)
            fs[u] = free_float

            if abs(total_float) < 1e-6:
                critical_path.append(u)
            else:
                parallel_slack.append(u)

        schedule_details: Dict[str, Any] = {}
        for u in topo_order:
            dur = _get_task_duration(task_dict[u])
            schedule_details[u] = {
                "duration": dur,
                "ES": es[u],
                "EF": ef[u],
                "LS": ls[u],
                "LF": lf[u],
                "TS": ts[u],
                "FS": fs[u],
                "is_critical": abs(ts[u]) < 1e-6,
                "predecessors": sorted(list(preds[u])),
                "successors": sorted(list(succs[u])),
            }

        return {
            "project_duration": project_duration,
            "critical_path": critical_path,
            "parallel_slack": parallel_slack,
            "tasks": schedule_details,
            "topological_order": topo_order,
        }


def check_predecessors_satisfied(task: Dict[str, Any], state_dir: Path) -> Tuple[bool, List[str]]:
    """
    Verifies whether all predecessors of a task have written successful checkpoints or reached status 'done'.
    Returns (all_satisfied: bool, pending_predecessors: List[str]).
    """
    preds = task.get("predecessors", [])
    if not preds:
        return True, []

    tasks_dir = state_dir / "tasks"
    checkpoints_dir = state_dir / "checkpoints"

    unresolved: List[str] = []
    for pred_id in preds:
        ckpt_file = checkpoints_dir / f"{pred_id}.json"
        task_file = tasks_dir / f"{pred_id}.json"

        is_done = False
        if ckpt_file.exists():
            is_done = True
        elif task_file.exists():
            try:
                t_data = json.loads(task_file.read_text(encoding="utf-8"))
                if t_data.get("status") in ("done", "completed"):
                    is_done = True
            except Exception:
                pass

        if not is_done:
            unresolved.append(pred_id)

    return (len(unresolved) == 0), unresolved


def submit_dag_bundle(
    dag_path: Path | str,
    state_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Parses a DAG specification file, solves the mathematical schedule,
    and atomically creates tasks with dependency metadata in orchestrator-state/tasks/.
    """
    p = Path(dag_path)
    if not p.exists():
        raise FileNotFoundError(f"DAG definition file not found: {p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    bundle_id = data.get("bundle_id") or data.get("sku") or f"dag_{int(time.time())}"

    # Solve CPM Schedule mathematically
    schedule = DeterministicCPMSolver.calculate_schedule(tasks)

    resolved_state = resolve_state_dir(str(state_dir) if state_dir else None)
    tasks_dir = resolved_state / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    enqueued_tasks: List[str] = []
    for t in tasks:
        tid = t["id"]
        sched_info = schedule["tasks"][tid]
        
        # Prepare task payload conforming to orchestrator contract
        task_payload = {
            "id": tid,
            "task_id": tid,
            "bundle_id": bundle_id,
            "kind": t.get("kind", "code"),
            "stage": t.get("stage", "code"),
            "status": "pending",
            "spec": t.get("spec") or t.get("prompt") or f"Execute DAG task {tid}",
            "prompt": t.get("spec") or t.get("prompt") or f"Execute DAG task {tid}",
            "predecessors": sched_info["predecessors"],
            "successors": sched_info["successors"],
            "cpm": {
                "duration": sched_info["duration"],
                "ES": sched_info["ES"],
                "EF": sched_info["EF"],
                "LS": sched_info["LS"],
                "LF": sched_info["LF"],
                "total_float": sched_info["TS"],
                "free_float": sched_info["FS"],
                "is_critical": sched_info["is_critical"],
            },
            "auto_tier": t.get("auto_tier", "intelligence" if sched_info["is_critical"] else "balance"),
            "recommended_model": t.get("model") or t.get("recommended_model"),
            "timeout": t.get("timeout", max(300.0, sched_info["duration"] * 60.0)),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if not dry_run:
            dest_file = tasks_dir / f"{tid}.json"
            atomic_write_json(dest_file, task_payload)
        enqueued_tasks.append(tid)

    return {
        "bundle_id": bundle_id,
        "enqueued_count": len(enqueued_tasks),
        "enqueued_tasks": enqueued_tasks,
        "project_duration": schedule["project_duration"],
        "critical_path": schedule["critical_path"],
        "parallel_slack": schedule["parallel_slack"],
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(description="Deterministic Critical Path Method (CPM) DAG Planner")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # plan: inspect and solve schedule
    p_plan = subparsers.add_parser("plan", help="Solve DAG schedule and print CPM critical path table")
    p_plan.add_argument("file", type=str, help="Path to JSON file containing DAG tasks")
    p_plan.add_argument("--json", action="store_true", help="Output full schedule in JSON format")

    # submit: solve schedule and materialize into orchestrator queue
    p_sub = subparsers.add_parser("submit", help="Solve DAG and enqueue all tasks into orchestrator-state/tasks")
    p_sub.add_argument("file", type=str, help="Path to JSON file containing DAG tasks")
    p_sub.add_argument("--dry-run", action="store_true", help="Simulate submission without writing task files")
    p_sub.add_argument("--state-dir", type=str, default=None, help="Custom orchestrator-state directory")

    args = parser.parse_args()

    if args.subcommand == "plan":
        p = Path(args.file)
        if not p.exists():
            print(f"Error: file not found: {p}", file=sys.stderr)
            sys.exit(1)
        data = json.loads(p.read_text(encoding="utf-8"))
        tasks = data.get("tasks", [])
        schedule = DeterministicCPMSolver.calculate_schedule(tasks)

        if getattr(args, "json", False):
            print(json.dumps(schedule, indent=2))
        else:
            print("===========================================================================")
            print(f"  DETERMINISTIC CPM DAG SCHEDULE ({len(tasks)} Tasks)")
            print("===========================================================================")
            print(f"  Project Duration : {schedule['project_duration']:.2f}")
            print(f"  Critical Path    : {' -> '.join(schedule['critical_path'])}")
            print(f"  Parallel Slack   : {', '.join(schedule['parallel_slack']) if schedule['parallel_slack'] else 'None'}")
            print("---------------------------------------------------------------------------")
            print(f"{'Task ID':<18} | {'Dur':<5} | {'ES':<6} | {'EF':<6} | {'LS':<6} | {'LF':<6} | {'Float':<6} | {'Status'}")
            print("-" * 75)
            for tid in schedule["topological_order"]:
                info = schedule["tasks"][tid]
                crit_badge = "CRITICAL" if info["is_critical"] else "Slack"
                print(f"{tid:<18} | {info['duration']:<5.1f} | {info['ES']:<6.1f} | {info['EF']:<6.1f} | {info['LS']:<6.1f} | {info['LF']:<6.1f} | {info['TS']:<6.1f} | {crit_badge}")
            print("===========================================================================")

    elif args.subcommand == "submit":
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
