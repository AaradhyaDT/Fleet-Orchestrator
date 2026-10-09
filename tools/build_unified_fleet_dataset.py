#!/usr/bin/env python3
"""
tools/build_unified_fleet_dataset.py
------------------------------------
Merges all harvested Antigravity datasets into a single, unified master dataset:
  1. Task Time & Intent Allocation (dataset/task_time_train.jsonl)
  2. Agent-Reflex Self-Healing Recovery (dataset/trajectories/agent_reflex_train.jsonl)
  3. Tool Sequence Speculation (dataset/trajectories/tool_speculator_train.jsonl)

Outputs:
  - dataset/unified_fleet_train.jsonl (4,729 samples)
  - dataset/unified_fleet_eval.jsonl (1,182 samples)
"""

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "dataset"
TRAJ_DIR = DATASET_DIR / "trajectories"

train_sources = [
    DATASET_DIR / "task_time_train.jsonl",
    TRAJ_DIR / "agent_reflex_train.jsonl",
    TRAJ_DIR / "tool_speculator_train.jsonl",
]

eval_sources = [
    DATASET_DIR / "task_time_eval.jsonl",
    TRAJ_DIR / "agent_reflex_eval.jsonl",
    TRAJ_DIR / "tool_speculator_eval.jsonl",
]

def merge_files(sources, out_file):
    all_rows = []
    for s in sources:
        if s.exists():
            with open(s, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        all_rows.append(json.loads(line.strip()))
    random.seed(42)
    random.shuffle(all_rows)
    with open(out_file, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(all_rows)

if __name__ == "__main__":
    train_count = merge_files(train_sources, DATASET_DIR / "unified_fleet_train.jsonl")
    eval_count = merge_files(eval_sources, DATASET_DIR / "unified_fleet_eval.jsonl")
    print(f"Created unified_fleet_train.jsonl with {train_count} samples.")
    print(f"Created unified_fleet_eval.jsonl with {eval_count} samples.")
