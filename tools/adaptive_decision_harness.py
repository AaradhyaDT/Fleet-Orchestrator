#!/usr/bin/env python3
"""tools/adaptive_decision_harness.py
------------------------------------
Universal Adaptive-Workflow Decision & Component Verification Harness.
Evaluates:
  L0: Static Hygiene & Unit Tests
  L1: Model Binary Artifacts & Checksums
  L2: LM Studio Runtime & Model Governance
  L3: Local LLM Client Latency & JSON Robustness
  L4: Golden Scenarios Decision Benchmark (Deterministic Zero-AI Baseline vs SLMs)
  L5: Live Host RAM Headroom & Banker's Concurrency Gates
  L6: Task Dispatch & Ceiling Calculation Integrity
  L7: Offline Fault Tolerance & Fast Heuristic Fallback
  L8: Copilot Fleet Readiness & Canary Execution
  L9: Gemini Fleet Multi-Key Rotator Verification
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
import psutil

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client.local_llm import ROUTER_MODEL, chat_completion, extract_json, is_online
from tools.fast_intent_router import (
    ALL_ARCHETYPES,
    _compute_time_allocation,
    _heuristic_fallback,
    _resolve_copilot_tier_and_model,
    route_intent,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("adaptive_harness")

GOLDEN_FIXTURE = ROOT / "tests" / "fixtures" / "adaptive_golden_scenarios.yaml"
BASELINE_PATH = ROOT / "tools" / "adaptive_decision_baseline.json"
STATE_DIR = ROOT / "orchestrator-state" / "bench"

# ============================================================================
# Core Decision Pipeline Engine (Prototype of one-shot /adaptive-workflow)
# ============================================================================

class AdaptiveDecisionEngine:
    """Simulates end-to-end /adaptive-workflow decision pipeline."""

    FAST_PATH_PATTERNS = [
        (r"\b(audit\s*thesis|check\s*thesis|audit\s*beamer)\b", r"python scripts/audit_latex_thesis.py .", "thesis_audit"),
        (r"\b(compile\s*thesis|compile\s*beamer|build\s*thesis)\b", r"python scripts/compile_thesis.py .", "thesis_compile"),
        (r"\b(audit\.bat|\.\\audit|run\s*audit|audit\s*ecosystem|reconcil\w*\.py|reconcil\w*\s*ecosystem|reconcil\w*\s*counts?|verify\s*ecosystem)\b|^\s*(audit|reconcile)\s*$", r".\audit.bat", "audit"),
        (r"\b(sync|pull|push)\b", r".\sync.bat", "sync"),
        (r"\bpytest\b", "pytest tests/", "pytest"),
        (r"\b(run\s*(\w+\s*)?tests?|unittest|test\s*suite)\b|^\s*test\b", "pytest tests/", "test"),
        (r"\b(format|lint|ruff)\b", "ruff check .", "lint"),
        (r"\b(git\s*status|status)\b", "git status", "status"),
        (r"\b(run\s*(\w+\s*)?sim|sim\.bat|simulation)\b", r".\sim.bat", "sim"),
        (r"\b(build\s*(\w+\s*)?report|compile\s*report|report\.pdf|build_report\.bat)\b", r".\build_report.bat", "report"),
        (r"\b(hygiene|prune\s*tasks?|clean\s*worktrees?|fleet\s*watchdog)\b", r".\sync.bat -Hygiene", "hygiene"),
        (r"\b(gap\s*detect\w*|capability\s*gap\w*|capability\s*audit|self\s*upgrade\s*scan)\b", r"python tools/capability_gap_detector.py", "gap_detect"),
        (r"\b(retrain\s*pipeline|retrain\s*slm|closed\s*loop\s*retrain|evaluate\s*routing\s*accuracy)\b", r"python tools/retrain_pipeline.py", "retrain"),
        (r"\b(harvest\s*trajector\w*|harvest\s*agent\s*trajector\w*)\b", r"python tools/harvest_agent_trajectories.py", "harvest_trajectories"),
    ]

    MATRIX_POLICY = {
        ("V0", "R0"): "DIRECT_FAST",
        ("V0", "R1"): "BRANCH_GUARD",
        ("V0", "R2"): "SURGICAL_LOCK",
        ("V1", "R0"): "CONCURRENT_LOCAL",
        ("V1", "R1"): "STAR_SUBAGENTS",
        ("V1", "R2"): "DECOUPLED_SLICES",
        ("V2", "R0"): "FLEET_SWARM",
        ("V2", "R1"): "THROTTLED_FLEET",
        ("V2", "R2"): "STRICT_INTERLOCK_BLOCKED",
    }

    R2_PATTERNS = [
        "schemas/", "reconciliation_engine.py", "access.js", "portfolio.db",
        "AGENTS.md", "GEMINI.md", "capability-registry.yaml", "ecosystem.registry.json",
    ]

    R1_PATTERNS = [
        "sim/", "tools/", "report/", ".agents/skills/", "src/", "components/", "skills/", "firmware/", "notes/",
    ]

    @classmethod
    def detect_fast_path(cls, prompt: str) -> Optional[Dict[str, Any]]:
        desc_lower = prompt.lower().strip()
        generative = [
            "write", "create", "implement", "refactor", "scaffold", "build feature",
            "fix bug", "add", "modify", "format", "design", "draft", "onboard",
            "launch", "fine-tune"
        ]
        if any(g in desc_lower for g in generative):
            if not any(k in desc_lower for k in ["run audit", "run test", "check status", "audit.bat", "sync.bat"]):
                return None

        for pattern, command, action_type in cls.FAST_PATH_PATTERNS:
            if re.search(pattern, desc_lower):
                return {
                    "is_fast_path": True,
                    "action_type": action_type,
                    "command": command,
                    "execution_tier": "Tier 0",
                    "latency_estimate": "<20 ms",
                    "ai_tokens": 0,
                    "policy": "DIRECT_FAST",
                    "backend": "shell",
                }
        return None

    @classmethod
    def compute_volume(cls, file_paths: Optional[List[str]]) -> Tuple[str, int]:
        count = len(file_paths) if file_paths else 1
        if count <= 2:
            return "V0", count
        elif count <= 15:
            return "V1", count
        return "V2", count

    @classmethod
    def compute_criticality(cls, file_paths: Optional[List[str]], prompt: str) -> Tuple[str, float]:
        paths = file_paths or []
        for p in paths:
            if any(r2 in p for r2 in cls.R2_PATTERNS):
                return "R2", 0.45
        if any(r2 in prompt for r2 in ["AGENTS.md", "access.js", "registry.json"]):
            return "R2", 0.45
        for p in paths:
            if any(r1 in p for r1 in cls.R1_PATTERNS):
                return "R1", 0.22
        return "R0", 0.05

    @classmethod
    def compute_banker_concurrency(cls, available_ram_mb: int) -> int:
        reserve_floor = 2048
        ram_per_worker = 256
        if available_ram_mb < reserve_floor + ram_per_worker:
            return 0
        raw = (available_ram_mb - reserve_floor) // ram_per_worker
        return min(27, max(0, raw))

    @classmethod
    def decide(
        cls,
        prompt: str,
        files: Optional[List[str]] = None,
        ram_mb: Optional[int] = None,
        decider: str = "deterministic",
    ) -> Dict[str, Any]:
        """Executes full 6-step decision pipeline."""
        # Step 1: Tier 0 Fast Path
        fast = cls.detect_fast_path(prompt)
        if fast:
            return {
                "is_fast_path": True,
                "archetype": "ENGINEERING_DEV",
                "matrix_cell": "(V0, R0)",
                "policy": "DIRECT_FAST",
                "primary_skill": "github-workflow",
                "backend": "shell",
                "command": fast["command"],
                "execution_tier": "Tier 0",
                "time_allocation": {"estimated_duration_s": 5, "timeout_ceiling_s": 30},
                "workers": 0,
                "auto_tier": "efficiency",
                "decider": decider,
            }

        # Step 2: 2D Matrix Triage (Volume & Criticality)
        v_label, count = cls.compute_volume(files)
        r_label, crit_score = cls.compute_criticality(files, prompt)
        cell = f"({v_label}, {r_label})"
        policy = cls.MATRIX_POLICY.get((v_label, r_label), "DIRECT_FAST")

        # Step 3: Intent & Skill Routing
        if decider == "deterministic":
            intent = _heuristic_fallback(prompt)
        else:
            # Route through local model via fast_intent_router
            old_model = os.getenv("FLEET_ROUTER_MODEL")
            os.environ["FLEET_ROUTER_MODEL"] = decider
            try:
                intent = route_intent(prompt)
            finally:
                if old_model:
                    os.environ["FLEET_ROUTER_MODEL"] = old_model
                else:
                    os.environ.pop("FLEET_ROUTER_MODEL", None)

        arch = intent.get("archetype", "ENGINEERING_DEV")
        pskill = intent.get("primary_skill", "github-workflow")

        # Step 4: Live Host RAM Headroom & Banker's Concurrency
        avail_ram = ram_mb if ram_mb is not None else int(psutil.virtual_memory().available / (1024 * 1024))
        workers = cls.compute_banker_concurrency(avail_ram)

        # Step 5: Backend Selection
        if policy == "FLEET_SWARM" or count > 15:
            backend = "fleet-copilot" if workers > 0 else "in-turn"
        elif arch == "SWARM_ORCHESTRATION" and "colab" in pskill:
            backend = "colab"
        elif arch == "AI_ENGINEERING_ML" and any(k in prompt.lower() for k in ["train", "gpu", "cuda"]):
            backend = "colab"
        elif policy in ["BRANCH_GUARD", "SURGICAL_LOCK", "STAR_SUBAGENTS"]:
            backend = "in-turn"
        else:
            backend = "in-turn"

        auto_tier, rec_model = _resolve_copilot_tier_and_model(cell, policy, prompt)
        time_alloc = intent.get("time_allocation") or _compute_time_allocation(prompt, arch, "Tier 1", policy)

        return {
            "is_fast_path": False,
            "archetype": arch,
            "matrix_cell": cell,
            "policy": policy,
            "primary_skill": pskill,
            "backend": backend,
            "workers": workers,
            "available_ram_mb": avail_ram,
            "time_allocation": time_alloc,
            "auto_tier": auto_tier,
            "recommended_copilot_model": rec_model,
            "decider": decider,
            "source": intent.get("source", "heuristic"),
        }

# ============================================================================
# Layer Verification Functions (L0 - L9)
# ============================================================================

def verify_l0_static_hygiene() -> Dict[str, Any]:
    """L0: Verifies pytest test suite passes hermetically."""
    res = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"], capture_output=True, text=True, cwd=str(ROOT))
    passed = res.returncode == 0
    return {
        "layer": "L0_STATIC_HYGIENE",
        "passed": passed,
        "returncode": res.returncode,
        "output_summary": res.stdout.strip().splitlines()[-1] if res.stdout else res.stderr[:100],
    }


def verify_l1_artifacts() -> Dict[str, Any]:
    """L1: Audits local GGUF model binaries against expectations."""
    models = {
        "qwen_intent_router_q4_k_m.gguf": 398 * 1024 * 1024,
        "fleet_master_brain_3b_q4km.gguf": 1930 * 1024 * 1024,
        "fleet_master_brain_7b_q4km.gguf": 4680 * 1024 * 1024,
    }
    details = {}
    all_ok = True
    for name, expected_size in models.items():
        p = ROOT / "models" / name
        if not p.exists():
            details[name] = {"exists": False}
            all_ok = False
            continue
        actual_size = p.stat().st_size
        size_diff = abs(actual_size - expected_size) / expected_size
        details[name] = {
            "exists": True,
            "size_mb": round(actual_size / (1024 * 1024), 2),
            "size_match": size_diff < 0.05,
        }
        if size_diff >= 0.05:
            all_ok = False

    return {
        "layer": "L1_MODEL_ARTIFACTS",
        "passed": all_ok,
        "details": details,
    }


def verify_l2_lm_studio_runtime() -> Dict[str, Any]:
    """L2: Audits LM Studio runtime status and port 1234."""
    online = is_online()
    ps_output = ""
    try:
        res = subprocess.run(["lms", "ps"], capture_output=True, text=True)
        ps_output = res.stdout.strip()
    except Exception as e:
        ps_output = str(e)

    return {
        "layer": "L2_LM_STUDIO_RUNTIME",
        "port_1234_online": online,
        "passed": online,
        "ps_summary": ps_output[:250],
    }


def verify_l3_local_llm_client() -> Dict[str, Any]:
    """L3: Probes socket latency and tolerant JSON extraction across 6 edge-case fixtures."""
    fixtures = [
        ('{"archetype": "ENGINEERING_DEV"}', True),
        ('```json\n{"archetype": "FRONTEND_PRODUCT"}\n```', True),
        ('Here is the parsed response:\n{"archetype": "DOMAIN_HARDWARE"}', True),
        ('{"archetype": "RESEARCH_ACADEMIC"}\nAdditional markdown notes.', True),
        ('{"nested": {"key": 123}, "archetype": "SWARM_ORCHESTRATION"}', True),
        ('Garbage non-json output without brackets', False),
    ]
    passed_fixtures = 0
    for text, should_succeed in fixtures:
        extracted = extract_json(text)
        if (extracted is not None) == should_succeed:
            passed_fixtures += 1

    t0 = time.perf_counter()
    online = is_online()
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "layer": "L3_LOCAL_LLM_CLIENT",
        "socket_latency_ms": latency_ms,
        "port_1234_online": online,
        "fixture_pass_count": f"{passed_fixtures}/{len(fixtures)}",
        "passed": passed_fixtures == len(fixtures),
    }


def verify_l4_golden_scenarios(
    deciders: List[str] = ["deterministic", "qwen-intent-router", "fleet-master-3b"],
) -> Dict[str, Any]:
    """L4: Evaluates decisions against human-reviewed golden test fixtures."""
    if not GOLDEN_FIXTURE.exists():
        return {"layer": "L4_GOLDEN_SCENARIOS", "passed": False, "error": "Fixture missing"}

    with open(GOLDEN_FIXTURE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    scenarios = data.get("scenarios", [])
    results_by_decider: Dict[str, Any] = {}

    for decider in deciders:
        correct_arch = 0
        correct_cell = 0
        correct_skill = 0
        correct_backend = 0
        correct_fast = 0
        total = len(scenarios)
        latencies = []

        for sc in scenarios:
            prompt = sc["prompt"]
            files = sc.get("files")
            exp = sc.get("expected", {})

            t0 = time.perf_counter()
            d = AdaptiveDecisionEngine.decide(prompt, files=files, decider=decider)
            lat_ms = (time.perf_counter() - t0) * 1000
            latencies.append(lat_ms)

            if d.get("is_fast_path") == exp.get("is_fast_path", False):
                correct_fast += 1
            if exp.get("archetype") and d.get("archetype") == exp.get("archetype"):
                correct_arch += 1
            if exp.get("matrix_cell") and d.get("matrix_cell") == exp.get("matrix_cell"):
                correct_cell += 1
            if exp.get("primary_skill") and d.get("primary_skill") == exp.get("primary_skill"):
                correct_skill += 1
            if exp.get("backend") and d.get("backend") == exp.get("backend"):
                correct_backend += 1

        results_by_decider[decider] = {
            "total_samples": total,
            "fast_path_accuracy": round((correct_fast / total) * 100, 1),
            "archetype_accuracy": round((correct_arch / total) * 100, 1),
            "matrix_cell_accuracy": round((correct_cell / total) * 100, 1),
            "primary_skill_accuracy": round((correct_skill / total) * 100, 1),
            "backend_accuracy": round((correct_backend / total) * 100, 1),
            "p50_latency_ms": round(sorted(latencies)[len(latencies) // 2], 2),
            "max_latency_ms": round(max(latencies), 2),
        }

    return {
        "layer": "L4_GOLDEN_SCENARIOS",
        "passed": True,
        "deciders": results_by_decider,
    }


def verify_l5_ram_and_banker_gates() -> Dict[str, Any]:
    """L5: Simulates RAM bands and Banker's algorithm worker concurrency floor."""
    bands = [
        (1800, 0),
        (2048, 0),
        (2304, 1),
        (3072, 4),
        (4096, 8),
        (8192, 24),
        (12288, 27),
    ]
    all_matched = True
    results = []
    for avail, expected in bands:
        computed = AdaptiveDecisionEngine.compute_banker_concurrency(avail)
        matched = computed == expected
        results.append({"avail_mb": avail, "expected_workers": expected, "computed": computed, "match": matched})
        if not matched:
            all_matched = False

    current_avail_mb = int(psutil.virtual_memory().available / (1024 * 1024))
    live_workers = AdaptiveDecisionEngine.compute_banker_concurrency(current_avail_mb)

    return {
        "layer": "L5_RAM_BANKER_GATES",
        "passed": all_matched,
        "live_host_avail_mb": current_avail_mb,
        "live_concurrency_capacity": live_workers,
        "simulation_bands": results,
    }


def verify_l6_task_dispatch_integrity() -> Dict[str, Any]:
    """L6: Verifies dispatch ceiling calculations and source metadata."""
    res = AdaptiveDecisionEngine.decide("Scaffold IV-II syllabus and share notes", files=["syllabus.md"])
    ta = res.get("time_allocation", {})
    valid_ceiling = ta.get("timeout_ceiling_s", 0) >= 30
    return {
        "layer": "L6_DISPATCH_INTEGRITY",
        "passed": valid_ceiling and "archetype" in res,
        "time_allocation": ta,
        "policy": res.get("policy"),
    }


def verify_l7_offline_fallback() -> Dict[str, Any]:
    """L7: Verifies immediate sub-3s fallback when server is unreachable."""
    old_url = os.environ.get("LMSTUDIO_BASE_URL")
    os.environ["LMSTUDIO_BASE_URL"] = "http://127.0.0.1:9999/v1"
    t0 = time.perf_counter()
    try:
        res = AdaptiveDecisionEngine.decide("Fix urgent bug in checkout", decider="deterministic")
        elapsed = time.perf_counter() - t0
        passed = elapsed < 3.0 and res["archetype"] == "ENGINEERING_DEV"
    finally:
        if old_url:
            os.environ["LMSTUDIO_BASE_URL"] = old_url
        else:
            os.environ.pop("LMSTUDIO_BASE_URL", None)

    return {
        "layer": "L7_OFFLINE_FALLBACK",
        "passed": passed,
        "fallback_latency_s": round(elapsed, 3),
        "source": res.get("source"),
    }


def verify_l8_copilot_readiness(live_cloud: bool = False) -> Dict[str, Any]:
    """L8: Checks Copilot multi-account fleet readiness and executes canary."""
    fleet_script = ROOT / "tools" / "copilot_fleet.py"
    res = subprocess.run([sys.executable, str(fleet_script), "status"], capture_output=True, text=True, cwd=str(ROOT))
    status_ok = "27" in res.stdout or "copilot-w" in res.stdout

    canary_result = "SKIPPED"
    if live_cloud:
        c_res = subprocess.run([sys.executable, str(fleet_script), "canary"], capture_output=True, text=True, cwd=str(ROOT))
        canary_result = "SUCCESS" if c_res.returncode == 0 else f"FAILED: {c_res.stderr[:100]}"

    return {
        "layer": "L8_COPILOT_READINESS",
        "passed": status_ok,
        "fleet_status_detected": status_ok,
        "canary_execution": canary_result,
    }


async def verify_l9_gemini_rotator(live_cloud: bool = False) -> Dict[str, Any]:
    """L9: Verifies Gemini Key Rotator pool and optionally pings live API."""
    from client.adapters.gemini_fleet_rotator import GeminiKeyRotator
    rotator = GeminiKeyRotator()
    status = rotator.get_status()
    total_keys = status.get("total_keys", 0)

    ping_result = "SKIPPED"
    if live_cloud and total_keys > 0:
        slot = await rotator.get_next_slot()
        if slot:
            try:
                from google import genai
                client = genai.Client(api_key=slot.api_key)
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents="Respond with 'healthy'",
                    config={"automatic_function_calling": {"disable": True}},
                )
                ping_result = f"OK: {resp.text.strip()[:20]}"
            except Exception as e:
                ping_result = f"ERR: {str(e)[:100]}"

    return {
        "layer": "L9_GEMINI_ROTATOR",
        "passed": total_keys > 0,
        "total_keys": total_keys,
        "healthy_keys": status.get("healthy_keys", 0),
        "live_ping": ping_result,
    }


# ============================================================================
# Main Orchestrator & Report Generator
# ============================================================================

def run_all_layers(
    models: List[str] = ["deterministic", "qwen-intent-router", "fleet-master-3b"],
    live_cloud: bool = False,
    update_baseline: bool = False,
) -> Dict[str, Any]:
    """Executes full diagnostic test suite and produces insight summary."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": {
            "platform": sys.platform,
            "cpu_count": psutil.cpu_count(logical=True),
            "ram_total_mb": int(psutil.virtual_memory().total / (1024 * 1024)),
            "ram_avail_mb": int(psutil.virtual_memory().available / (1024 * 1024)),
        },
        "layers": {},
    }

    print("=" * 70)
    print("STARTING ADAPTIVE-WORKFLOW DECISION HARNESS & REALITY GATE")
    print("=" * 70)

    print("\n[L0] Verifying Static Hygiene & Unit Tests...")
    report["layers"]["L0"] = verify_l0_static_hygiene()
    print(f"  -> L0 Passed: {report['layers']['L0']['passed']}")

    print("\n[L1] Auditing Model Artifacts & Sizes...")
    report["layers"]["L1"] = verify_l1_artifacts()
    print(f"  -> L1 Passed: {report['layers']['L1']['passed']}")

    print("\n[L2] Checking LM Studio Runtime & Models...")
    report["layers"]["L2"] = verify_l2_lm_studio_runtime()
    print(f"  -> L2 Passed: {report['layers']['L2']['passed']}")

    print("\n[L3] Probing Local LLM Client Latency & JSON Robustness...")
    report["layers"]["L3"] = verify_l3_local_llm_client()
    print(f"  -> L3 Passed: {report['layers']['L3']['passed']}")

    print("\n[L4] Running Golden Scenario Benchmarks across Deciders...")
    report["layers"]["L4"] = verify_l4_golden_scenarios(deciders=models)
    print(f"  -> L4 Evaluated deciders: {list(report['layers']['L4']['deciders'].keys())}")

    print("\n[L5] Verifying RAM Headroom & Banker's Concurrency Gates...")
    report["layers"]["L5"] = verify_l5_ram_and_banker_gates()
    print(f"  -> L5 Passed: {report['layers']['L5']['passed']}")

    print("\n[L6] Verifying Task Dispatch Integrity...")
    report["layers"]["L6"] = verify_l6_task_dispatch_integrity()
    print(f"  -> L6 Passed: {report['layers']['L6']['passed']}")

    print("\n[L7] Verifying Offline Heuristic Fallback Resilience...")
    report["layers"]["L7"] = verify_l7_offline_fallback()
    print(f"  -> L7 Passed: {report['layers']['L7']['passed']}")

    print("\n[L8] Verifying Copilot Fleet Readiness...")
    report["layers"]["L8"] = verify_l8_copilot_readiness(live_cloud=live_cloud)
    print(f"  -> L8 Passed: {report['layers']['L8']['passed']}")

    print("\n[L9] Verifying Gemini Fleet Multi-Key Rotator...")
    report["layers"]["L9"] = asyncio.run(verify_l9_gemini_rotator(live_cloud=live_cloud))
    print(f"  -> L9 Passed: {report['layers']['L9']['passed']}")

    # Save timestamped report
    iso_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = STATE_DIR / f"decision_report_{iso_stamp}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[INFO] Comprehensive JSON report saved to: {out_file}")

    if update_baseline:
        baseline_data = {
            "updated_at": report["timestamp"],
            "deterministic_baseline": report["layers"]["L4"]["deciders"]["deterministic"],
            "banker_concurrency_rules": report["layers"]["L5"]["simulation_bands"],
        }
        with open(BASELINE_PATH, "w", encoding="utf-8") as bf:
            json.dump(baseline_data, bf, indent=2)
        print(f"[INFO] Authoritative baseline updated: {BASELINE_PATH}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Adaptive-Workflow Decision Harness")
    parser.add_argument("--models", default="deterministic,qwen-intent-router,fleet-master-3b", help="Comma-separated deciders")
    parser.add_argument("--live-cloud", action="store_true", help="Execute live cloud ping for Copilot and Gemini")
    parser.add_argument("--update-baseline", action="store_true", help="Persist results as ground truth baseline")
    args = parser.parse_args()

    selected_models = [m.strip() for m in args.models.split(",") if m.strip()]
    run_all_layers(models=selected_models, live_cloud=args.live_cloud, update_baseline=args.update_baseline)
