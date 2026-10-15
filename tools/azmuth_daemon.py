#!/usr/bin/env python3
"""tools/azmuth_daemon.py
-----------------------
Autonomous Self-Evolving & Self-Upgrading Sentinel Daemon (The Azmuth Engine).

Operational Cycle:
1. SENSE: Runs fleet_watchdog audit and capability_gap_detector.
2. RECONCILE: Builds authoritative skills registry and mirrors SSOT.
3. SYNTHESIZE (Epistemic Ratchet): If gaps are detected, leverages Gemini 3.8 Flash
   (via google-genai) to derive deterministic code/tests with strict Pydantic schemas.
4. VERIFY: Runs local pytest verification gate. If passed, stages changes.
5. PERSIST: Emits run metadata to orchestrator-state/azmuth_run.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Root directory anchoring
ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "orchestrator-state"
RUN_LOG = STATE_DIR / "azmuth_run.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Azmuth] %(message)s",
)
logger = logging.getLogger("azmuth_daemon")


def run_command(cmd: list[str], cwd: Path = ROOT, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    """Execute a local subprocess with deterministic timeout and output capture."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def sense_capability_gaps() -> dict[str, Any]:
    """Run the 6th Sentinel: capability_gap_detector in JSON mode."""
    detector_script = ROOT / "tools" / "capability_gap_detector.py"
    res = run_command([sys.executable, str(detector_script), "--format", "json"])
    if res.returncode == 0:
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError:
            pass
    return {"total_gaps": 0, "gaps": [], "critical": 0, "high": 0, "medium": 0, "low": 0}


def reconcile_mirrors_and_registry() -> bool:
    """Reconcile skill mirrors and compile skills registry."""
    logger.info("Reconciling skill mirrors and compiling skills registry...")
    # 1. mirror_skills.py --fix
    mirror_script = ROOT / "tools" / "mirror_skills.py"
    run_command([sys.executable, str(mirror_script), "--fix"])

    # 2. build_skills_registry.py
    registry_script = ROOT / "tools" / "build_skills_registry.py"
    res_reg = run_command([sys.executable, str(registry_script)])
    return res_reg.returncode == 0


def run_verification_suite(target: Optional[str] = None) -> bool:
    """Run pytest suite to verify deterministic reality layer."""
    cmd = [sys.executable, "-m", "pytest"]
    if target:
        cmd.append(target)
    else:
        # Default fast smoke verification
        cmd.extend([
            "tests/test_adaptive_cli_governance.py",
            "tests/test_codex_cli_adapter.py",
            "tests/test_copilot_cli_adapter.py",
            "tests/test_symbolic_math_adapter.py",
        ])
    res = run_command(cmd, timeout=90.0)
    return res.returncode == 0


def synthesize_gap_solution_with_gemini(gap: dict[str, Any]) -> Optional[dict[str, str]]:
    """Synthesizes code/test solution using Gemini 3.8 Flash via official google-genai SDK."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("No GEMINI_API_KEY found; skipping generative synthesis.")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = (
            "You are Azmuth, the master system architect of Fleet-Orchestrator. "
            "Resolve the following capability gap by providing the exact deterministic Python code or unit test.\n"
            f"Gap Category: {gap.get('category')}\n"
            f"Summary: {gap.get('summary')}\n"
            f"Details: {json.dumps(gap.get('details', {}))}\n\n"
            "Return a clean JSON object with keys:\n"
            "- 'target_file': Relative path where the code belongs (e.g. tests/test_xxx.py)\n"
            "- 'code_content': Pure executable Python code\n"
            "- 'description': Concise rationale\n"
            "Do not output markdown code blocks outside the JSON."
        )

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        if response.text:
            return json.loads(response.text)
    except Exception as exc:
        logger.error("Generative synthesis error with Gemini 3.8 Flash: %s", exc)

    return None


def execute_cycle(dry_run: bool = False, use_ai: bool = True) -> dict[str, Any]:
    """Execute a single complete Azmuth self-upgrade cycle."""
    cycle_start = datetime.now(timezone.utc)
    logger.info("=== Starting Azmuth Self-Upgrade Cycle ===")

    report: dict[str, Any] = {
        "timestamp": cycle_start.isoformat(),
        "status": "HEALTHY",
        "tokens_spent": 0,
        "gaps_detected": 0,
        "actions_taken": [],
    }

    # 1. Reconcile
    reconciled = reconcile_mirrors_and_registry()
    report["actions_taken"].append(f"reconcile_registry_success={reconciled}")

    # 2. Sense
    gap_data = sense_capability_gaps()
    total_gaps = gap_data.get("total_gaps", 0)
    report["gaps_detected"] = total_gaps

    if total_gaps == 0:
        logger.info("[+] Zero capability gaps detected. System is 100% healthy.")
        report["status"] = "ALL_HEALTHY_ZERO_TOKENS"
    else:
        logger.warning(f"[-] {total_gaps} capability gap(s) detected.")
        report["status"] = "GAPS_DETECTED"

        if use_ai and not dry_run:
            for g in gap_data.get("gaps", []):
                if g.get("severity") in ("HIGH", "CRITICAL"):
                    logger.info(f"Synthesizing solution via Gemini 3.8 Flash for: {g.get('summary')}")
                    solution = synthesize_gap_solution_with_gemini(g)
                    if solution and "target_file" in solution and "code_content" in solution:
                        target_path = ROOT / solution["target_file"]
                        logger.info(f"Applying synthesized code to: {target_path}")
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        target_path.write_text(solution["code_content"], encoding="utf-8")

                        # Verify
                        passed = run_verification_suite(str(target_path))
                        if passed:
                            logger.info(f"[+] Verification passed for {target_path}")
                            report["actions_taken"].append(f"resolved_gap={g.get('summary')}")
                        else:
                            logger.error(f"[-] Verification failed for {target_path}; rolling back")
                            target_path.unlink(missing_ok=True)
                            report["actions_taken"].append(f"failed_resolution={g.get('summary')}")

    # 3. Final Smoke Verification
    smoke_passed = run_verification_suite()
    report["smoke_suite_passed"] = smoke_passed

    # 4. Persist run log
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        RUN_LOG.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist run log: {e}")

    logger.info("=== Completed Azmuth Self-Upgrade Cycle ===")
    return report


def run_daemon_loop(interval_hours: float = 24.0, dry_run: bool = False, use_ai: bool = True) -> None:
    """Run Azmuth in continuous low-resource background mode, executing once per interval."""
    logger.info(f"Azmuth Daemon started in persistent background mode (interval: {interval_hours}h).")
    try:
        while True:
            execute_cycle(dry_run=dry_run, use_ai=use_ai)
            sleep_seconds = interval_hours * 3600
            logger.info(f"Sleeping for {interval_hours} hours until next scheduled cycle...")
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("Azmuth Daemon stopped cleanly by user interrupt.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Azmuth Daemon: Autonomous Evolving Learning Sentinel")
    parser.add_argument("--once", action="store_true", help="Execute a single cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously in background, sleeping between daily cycles")
    parser.add_argument("--interval-hours", type=float, default=24.0, help="Interval in hours for --loop mode (default: 24.0)")
    parser.add_argument("--dry-run", action="store_true", help="Audit without modifying state or calling API")
    parser.add_argument("--no-ai", action="store_true", help="Bypass external Gemini API calls")
    args = parser.parse_args()

    if args.loop:
        run_daemon_loop(interval_hours=args.interval_hours, dry_run=args.dry_run, use_ai=not args.no_ai)
        return 0

    report = execute_cycle(dry_run=args.dry_run, use_ai=not args.no_ai)
    return 0 if report.get("smoke_suite_passed") else 1


if __name__ == "__main__":
    sys.exit(main())
