#!/usr/bin/env python3
"""
tools/harvest_task_time_dataset.py
-----------------------------------
High-throughput empirical dataset harvester for SLM task time allocation.
Ingests:
  1. Antigravity chat transcripts (~/.gemini/antigravity/brain/*/transcript.jsonl)
  2. Fleet Orchestrator completed task checkpoints & tasks (orchestrator-state/)
Emits instruction-tuning JSONL pairs:
  - dataset/task_time_train.jsonl (80%)
  - dataset/task_time_eval.jsonl (20%)
  - dataset/dataset_summary.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("harvest_task_time")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAIN_ROOT = Path.home() / ".gemini" / "antigravity" / "brain"
CHECKPOINTS_DIR = PROJECT_ROOT / "orchestrator-state" / "checkpoints"
TASKS_DIR = PROJECT_ROOT / "orchestrator-state" / "tasks"
DATASET_DIR = PROJECT_ROOT / "dataset"

SYSTEM_INSTRUCTION = (
    "You are the high-speed Intent, Skill, and Task Time Allocation Router for the Aaradhya development ecosystem. "
    "Classify the incoming user intent into the exact lifecycle archetype, tier, 2D matrix cell, "
    "primary skill, supporting skills, velocity profile, and task time allocation (tier, estimated_duration_s, "
    "timeout_ceiling_s, cpm_weight, execution_route) in strict JSON format."
)


def clean_prompt_text(raw_text: str) -> str:
    """Strips XML wrappers, metadata, and trailing control tags from user prompt."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    
    # Strip <USER_REQUEST> ... </USER_REQUEST> tags if present
    match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    else:
        # Strip standalone opening/closing tags
        text = re.sub(r"</?USER_REQUEST>", "", text, flags=re.IGNORECASE).strip()

    # Strip ADDITIONAL_METADATA and USER_SETTINGS_CHANGE blocks
    text = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    text = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    
    # Collapse multiple whitespaces/newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def assign_time_tier(duration_s: float) -> str:
    """Categorizes duration into discrete time complexity tiers."""
    if duration_s < 15.0:
        return "T0_MICRO"
    elif duration_s < 60.0:
        return "T1_FAST"
    elif duration_s < 180.0:
        return "T2_MEDIUM"
    elif duration_s < 480.0:
        return "T3_LONG"
    else:
        return "T4_EPIC"


def assign_execution_route(time_tier: str, tool_count: int, prompt_lower: str) -> str:
    """Determines optimal execution route based on duration tier and complexity."""
    if any(k in prompt_lower for k in ["swarm", "fleet", "worker", "batch"]):
        return "FLEET_WORKER"
    if time_tier in ("T0_MICRO", "T1_FAST") and tool_count <= 4:
        return "DIRECT_FAST"
    elif time_tier in ("T2_MEDIUM", "T3_LONG") or tool_count > 6:
        return "SUBAGENT"
    elif time_tier == "T4_EPIC":
        return "FLEET_WORKER"
    return "SUBAGENT"


def calculate_cpm_weight(duration_s: float) -> float:
    """Calculates normalized CPM duration factor D_j (base 30s unit)."""
    return round(max(0.5, duration_s / 30.0), 2)


def calculate_timeout_ceiling(duration_s: float) -> int:
    """Calculates safety timeout ceiling with 30s floor and 1200s ceiling."""
    calculated = int(math.ceil(max(30.0, round(duration_s * 2.2, 4))))
    return min(1200, calculated)


def infer_routing_metadata(prompt: str) -> Dict[str, Any]:
    """Derives archetype, tier, matrix cell, policy, and skills from prompt semantics."""
    p = prompt.lower()
    if any(k in p for k in ["iv-ii", "iv-i", "syllabus", "semester", "super-nlm", "notebooklm", "studyhub", "notes"]):
        return {
            "archetype": "RESEARCH_ACADEMIC",
            "tier": "Tier 2" if any(k in p for k in ["scaffold", "batch", "extract"]) else "Tier 1",
            "matrix_cell": "(V1, R1)",
            "policy": "STAR_SUBAGENTS",
            "primary_skill": "academic-notebook-architect" if "notes" in p or "scaffold" in p else "super-nlm",
            "supporting_skills": ["fleet-orchestrator"],
            "velocity": "TURBO" if "batch" in p else "BALANCED",
        }
    if any(k in p for k in ["firmware", "dsp", "radar", "stm32", "freertos", "filter", "rf", "telecom"]):
        return {
            "archetype": "DOMAIN_HARDWARE",
            "tier": "Tier 2",
            "matrix_cell": "(V0, R1)",
            "policy": "BRANCH_GUARD",
            "primary_skill": "dsp-signal-engine" if "filter" in p else "embedded-firmware-scaffold",
            "supporting_skills": ["systems-concurrency-harness"],
            "velocity": "BALANCED",
        }
    if any(k in p for k in ["portfolio", "aaradhyadt.github.io", "access.js", "navbar", "css", "html", "react"]):
        return {
            "archetype": "FRONTEND_PRODUCT",
            "tier": "Tier 1",
            "matrix_cell": "(V0, R2)" if "access.js" in p else "(V0, R1)",
            "policy": "SURGICAL_LOCK" if "access.js" in p else "BRANCH_GUARD",
            "primary_skill": "portfolio-project-manager" if "project" in p else "design-taste-frontend",
            "supporting_skills": ["modern-web-guidance", "github-workflow"],
            "velocity": "BALANCED",
        }
    if any(k in p for k in ["swarm", "fleet", "worker", "copilot-w", "teamwork"]):
        return {
            "archetype": "SWARM_ORCHESTRATION",
            "tier": "Tier 2",
            "matrix_cell": "(V2, R0)",
            "policy": "FLEET_SWARM",
            "primary_skill": "fleet-orchestrator",
            "supporting_skills": ["adaptive-workflow"],
            "velocity": "TURBO",
        }
    if any(k in p for k in ["forensics", "vault", "lock", "pe header", "ads", "winpilot"]):
        return {
            "archetype": "SYSADMIN_SECURITY",
            "tier": "Tier 1",
            "matrix_cell": "(V0, R1)",
            "policy": "BRANCH_GUARD",
            "primary_skill": "cyber-forensics" if "forensics" in p else "win-vault",
            "supporting_skills": [],
            "velocity": "BALANCED",
        }
    return {
        "archetype": "ENGINEERING_DEV",
        "tier": "Tier 1" if len(p.split()) < 15 else "Tier 2",
        "matrix_cell": "(V0, R0)",
        "policy": "DIRECT_FAST",
        "primary_skill": "github-workflow",
        "supporting_skills": [],
        "velocity": "BALANCED",
    }


def parse_iso_dt(dt_str: str) -> Optional[datetime]:
    """Robust ISO 8601 parser."""
    try:
        clean_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None


def harvest_transcripts(brain_path: Path, max_conversations: Optional[int] = None) -> List[Dict[str, Any]]:
    """Crawls brain directory to extract empirical prompt-to-duration samples."""
    samples: List[Dict[str, Any]] = []
    if not brain_path.exists():
        logger.warning(f"Brain path does not exist: {brain_path}")
        return samples

    conv_dirs = [d for d in brain_path.iterdir() if d.is_dir()]
    if max_conversations:
        conv_dirs = sorted(conv_dirs, key=lambda d: d.stat().st_mtime, reverse=True)[:max_conversations]

    logger.info(f"Scanning {len(conv_dirs)} conversation directories...")

    for cdir in conv_dirs:
        transcript_file = cdir / ".system_generated" / "logs" / "transcript.jsonl"
        if not transcript_file.exists():
            continue

        turns: List[Dict[str, Any]] = []
        curr_turn: Optional[Dict[str, Any]] = None

        try:
            with open(transcript_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    etype = entry.get("type")
                    source = entry.get("source")

                    if etype == "USER_INPUT" and source == "USER_EXPLICIT":
                        if curr_turn:
                            turns.append(curr_turn)
                        raw_c = entry.get("content", "")
                        curr_turn = {
                            "raw_prompt": raw_c,
                            "start_ts": entry.get("created_at"),
                            "end_ts": entry.get("created_at"),
                            "tool_calls_count": 0,
                            "tool_types": set(),
                        }
                    elif curr_turn:
                        tcalls = entry.get("tool_calls", [])
                        if tcalls:
                            curr_turn["tool_calls_count"] += len(tcalls)
                            for tc in tcalls:
                                if isinstance(tc, dict) and "name" in tc:
                                    curr_turn["tool_types"].add(tc["name"])
                        ts = entry.get("created_at")
                        if ts:
                            curr_turn["end_ts"] = ts
            if curr_turn:
                turns.append(curr_turn)

            for t in turns:
                prompt = clean_prompt_text(t["raw_prompt"])
                # Quality filter: skip empty prompts, single punctuation, or ultra short prompts
                if len(prompt) < 5 or prompt.startswith("continue") and len(prompt) < 15:
                    continue

                # Filter out pure chat without tool executions
                if t["tool_calls_count"] < 1:
                    continue

                dt_start = parse_iso_dt(t["start_ts"])
                dt_end = parse_iso_dt(t["end_ts"])
                if not dt_start or not dt_end:
                    continue

                duration_s = (dt_end - dt_start).total_seconds()
                # Exclude outliers: < 2s (instant cancel) or > 1800s (idle pause/stalled)
                if duration_s < 2.0 or duration_s > 1800.0:
                    continue

                samples.append({
                    "prompt": prompt,
                    "duration_s": round(duration_s, 1),
                    "tool_count": t["tool_calls_count"],
                    "tool_types": sorted(list(t["tool_types"])),
                    "source": "antigravity_transcript",
                    "conv_id": cdir.name,
                })
        except Exception as e:
            logger.debug(f"Error parsing transcript {transcript_file}: {e}")

    logger.info(f"Harvested {len(samples)} valid turns from transcripts.")
    return samples


def harvest_checkpoints(checkpoints_path: Path, tasks_path: Path) -> List[Dict[str, Any]]:
    """Crawls Fleet-Orchestrator checkpoints to extract empirical worker run durations."""
    samples: List[Dict[str, Any]] = []
    if not checkpoints_path.exists():
        return samples

    cp_files = list(checkpoints_path.glob("task_*.json"))
    for cpf in cp_files:
        try:
            with open(cpf, "r", encoding="utf-8") as f:
                cp = json.load(f)
            tid = cp.get("task_id")
            sub_ts = cp.get("submitted_at")
            if not tid or not sub_ts:
                continue

            # Look for matching task in tasks_path
            tf = tasks_path / f"{tid}.json"
            spec = ""
            created_ts = None
            if tf.exists():
                with open(tf, "r", encoding="utf-8") as f:
                    tdata = json.load(f)
                spec = tdata.get("spec") or tdata.get("prompt", "")
                created_ts = tdata.get("created_at")
            else:
                summary = cp.get("summary", "")
                spec = f"Fleet worker execution: {summary}"

            prompt = clean_prompt_text(spec)
            if not prompt or len(prompt) < 8:
                continue

            dt_sub = parse_iso_dt(sub_ts)
            dt_cre = parse_iso_dt(created_ts) if created_ts else None
            
            # Headless execution duration
            duration_s = 45.0  # Safe default baseline
            if dt_cre and dt_sub:
                diff = (dt_sub - dt_cre).total_seconds()
                if 5.0 <= diff <= 1200.0:
                    duration_s = diff

            samples.append({
                "prompt": prompt,
                "duration_s": round(duration_s, 1),
                "tool_count": 3,
                "tool_types": ["git", "copilot_cli"],
                "source": "fleet_checkpoint",
                "conv_id": tid,
            })
        except Exception:
            pass

    logger.info(f"Harvested {len(samples)} valid tasks from fleet checkpoints.")
    return samples


def format_training_example(sample: Dict[str, Any]) -> Dict[str, Any]:
    """Formats harvested sample into Alpaca/ShareGPT instruction tuning schema."""
    prompt = sample["prompt"]
    duration_s = float(sample["duration_s"])
    tool_count = int(sample.get("tool_count", 1))

    # Calibrated headless multiplier: convert interactive multi-turn duration to expected headless worker runtime
    is_interactive = sample.get("source") == "antigravity_transcript"
    worker_duration_s = round(duration_s * 0.7, 1) if is_interactive else duration_s
    worker_duration_s = max(5.0, worker_duration_s)

    time_tier = assign_time_tier(worker_duration_s)
    route = assign_execution_route(time_tier, tool_count, prompt.lower())
    cpm_w = calculate_cpm_weight(worker_duration_s)
    timeout_s = calculate_timeout_ceiling(worker_duration_s)

    routing_meta = infer_routing_metadata(prompt)

    output_payload = {
        "archetype": routing_meta["archetype"],
        "tier": routing_meta["tier"],
        "matrix_cell": routing_meta["matrix_cell"],
        "policy": routing_meta["policy"],
        "primary_skill": routing_meta["primary_skill"],
        "supporting_skills": routing_meta["supporting_skills"],
        "velocity": routing_meta["velocity"],
        "time_allocation": {
            "tier": time_tier,
            "estimated_duration_s": int(round(worker_duration_s)),
            "timeout_ceiling_s": timeout_s,
            "cpm_weight": cpm_w,
            "execution_route": route,
        },
    }

    return {
        "instruction": SYSTEM_INSTRUCTION,
        "input": prompt,
        "output": json.dumps(output_payload, ensure_ascii=False),
    }


def export_dataset(
    samples: List[Dict[str, Any]],
    output_dir: Path,
    eval_split_ratio: float = 0.20,
    seed: int = 42,
) -> Tuple[int, int]:
    """Splits dataset into train/eval sets and writes JSONL files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    random.seed(seed)
    
    # Deduplicate prompts
    seen_prompts = set()
    deduped_samples = []
    for s in samples:
        norm_key = s["prompt"].strip().lower()
        if norm_key not in seen_prompts:
            seen_prompts.add(norm_key)
            deduped_samples.append(s)

    random.shuffle(deduped_samples)
    eval_count = max(1, int(len(deduped_samples) * eval_split_ratio))
    eval_samples = deduped_samples[:eval_count]
    train_samples = deduped_samples[eval_count:]

    train_file = output_dir / "task_time_train.jsonl"
    eval_file = output_dir / "task_time_eval.jsonl"
    summary_file = output_dir / "dataset_summary.json"

    with open(train_file, "w", encoding="utf-8") as f:
        for s in train_samples:
            ex = format_training_example(s)
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    with open(eval_file, "w", encoding="utf-8") as f:
        for s in eval_samples:
            ex = format_training_example(s)
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    durations = [s["duration_s"] for s in deduped_samples]
    tier_counts: Dict[str, int] = {}
    for d in durations:
        tier = assign_time_tier(d)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_unique_samples": len(deduped_samples),
        "train_samples": len(train_samples),
        "eval_samples": len(eval_samples),
        "split_ratio": f"{int((1 - eval_split_ratio)*100)}/{int(eval_split_ratio*100)}",
        "duration_distribution": {
            "min_s": min(durations) if durations else 0,
            "median_s": sorted(durations)[len(durations)//2] if durations else 0,
            "max_s": max(durations) if durations else 0,
            "avg_s": round(sum(durations) / len(durations), 1) if durations else 0,
        },
        "time_tier_breakdown": tier_counts,
        "train_file": str(train_file),
        "eval_file": str(eval_file),
    }

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Dataset generated: {len(train_samples)} train, {len(eval_samples)} eval. Summary saved to {summary_file}")
    return len(train_samples), len(eval_samples)


def main():
    parser = argparse.ArgumentParser(description="Harvest empirical task duration dataset from chat transcripts and checkpoints.")
    parser.add_argument("--brain-dir", type=str, default=str(BRAIN_ROOT), help="Path to Antigravity brain directory.")
    parser.add_argument("--output-dir", type=str, default=str(DATASET_DIR), help="Output directory for generated JSONL datasets.")
    parser.add_argument("--eval-ratio", type=float, default=0.20, help="Ratio for evaluation split (default 0.20).")
    parser.add_argument("--max-convs", type=int, default=None, help="Optional limit on conversations to scan.")
    parser.add_argument("--summary", action="store_true", help="Print summary of generated dataset.")
    args = parser.parse_args()

    brain_path = Path(args.brain_dir)
    out_dir = Path(args.output_dir)

    transcript_samples = harvest_transcripts(brain_path, max_conversations=args.max_convs)
    checkpoint_samples = harvest_checkpoints(CHECKPOINTS_DIR, TASKS_DIR)
    all_samples = transcript_samples + checkpoint_samples

    if not all_samples:
        logger.error("No valid samples harvested!")
        return 1

    train_n, eval_n = export_dataset(all_samples, out_dir, eval_split_ratio=args.eval_ratio)
    print(f"\n[SUCCESS] Successfully harvested {train_n + eval_n} total samples ({train_n} train, {eval_n} eval).")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
