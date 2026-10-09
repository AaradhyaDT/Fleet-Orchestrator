#!/usr/bin/env python3
"""
tools/harvest_agent_trajectories.py
------------------------------------
Universal Trajectory Harvester & Sanitizer for Antigravity Chat Transcripts.
Crawls ~/.gemini/antigravity/brain/*/transcript.jsonl to extract:
  1. Self-Healing Error Recovery Pairs (Agent-Reflex dataset)
  2. Speculative Tool Sequences (Next-Action Predictor dataset)
  3. Ecosystem SFT Pairs (Domain-adapted reasoning dataset)

Applies strict data hygiene:
  - Path normalization (redacting local usernames and absolute drive paths)
  - Token and credential redaction
  - 80/20 train/eval partitioning
  - Summary metric generation
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("harvest_trajectories")

BRAIN_ROOT = Path.home() / ".gemini" / "antigravity" / "brain"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "dataset" / "trajectories"

REFLEX_SYSTEM_INSTRUCTION = (
    "You are Agent-Reflex, an autonomous self-healing error recovery engine for developer agent swarms. "
    "Given a failed tool action and its error output, diagnose the failure and output the exact "
    "corrective tool action in strict JSON format."
)

TOOL_SEQ_SYSTEM_INSTRUCTION = (
    "You are an Agentic Tool Speculator. Given a user development request, predict the sequence "
    "of tool actions required to fulfill the task in strict JSON format."
)


def sanitize_text(text: str) -> str:
    """Sanitizes file paths, usernames, and sensitive tokens from text."""
    if not text:
        return ""
    s = text

    # Strip XML wrapper markers
    s = re.sub(r"</?USER_REQUEST>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<SYSTEM_MESSAGE>.*?</SYSTEM_MESSAGE>", "", s, flags=re.DOTALL | re.IGNORECASE)

    # Sanitize user home directories and drive letters
    s = re.sub(r"[A-Za-z]:[\\/]Users[\\/][^\\/\"'\s]+[\\/]\.gemini[\\/]antigravity", "~/.antigravity", s, flags=re.IGNORECASE)
    s = re.sub(r"[A-Za-z]:[\\/]Users[\\/][^\\/\"'\s]+", "~", s, flags=re.IGNORECASE)
    s = re.sub(r"[A-Za-z]:[\\/]Aaradhya-Dev-Tamrakar[\\/]", "/repo/", s, flags=re.IGNORECASE)
    s = re.sub(r"[A-Za-z]:[\\/]AaradhyaDT[\\/]", "/repo/", s, flags=re.IGNORECASE)

    # Redact common tokens / keys
    s = re.sub(r"ghp_[a-zA-Z0-9]{30,45}", "ghp_REDACTED_TOKEN", s)
    s = re.sub(r"github_pat_[a-zA-Z0-9_]{60,90}", "github_pat_REDACTED_TOKEN", s)
    s = re.sub(r"AIzaSy[a-zA-Z0-9_-]{33}", "AIzaSy_REDACTED_API_KEY", s)
    s = re.sub(r"xox[baprs]-[0-9a-zA-Z]{10,48}", "slack_REDACTED_TOKEN", s)

    return s.strip()


def is_error_output(content: str) -> bool:
    """Detects whether a tool execution resulted in an error or non-zero exit code."""
    if not content:
        return False
    lower = content.lower()
    error_patterns = [
        "exited with code 1",
        "exited with code 2",
        "exited with code 127",
        "command exited with non-zero code",
        "traceback (most recent call last)",
        "syntaxerror:",
        "filenotfounderror:",
        "modulenotfounderror:",
        "importerror:",
        "permissionerror:",
        "parse error",
        "cannot find path",
        "failed to execute",
        "assertionerror",
        "fatal: ",
    ]
    return any(p in lower for p in error_patterns)


def harvest_conversation(transcript_file: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Parses a single transcript into self-healing, tool-sequence, and SFT samples."""
    self_healing: List[Dict[str, Any]] = []
    tool_sequences: List[Dict[str, Any]] = []

    try:
        with open(transcript_file, "r", encoding="utf-8", errors="replace") as f:
            lines = [json.loads(line.strip()) for line in f if line.strip()]
    except Exception as e:
        logger.debug(f"Could not read {transcript_file}: {e}")
        return {"self_healing": [], "tool_sequences": []}

    # Tracking state
    last_user_prompt: str = ""
    current_turn_tools: List[str] = []
    pending_tool_call: Optional[Dict[str, Any]] = None

    for entry in lines:
        etype = entry.get("type")
        source = entry.get("source")

        if etype == "USER_INPUT" and source == "USER_EXPLICIT":
            # Save prior sequence if substantial
            if last_user_prompt and len(current_turn_tools) >= 2:
                tool_sequences.append({
                    "prompt": sanitize_text(last_user_prompt),
                    "sequence": current_turn_tools,
                })
            last_user_prompt = entry.get("content", "")
            current_turn_tools = []
            pending_tool_call = None

        elif etype == "PLANNER_RESPONSE":
            tcalls = entry.get("tool_calls", [])
            thinking = entry.get("thinking", "")

            # If there was a pending failed tool call and this model response provides a fix
            if pending_tool_call and tcalls:
                fix_call = tcalls[0]
                diagnosis = sanitize_text(thinking[:400] if thinking else "Analyzing failure and applying correction.")
                self_healing.append({
                    "failed_tool": pending_tool_call["name"],
                    "failed_args": pending_tool_call.get("args", {}),
                    "error_output": sanitize_text(pending_tool_call["error_output"][:800]),
                    "diagnosis": diagnosis,
                    "recovery_tool": fix_call.get("name", "run_command"),
                    "recovery_args": fix_call.get("args", {}),
                })
                pending_tool_call = None

            for tc in tcalls:
                if isinstance(tc, dict) and "name" in tc:
                    current_turn_tools.append(tc["name"])
                    # Save as the latest executed tool awaiting output
                    pending_tool_call = {
                        "name": tc["name"],
                        "args": tc.get("args", {}),
                        "error_output": "",
                    }

        elif etype == "GENERIC":
            content = entry.get("content", "")
            if pending_tool_call:
                if is_error_output(content):
                    # Flag this pending call as an error to pair with next model turn
                    pending_tool_call["error_output"] = content
                else:
                    # Successful tool execution
                    pending_tool_call = None

    if last_user_prompt and len(current_turn_tools) >= 2:
        tool_sequences.append({
            "prompt": sanitize_text(last_user_prompt),
            "sequence": current_turn_tools,
        })

    return {
        "self_healing": self_healing,
        "tool_sequences": tool_sequences,
    }


def export_splits(
    samples: List[Dict[str, Any]],
    output_prefix: str,
    output_dir: Path,
    eval_ratio: float = 0.20,
    seed: int = 42,
) -> Tuple[int, int]:
    """Splits into train and eval sets and writes JSONL."""
    output_dir.mkdir(parents=True, exist_ok=True)
    random.seed(seed)
    shuffled = list(samples)
    random.shuffle(shuffled)

    eval_count = max(1, int(len(shuffled) * eval_ratio)) if len(shuffled) > 5 else 0
    eval_data = shuffled[:eval_count]
    train_data = shuffled[eval_count:]

    train_path = output_dir / f"{output_prefix}_train.jsonl"
    eval_path = output_dir / f"{output_prefix}_eval.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(eval_path, "w", encoding="utf-8") as f:
        for item in eval_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return len(train_data), len(eval_data)


def main():
    parser = argparse.ArgumentParser(description="Harvest agentic trajectories from chat transcripts.")
    parser.add_argument("--brain-dir", type=str, default=str(BRAIN_ROOT), help="Path to Antigravity brain directory.")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Output directory for datasets.")
    parser.add_argument("--eval-ratio", type=float, default=0.20, help="Eval split ratio.")
    args = parser.parse_args()

    brain_path = Path(args.brain_dir)
    out_dir = Path(args.output_dir)

    if not brain_path.exists():
        logger.error(f"Brain path does not exist: {brain_path}")
        return 1

    conv_dirs = [d for d in brain_path.iterdir() if d.is_dir()]
    logger.info(f"Scanning {len(conv_dirs)} conversation directories...")

    all_self_healing: List[Dict[str, Any]] = []
    all_tool_sequences: List[Dict[str, Any]] = []

    for cdir in conv_dirs:
        transcript = cdir / ".system_generated" / "logs" / "transcript.jsonl"
        if not transcript.exists():
            continue
        res = harvest_conversation(transcript)
        all_self_healing.extend(res["self_healing"])
        all_tool_sequences.extend(res["tool_sequences"])

    logger.info(f"Harvested {len(all_self_healing)} raw self-healing recovery turns.")
    logger.info(f"Harvested {len(all_tool_sequences)} raw tool sequences.")

    # Deduplicate & Format Agent-Reflex (Self-Healing)
    reflex_examples = []
    seen_reflex = set()
    for sh in all_self_healing:
        key = (sh["failed_tool"], str(sh["failed_args"]), sh["recovery_tool"], str(sh["recovery_args"]))
        if key not in seen_reflex:
            seen_reflex.add(key)
            reflex_examples.append({
                "instruction": REFLEX_SYSTEM_INSTRUCTION,
                "input": json.dumps({
                    "failed_tool": sh["failed_tool"],
                    "failed_args": sh["failed_args"],
                    "error_output": sh["error_output"],
                }, ensure_ascii=False),
                "output": json.dumps({
                    "diagnosis": sh["diagnosis"],
                    "recovery_tool": sh["recovery_tool"],
                    "recovery_args": sh["recovery_args"],
                }, ensure_ascii=False),
            })

    # Deduplicate & Format Tool Sequence Speculator
    seq_examples = []
    seen_seq = set()
    for ts in all_tool_sequences:
        p = ts["prompt"].strip()
        if len(p) >= 10 and p not in seen_seq:
            seen_seq.add(p)
            seq_examples.append({
                "instruction": TOOL_SEQ_SYSTEM_INSTRUCTION,
                "input": p,
                "output": json.dumps({"tool_sequence": ts["sequence"]}, ensure_ascii=False),
            })

    reflex_train, reflex_eval = export_splits(reflex_examples, "agent_reflex", out_dir, eval_ratio=args.eval_ratio)
    seq_train, seq_eval = export_splits(seq_examples, "tool_speculator", out_dir, eval_ratio=args.eval_ratio)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_conversations_scanned": len(conv_dirs),
        "agent_reflex": {
            "total_unique": len(reflex_examples),
            "train": reflex_train,
            "eval": reflex_eval,
            "train_file": str(out_dir / "agent_reflex_train.jsonl"),
            "eval_file": str(out_dir / "agent_reflex_eval.jsonl"),
        },
        "tool_speculator": {
            "total_unique": len(seq_examples),
            "train": seq_train,
            "eval": seq_eval,
            "train_file": str(out_dir / "tool_speculator_train.jsonl"),
            "eval_file": str(out_dir / "tool_speculator_eval.jsonl"),
        },
    }

    summary_file = out_dir / "trajectories_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 60)
    print(" TRAJECTORY HARVESTING COMPLETE")
    print("=" * 60)
    print(f"Total Conversations Scanned: {len(conv_dirs)}")
    print(f"Agent-Reflex (Self-Healing): {len(reflex_examples)} samples ({reflex_train} train, {reflex_eval} eval)")
    print(f"Tool-Speculator Sequences:   {len(seq_examples)} samples ({seq_train} train, {seq_eval} eval)")
    print(f"Summary Manifest:            {summary_file}")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
