#!/usr/bin/env python3
r"""tools/probe_environment.py
----------------------------
Deterministic Live Environment Probe for Adaptive-Workflow & Fleet-Orchestrator.

Probes live host telemetry, local LM Studio, configured fleet accounts, CLI tooling,
and skills registry availability. Emits an auditable snapshot:
    tools/environment_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("probe_environment")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "tools" / "environment_snapshot.json"
REGISTRY_FILE = ROOT / "tools" / "skills_registry.json"


def probe_host_telemetry() -> Dict[str, Any]:
    """Captures CPU and RAM metrics with Banker's concurrency slot calculation."""
    res: Dict[str, Any] = {
        "cpu_count": os.cpu_count() or 4,
        "total_ram_mb": 0,
        "free_ram_mb": 0,
        "banker_reserve_floor_mb": 2048,
        "safe_worker_slots": 0,
    }
    try:
        import psutil
        vm = psutil.virtual_memory()
        total_mb = int(vm.total / (1024 * 1024))
        free_mb = int(vm.available / (1024 * 1024))
        res["total_ram_mb"] = total_mb
        res["free_ram_mb"] = free_mb
        # Concurrency formula: floor((Free RAM - 2048) / 256) capped at 27
        slots = max(0, (free_mb - 2048) // 256)
        res["safe_worker_slots"] = min(27, slots)
    except Exception as e:
        logger.debug(f"psutil probe failed: {e}")
    return res


def probe_lm_studio(endpoint: str = "http://127.0.0.1:1234/v1/models") -> Dict[str, Any]:
    """Probes local LM Studio instance with a strict 500ms timeout."""
    status = {
        "endpoint": endpoint,
        "online": False,
        "loaded_models": [],
        "latency_ms": None,
    }
    try:
        t0 = time.perf_counter()
        req = urllib.request.Request(endpoint, headers={"User-Agent": "FleetProbe/1.0"})
        with urllib.request.urlopen(req, timeout=0.6) as resp:
            elapsed = (time.perf_counter() - t0) * 1000
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id") for m in data.get("data", []) if m.get("id")]
            status["online"] = True
            status["loaded_models"] = models
            status["latency_ms"] = round(elapsed, 1)
    except Exception:
        pass
    return status


def probe_fleet_accounts() -> Dict[str, Any]:
    """Safely audits configured account pools without logging raw secrets."""
    counts = {
        "copilot_accounts": 0,
        "gemini_api_keys": 0,
        "agy_workers": 0,
    }
    try:
        from tools.fleet_env import load_all_fleet_env
        fleet_data = load_all_fleet_env(repo_root=ROOT, inject_os_environ=False)
        copilot_vars = fleet_data.get("copilot", {})
        gemini_vars = fleet_data.get("gemini", {})
        agy_vars = fleet_data.get("agy", {})

        # Count COPILOT_TOKEN_* keys
        c_tokens = sum(1 for k in copilot_vars if k.startswith("COPILOT_") and "TOKEN" in k)
        g_keys = sum(1 for k in gemini_vars if "GEMINI" in k and "KEY" in k)
        a_workers = sum(1 for k in agy_vars if "AGY" in k or "WORKER" in k)

        counts["copilot_accounts"] = c_tokens
        counts["gemini_api_keys"] = g_keys
        counts["agy_workers"] = a_workers
    except Exception as e:
        logger.debug(f"Fleet account probe failed: {e}")
    return counts


def probe_cli_tooling() -> Dict[str, bool]:
    """Checks presence of key CLI executables in PATH."""
    binaries = [
        "git",
        "python",
        "pwsh",
        "colab",
        "copilot",
        "graphify",
        "ruff",
        "pytest",
    ]
    return {b: shutil.which(b) is not None for b in binaries}


def probe_skills_registry() -> Dict[str, Any]:
    """Checks freshness and metrics of skills_registry.json."""
    if not REGISTRY_FILE.exists():
        return {"present": False, "distinct_skills": 0}
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "present": True,
            "version": data.get("version"),
            "distinct_skills": data.get("total_distinct_skills", 0),
            "tier_counts": data.get("tier_counts", {}),
        }
    except Exception:
        return {"present": False, "distinct_skills": 0}


def capture_environment_snapshot() -> Dict[str, Any]:
    """Assembles comprehensive live environment snapshot."""
    snapshot = {
        "timestamp_epoch": time.time(),
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host_telemetry": probe_host_telemetry(),
        "lm_studio": probe_lm_studio(),
        "fleet_pools": probe_fleet_accounts(),
        "cli_binaries": probe_cli_tooling(),
        "skills_registry": probe_skills_registry(),
    }
    return snapshot


def save_environment_snapshot(output_path: Path = OUTPUT_FILE) -> Dict[str, Any]:
    """Saves environment snapshot to JSON file."""
    snap = capture_environment_snapshot()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)
    logger.info(f"Environment snapshot captured and saved to {output_path}")
    return snap


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Environment Probe for Adaptive-Workflow")
    parser.add_argument("--output", "-o", type=Path, default=OUTPUT_FILE, help="Path for output JSON")
    parser.add_argument("--json", action="store_true", help="Print snapshot JSON to stdout")
    args = parser.parse_args()

    snap = save_environment_snapshot(args.output)
    if args.json:
        print(json.dumps(snap, indent=2))
        return 0

    print("=" * 65)
    print("  LIVE ENVIRONMENT SNAPSHOT (INV-ENV-PROBE)")
    print("=" * 65)
    telemetry = snap["host_telemetry"]
    print(f"  CPU Cores       : {telemetry['cpu_count']}")
    print(f"  Host RAM        : {telemetry['free_ram_mb']} MB free / {telemetry['total_ram_mb']} MB total")
    print(f"  Safe Concurrency: {telemetry['safe_worker_slots']} workers")
    lm = snap["lm_studio"]
    print(f"  LM Studio (1234): {'ONLINE' if lm['online'] else 'OFFLINE'}")
    pools = snap["fleet_pools"]
    print(f"  Copilot Accounts: {pools['copilot_accounts']} configured")
    reg = snap["skills_registry"]
    print(f"  Skills Registry : {'READY (' + str(reg['distinct_skills']) + ' skills)' if reg['present'] else 'MISSING'}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
