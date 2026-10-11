#!/usr/bin/env python3
"""tools/bench_local_router.py
----------------------------
Empirical benchmark comparing local router candidates (0.5B vs 3B)
on task classification, JSON adherence, and inference latency.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from client.local_llm import chat_completion, extract_json, is_online
from tools.fast_intent_router import SYSTEM_PROMPT, _compute_time_allocation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bench")

EVAL_DATASET = ROOT / "dataset" / "task_time_eval.jsonl"
OUT_DIR = ROOT / "orchestrator-state" / "bench"


def load_eval_samples(max_samples: int = 30) -> List[Dict[str, Any]]:
    if not EVAL_DATASET.exists():
        logger.error(f"Eval dataset not found at {EVAL_DATASET}")
        return []

    samples = []
    with open(EVAL_DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                user_msg = data.get("input")
                asst_msg = data.get("output")
                if not user_msg:
                    messages = data.get("messages", [])
                    user_msg = next((m["content"] for m in messages if m["role"] == "user"), None)
                    asst_msg = next((m["content"] for m in messages if m["role"] == "assistant"), None)
                if user_msg and asst_msg:
                    samples.append({
                        "prompt": user_msg,
                        "ground_truth_raw": asst_msg,
                        "ground_truth_json": extract_json(asst_msg)
                    })
                if len(samples) >= max_samples:
                    break
            except Exception:
                continue
    return samples


def benchmark_model(model_name: str, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    print(f"\nEvaluating Model: {model_name} on {len(samples)} samples...")
    latencies = []
    json_valid = 0
    archetype_matches = 0

    for idx, sample in enumerate(samples):
        prompt = sample["prompt"]
        gt_json = sample["ground_truth_json"] or {}
        expected_archetype = gt_json.get("archetype")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        t0 = time.perf_counter()
        raw = chat_completion(model=model_name, messages=messages, temperature=0.0, max_tokens=220, timeout=8.0)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(dur_ms)

        parsed = extract_json(raw) if raw else None
        if parsed and isinstance(parsed, dict) and "archetype" in parsed:
            json_valid += 1
            if expected_archetype and parsed.get("archetype") == expected_archetype:
                archetype_matches += 1

    latencies.sort()
    n = len(latencies)
    p50 = latencies[n // 2] if n > 0 else 0
    p95 = latencies[int(n * 0.95)] if n > 0 else 0

    return {
        "model": model_name,
        "sample_count": n,
        "json_valid_count": json_valid,
        "json_valid_pct": round((json_valid / n) * 100.0, 1) if n > 0 else 0,
        "archetype_accuracy_pct": round((archetype_matches / max(1, json_valid)) * 100.0, 1) if json_valid > 0 else 0,
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark Local Router Candidates")
    parser.add_argument("--samples", type=int, default=20, help="Number of eval samples")
    parser.add_argument("--models", default="qwen-intent-router,fleet-master-3b", help="Comma-separated model identifiers")
    args = parser.parse_args()

    if not is_online():
        print("[ERROR] LM Studio server is not online on port 1234. Run `tools/models.bat up` first.")
        sys.exit(1)

    samples = load_eval_samples(args.samples)
    if not samples:
        print("[ERROR] No samples loaded from dataset.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    models_to_test = [m.strip() for m in args.models.split(",") if m.strip()]

    for m in models_to_test:
        res = benchmark_model(m, samples)
        results.append(res)
        print(f"  -> Valid JSON: {res['json_valid_pct']}% | Archetype Acc: {res['archetype_accuracy_pct']}% | p50: {res['latency_p50_ms']}ms | p95: {res['latency_p95_ms']}ms")

    ts = int(time.time())
    out_file = OUT_DIR / f"router_bench_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[REPORT SAVED] {out_file.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()
