#!/usr/bin/env python3
"""tools/run_colab_until_cu_consumed.py
---------------------------------------
A100 Cloud Harvester Watchdog & Auto-Teardown Engine.

Lifecycle:
1. Queries initial Colab Compute Unit balance (e.g. 351.70 CU).
2. Spawns an NVIDIA A100 GPU session on Google Colab (`colab run --gpu A100 --keep`).
3. Streams live opportunity harvesting & tensor scoring output.
4. Downloads `/content/deep_eval_results.json` to `orchestrator-state/opportunities/deep_cloud_a100_results.json`.
5. Polls `colab usage` every 20 seconds.
6. The moment balance decrements below initial balance (i.e. first CU consumed):
   - Immediately executes `colab stop -s <session_name>`.
   - Records exact time, final balance, and total opportunities indexed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "orchestrator-state"
OPPORTUNITIES_DIR = STATE_DIR / "opportunities"
COLAB_OUTPUT_PATH = OPPORTUNITIES_DIR / "deep_cloud_a100_results.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [A100-Watchdog] %(message)s")
logger = logging.getLogger("a100_watchdog")


def get_colab_balance() -> Optional[float]:
    """Retrieve current Colab compute unit balance."""
    try:
        res = subprocess.run(["colab", "usage"], capture_output=True, text=True, shell=True, timeout=15)
        m = re.search(r"Current balance:\s*([0-9.]+)\s*compute units", res.stdout)
        if m:
            return float(m.group(1))
    except Exception as e:
        logger.warning("Failed to query colab balance: %s", e)
    return None


def stop_colab_session(session_name: str) -> None:
    """Safely terminate a Colab session."""
    logger.info("Stopping Colab session '%s'...", session_name)
    try:
        subprocess.run(["colab", "stop", "-s", session_name], capture_output=True, text=True, shell=True, timeout=20)
        logger.info("Colab session '%s' terminated successfully.", session_name)
    except Exception as e:
        logger.error("Error stopping session '%s': %s", session_name, e)


def main() -> None:
    session_id = f"azmuth-a100-{int(time.time())}"
    script_path = ROOT / "tools" / "colab_deep_harvester_a100.py"

    print("=" * 80)
    print("  AZMUTH PERSISTENT A100 CLOUD HARVESTER & FIRST-CU WATCHDOG")
    print("=" * 80)

    # 1. Check Initial Balance
    initial_balance = get_colab_balance()
    if initial_balance is None:
        print("[ERROR] Unable to reach Colab CLI or query compute units. Aborting.")
        sys.exit(1)

    print(f"- Initial Compute Unit Balance: {initial_balance:.2f} CU")
    print(f"- Session Name Target:          {session_id}")
    print(f"- Target Accelerator:           NVIDIA A100 GPU")
    print(f"- Teardown Trigger:             Current Balance < {initial_balance:.2f} CU")
    print("=" * 80)

    # 2. Launch Background Session with --keep
    cmd = [
        "colab", "run",
        "--session", session_id,
        "--gpu", "A100",
        "--keep",
        "--timeout", "3600",
        str(script_path)
    ]

    print(f"\n[Watchdog] Spawning persistent A100 GPU worker on Google Cloud...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)

    start_time = time.time()
    downloaded_results = False

    try:
        # 3. Read output lines non-blocking / streaming
        while True:
            line = proc.stdout.readline() if proc.stdout else ""
            if line:
                print(f"  [A100] {line.strip()}")
                if "AZMUTH DEEP HARVEST REPORT" in line and not downloaded_results:
                    # Allow remote script a couple seconds to flush to /content/deep_eval_results.json
                    time.sleep(3)
                    print("\n[Watchdog] Opportunity scoring complete! Downloading results from remote A100...")
                    OPPORTUNITIES_DIR.mkdir(parents=True, exist_ok=True)
                    dl_res = subprocess.run(
                        ["colab", "download", "-s", session_id, "/content/deep_eval_results.json", str(COLAB_OUTPUT_PATH)],
                        capture_output=True, text=True, shell=True, timeout=30
                    )
                    if dl_res.returncode == 0:
                        print(f"[Watchdog] Downloaded report to {COLAB_OUTPUT_PATH}")
                        downloaded_results = True
                    else:
                        print(f"[Watchdog] Download notice: {dl_res.stderr.strip() or dl_res.stdout.strip()}")

            # Check process exit
            if proc.poll() is not None:
                print(f"[Watchdog] Process terminated prematurely with exit code {proc.returncode}.")
                break

            # 4. Periodically inspect compute balance
            elapsed = time.time() - start_time
            if elapsed > 20 and int(elapsed) % 20 < 2:
                curr_balance = get_colab_balance()
                if curr_balance is not None:
                    cu_used = initial_balance - curr_balance
                    print(f"[Watchdog Monitor] Elapsed: {elapsed/60:.1f}m | Balance: {curr_balance:.2f} CU (Consumed: {cu_used:.2f} CU)")
                    if curr_balance < initial_balance:
                        print("\n" + "!" * 80)
                        print(f"[WATCHDOG TRIGGER] FIRST COMPUTE UNITS CONSUMED: {cu_used:.2f} CU billed!")
                        print(f"Stopping A100 session immediately to enforce budget boundaries.")
                        print("!" * 80)
                        break

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[Watchdog] Received manual interrupt signal.")
    finally:
        # Guarantee teardown
        stop_colab_session(session_id)
        final_balance = get_colab_balance() or initial_balance
        total_time = time.time() - start_time
        print("\n" + "=" * 80)
        print("  AZMUTH PERSISTENT A100 HARVESTER RUN COMPLETED")
        print("=" * 80)
        print(f"- Total Run Duration:  {total_time/60:.2f} minutes ({total_time:.1f} seconds)")
        print(f"- Initial Balance:     {initial_balance:.2f} CU")
        print(f"- Final Balance:       {final_balance:.2f} CU")
        print(f"- Total Consumed:      {initial_balance - final_balance:.2f} CU")
        print(f"- Stored Dataset:      {COLAB_OUTPUT_PATH}")
        print("=" * 80)


if __name__ == "__main__":
    main()
