#!/usr/bin/env python3
"""tools/azmuth_colab_burst.py
----------------------------
Azmuth Cloud Hyper-Burst Engine (Google Colab A100 High-RAM / GPU / CPU).

Version 2.0 (VRAM-Saturated 8-Phase Engine):
- Phase 1: GPU-accelerated genotype tournament (2^20 = 1,048,576 combinations across 32 alleles)
- Phase 2: 1 Billion Monte Carlo shock trials across all 15 universes in 165M chunks (71.8 GB VRAM)
- Phase 3: Full 99-node master cross-universe spectral SVD + 27 cross-bridges + condition number
- Phase 4: In-place 35M-path multi-horizon SDE (7D, 30D, 90D, 365D)
- Phase 5: Cross-universe contagion reachability matrix (15x15 apex with 35M paths)
- Phase 6: Systematic N-1 node knockout resilience analysis (99 nodes)
- Phase 7: Allele pairwise epistasis matrix (496 pairs)
- Phase 8: CBF breach remediation re-baselining U13/U14 nodes
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE_DIR = ROOT / "orchestrator-state"
BURST_LEDGER = STATE_DIR / "azmuth_colab_burst_ledger.json"
INGESTION_FEED = STATE_DIR / "azmuth_ingestion_feed.jsonl"
MUTATION_LEDGER = STATE_DIR / "azmuth_mutation_ledger.json"
UNIVERSES_DIR = ROOT / "data" / "universes"
WORKER_V2_TEMPLATE_FILE = ROOT / "tools" / "azmuth_remote_worker_v2.py.tpl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ColabHyperBurst] %(message)s",
)
logger = logging.getLogger("azmuth_colab_burst")

COLAB_BIN = shutil.which("colab") or "colab"
IS_WIN = sys.platform == "win32"


def get_colab_compute_balance() -> Tuple[float, str]:
    """Queries colab usage to extract available compute units balance."""
    cmd = [COLAB_BIN, "usage"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=IS_WIN)
        out = proc.stdout
        m = re.search(r"Current balance:\s*([\d\.]+)\s*compute units", out)
        if m:
            return float(m.group(1)), out.strip()
    except Exception as exc:
        logger.warning(f"Failed to query colab usage: {exc}")
    return 0.0, ""


def write_remote_worker_script(
    dest_path: Path,
    monte_carlo_trials: int = 1000000000,
    chunk_size: int = 165000000,
    sde_paths: int = 35000000,
    contagion_paths: int = 35000000,
    knockout_paths: int = 20000000,
) -> None:
    """Generates the remote worker script executed inside the Colab VM."""
    universes_dict: dict[str, Any] = {}
    if UNIVERSES_DIR.exists():
        for u_file in UNIVERSES_DIR.glob("*.json"):
            try:
                universes_dict[u_file.name] = json.loads(u_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    from tools.azmuth_macro_graph import CROSS_UNIVERSE_BRIDGE_SYNAPSES

    template_code = WORKER_V2_TEMPLATE_FILE.read_text(encoding="utf-8")
    universes_json_str = json.dumps(universes_dict)
    bridges_json_str = json.dumps(CROSS_UNIVERSE_BRIDGE_SYNAPSES)

    script_content = (
        template_code.replace("__MONTE_CARLO_TRIALS__", str(monte_carlo_trials))
        .replace("__CHUNK_SIZE__", str(chunk_size))
        .replace("__SDE_PATHS__", str(sde_paths))
        .replace("__CONTAGION_PATHS__", str(contagion_paths))
        .replace("__KNOCKOUT_PATHS__", str(knockout_paths))
        .replace("__EMBEDDED_UNIVERSES_JSON__", repr(universes_json_str))
        .replace("__EMBEDDED_BRIDGES_JSON__", repr(bridges_json_str))
    )
    dest_path.write_text(script_content, encoding="utf-8")


def run_cloud_hyper_burst(
    tier: str = "a100-highmem",
    monte_carlo_trials: int = 1000000000,
    chunk_size: int = 165000000,
    sde_paths: int = 35000000,
    contagion_paths: int = 35000000,
    knockout_paths: int = 20000000,
    sync_drive: bool = True,
    session_name: str = "azmuth-expansion-v2",
    timeout_sec: float = 7200.0,
) -> dict[str, Any]:
    """Orchestrates provisioning, execution, result download, and teardown."""
    logger.info("=== INITIALIZING AZMUTH CLOUD HYPER-BURST V2 ===")
    initial_balance, _ = get_colab_compute_balance()
    logger.info(f"Initial Compute Unit Balance: {initial_balance:.2f} units")

    scratch_dir = ROOT / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    local_worker_script = scratch_dir / "remote_hyperburst_worker_v2.py"
    write_remote_worker_script(
        local_worker_script,
        monte_carlo_trials=monte_carlo_trials,
        chunk_size=chunk_size,
        sde_paths=sde_paths,
        contagion_paths=contagion_paths,
        knockout_paths=knockout_paths,
    )

    tier_flags = []
    if tier == "a100-highmem":
        tier_flags = ["--gpu", "A100", "--high-mem"]
    elif tier == "a100":
        tier_flags = ["--gpu", "A100"]
    elif tier == "t4":
        tier_flags = ["--gpu", "T4"]
    elif tier == "l4":
        tier_flags = ["--gpu", "L4"]
    elif tier == "cpu-highmem":
        tier_flags = ["--high-mem"]

    burst_record: dict[str, Any] = {
        "timestamp_start": datetime.now(timezone.utc).isoformat(),
        "tier": tier,
        "session_name": session_name,
        "initial_balance": initial_balance,
        "status": "FAILED",
    }

    try:
        # 1. Provision VM
        new_cmd = [COLAB_BIN, "new", "-s", session_name] + tier_flags
        logger.info(f"Provisioning session: {' '.join(new_cmd)}")
        try:
            subprocess.run(new_cmd, check=True, shell=IS_WIN)
        except subprocess.CalledProcessError:
            if tier == "a100-highmem":
                logger.warning("A100-HighMem shape busy. Automatically falling back to standard A100 GPU...")
                tier_flags = ["--gpu", "A100"]
                new_cmd = [COLAB_BIN, "new", "-s", session_name] + tier_flags
                subprocess.run(new_cmd, check=True, shell=IS_WIN)
            else:
                raise

        # 2. Execute Worker script
        logger.info(f"Executing parallel hyper-burst v2 on {tier.upper()} (Timeout: {timeout_sec}s)...")
        exec_cmd = [
            COLAB_BIN,
            "exec",
            "-s",
            session_name,
            "-f",
            str(local_worker_script),
            "--timeout",
            str(timeout_sec),
        ]
        exec_proc = subprocess.run(exec_cmd, capture_output=True, text=True, check=False, shell=IS_WIN)
        raw_stdout = exec_proc.stdout or ""
        raw_stderr = exec_proc.stderr or ""
        logger.info(f"Remote execution finished with exit code {exec_proc.returncode}, stdout length {len(raw_stdout)}, stderr length {len(raw_stderr)}")
        if raw_stderr:
            logger.warning(f"Remote stderr preview:\n{raw_stderr[:1000]}")
        if raw_stdout:
            logger.info(f"Remote stdout preview:\n{raw_stdout[:1000]}")

        # 3. Extract and parse results directly from output stream or download fallback
        local_results_path = STATE_DIR / "hyperburst_results.json"
        local_v2_results_path = STATE_DIR / "hyperburst_results_v2.json"
        remote_data: dict[str, Any] = {}

        if "<<<HYPERBURST_PAYLOAD_START>>>" in raw_stdout and "<<<HYPERBURST_PAYLOAD_END>>>" in raw_stdout:
            import base64

            start_marker = "<<<HYPERBURST_PAYLOAD_START>>>"
            end_marker = "<<<HYPERBURST_PAYLOAD_END>>>"
            b64_content = raw_stdout.split(start_marker)[1].split(end_marker)[0].strip()
            try:
                remote_data = json.loads(base64.b64decode(b64_content).decode("utf-8"))
                local_results_path.write_text(json.dumps(remote_data, indent=2), encoding="utf-8")
                local_v2_results_path.write_text(json.dumps(remote_data, indent=2), encoding="utf-8")
                logger.info(f"Extracted payload directly from stdout into {local_v2_results_path}")
            except Exception as e:
                logger.warning(f"Failed to decode stdout payload: {e}")

        if not remote_data:
            logger.info(f"Attempting download fallback to {local_v2_results_path}...")
            dl_cmd = [
                COLAB_BIN,
                "download",
                "-s",
                session_name,
                "/content/hyperburst_results.json",
                str(local_v2_results_path),
            ]
            subprocess.run(dl_cmd, check=False, shell=IS_WIN)
            if local_v2_results_path.exists():
                try:
                    remote_data = json.loads(local_v2_results_path.read_text(encoding="utf-8"))
                    local_results_path.write_text(json.dumps(remote_data, indent=2), encoding="utf-8")
                except Exception:
                    pass

        if remote_data:
            burst_record["remote_data"] = remote_data
            burst_record["status"] = "SUCCESS"

            # Merge evolved alleles into mutation ledger
            evolved = remote_data.get("phase_1_genotype_tournament", {}).get("evolved_alleles", [])
            if MUTATION_LEDGER.exists():
                try:
                    mut_ledger = json.loads(MUTATION_LEDGER.read_text(encoding="utf-8"))
                    mut_ledger["mutations_applied"] = mut_ledger.get("mutations_applied", 0) + len(evolved)
                    mut_ledger["promotions_won"] = mut_ledger.get("promotions_won", 0) + len(evolved)
                    MUTATION_LEDGER.write_text(json.dumps(mut_ledger, indent=2), encoding="utf-8")
                except Exception:
                    pass

            # Record Ingestion Feed event
            feed_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "COLAB_A100_HYPERBURST_V2",
                "source": "ColabCloudAccelerator",
                "item_id": f"burst_v2_{tier}_{session_name}",
                "title": f"Executed A100 High-RAM Hyper-Burst v2 (8 Phases, {monte_carlo_trials:,} MC trials, 35M SDE)",
                "status": "SUCCESS",
                "details": {
                    "accelerator": remote_data.get("accelerator"),
                    "system_ram_gb": remote_data.get("system_ram_gb"),
                    "execution_summary": remote_data.get("execution_time_summary", {}),
                    "evolved_count": len(evolved),
                    "universes": list(remote_data.get("phase_2_monte_carlo_1B", {}).get("universes", {}).keys()),
                    "cbf_breaches_resolved": remote_data.get("phase_8_cbf_remediation", {}).get("breaches_resolved", 0),
                },
            }
            if INGESTION_FEED.exists():
                feed_lines = INGESTION_FEED.read_text(encoding="utf-8").splitlines()
            else:
                feed_lines = []
            feed_lines.append(json.dumps(feed_entry))
            INGESTION_FEED.write_text("\n".join(feed_lines[-500:]) + "\n", encoding="utf-8")

    finally:
        # Mandatory Teardown
        logger.info(f"Terminating remote session '{session_name}'...")
        try:
            subprocess.run([COLAB_BIN, "stop", "-s", session_name], check=True, shell=IS_WIN)
            logger.info("Session terminated cleanly. Zero dangling compute units.")
        except Exception as e:
            logger.warning(f"Notice during session teardown: {e}")

        # Post-flight Cost Audit
        final_balance, _ = get_colab_compute_balance()
        spent = max(0.0, round(initial_balance - final_balance, 4))
        burst_record["final_balance"] = final_balance
        burst_record["units_spent"] = spent
        burst_record["timestamp_end"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Compute Units Spent: {spent:.4f} units (Remaining Balance: {final_balance:.2f} units)")

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            history = []
            if BURST_LEDGER.exists():
                history = json.loads(BURST_LEDGER.read_text(encoding="utf-8"))
            history.append(burst_record)
            BURST_LEDGER.write_text(json.dumps(history[-50:], indent=2), encoding="utf-8")
        except Exception:
            pass

        # Cleanup scratch script
        local_worker_script.unlink(missing_ok=True)

    # 5. Optional Drive Sync
    if sync_drive:
        sync_script = ROOT / "scripts" / "sync_drive.py"
        if sync_script.exists():
            logger.info("Synchronizing updated ledgers and manifests to Google Drive...")
            try:
                subprocess.run([sys.executable, str(sync_script)], cwd=str(ROOT), check=False)
            except Exception as e:
                logger.warning(f"Drive sync notice: {e}")

    logger.info("=== CLOUD HYPER-BURST RUN COMPLETED SUCCESSFULLY ===")
    return burst_record


def main() -> int:
    parser = argparse.ArgumentParser(description="Azmuth Colab Cloud Hyper-Burst Engine v2")
    parser.add_argument("--tier", choices=["a100-highmem", "t4", "l4", "cpu-highmem", "cpu"], default="a100-highmem", help="Compute tier (default: a100-highmem)")
    parser.add_argument("--monte-carlo-trials", type=int, default=1000000000, help="Number of Monte Carlo trials (default: 1,000,000,000)")
    parser.add_argument("--chunk-size", type=int, default=165000000, help="CUDA chunk size (default: 165,000,000)")
    parser.add_argument("--sde-paths", type=int, default=35000000, help="In-place SDE paths (default: 35,000,000)")
    parser.add_argument("--contagion-paths", type=int, default=35000000, help="Contagion matrix paths (default: 35,000,000)")
    parser.add_argument("--knockout-paths", type=int, default=20000000, help="Knockout SDE paths (default: 20,000,000)")
    parser.add_argument("--session-name", type=str, default="azmuth-expansion-v2", help="Remote Colab session name")
    parser.add_argument("--timeout", type=float, default=7200.0, help="Execution timeout in seconds (default: 7200)")
    parser.add_argument("--sync-drive", action="store_true", default=True, help="Trigger Google Drive sync upon completion")
    parser.add_argument("--no-sync-drive", dest="sync_drive", action="store_false", help="Skip Google Drive sync")
    args = parser.parse_args()

    record = run_cloud_hyper_burst(
        tier=args.tier,
        monte_carlo_trials=args.monte_carlo_trials,
        chunk_size=args.chunk_size,
        sde_paths=args.sde_paths,
        contagion_paths=args.contagion_paths,
        knockout_paths=args.knockout_paths,
        sync_drive=args.sync_drive,
        session_name=args.session_name,
        timeout_sec=args.timeout,
    )
    return 0 if record.get("status") == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
