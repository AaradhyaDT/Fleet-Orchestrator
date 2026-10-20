#!/usr/bin/env python3
"""tools/run_dense_matcher_a100.py
----------------------------------
A100 Dense Neural Matcher Watchdog & Cloud Execution Harness.

Lifecycle:
1. Queries initial Colab Compute Unit balance.
2. Spawns an NVIDIA A100 GPU session on Google Colab (`colab run --gpu A100 --keep`).
3. Streams live opportunity harvesting, sentence-transformer encoding, and tensor scoring.
4. Downloads `/content/dense_neural_matrix.json` to `orchestrator-state/opportunities/dense_neural_matrix.json`.
5. Monitors CU consumption with a hard ceiling (0.20 CU budget).
6. Auto-terminates session cleanly and prints final accounting.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "orchestrator-state"
OPPORTUNITIES_DIR = STATE_DIR / "opportunities"
COLAB_OUTPUT_PATH = OPPORTUNITIES_DIR / "dense_neural_matrix.json"
MAX_CU_BUDGET = 0.20
MAX_WALL_TIME_SEC = 180

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [A100-Dense] %(message)s")
logger = logging.getLogger("a100_dense")


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
    session_id = f"azmuth-dense-{int(time.time())}"
    script_path = ROOT / "tools" / "colab_dense_neural_matcher.py"

    print("=" * 80)
    print("  AZMUTH A100 DENSE NEURAL MATCHER & OPPORTUNITY MINING WATCHDOG")
    print("=" * 80)

    # 1. Check Initial Balance
    initial_balance = get_colab_balance()
    if initial_balance is None:
        print("[ERROR] Unable to reach Colab CLI or query compute units. Aborting.")
        sys.exit(1)

    print(f"- Initial Compute Unit Balance: {initial_balance:.2f} CU")
    print(f"- Session Name Target:          {session_id}")
    print(f"- Target Accelerator:           NVIDIA A100 GPU")
    print(f"- Max Budget Ceiling:           {MAX_CU_BUDGET:.2f} CU (Min remaining: {initial_balance - MAX_CU_BUDGET:.2f} CU)")
    print(f"- Max Execution Timeout:        {MAX_WALL_TIME_SEC}s")
    print("=" * 80)

    # 2. Launch Background Session with --keep
    cmd = [
        "colab", "run",
        "--session", session_id,
        "--gpu", "A100",
        "--keep",
        "--timeout", "600",
        str(script_path)
    ]

    print("\n[Watchdog] Spawning A100 GPU worker on Google Cloud...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)

    start_time = time.time()
    downloaded_results = False

    try:
        # 3. Read output lines streaming
        while True:
            line = proc.stdout.readline() if proc.stdout else ""
            if line:
                print(f"  [A100] {line.strip()}")
                if ("AZMUTH DENSE NEURAL REPORT" in line or "[Persistent Watchdog Mode Active]" in line) and not downloaded_results:
                    # Give remote filesystem 3 seconds to flush
                    time.sleep(3)
                    print("\n[Watchdog] Neural matching report ready! Downloading results from remote A100...")
                    OPPORTUNITIES_DIR.mkdir(parents=True, exist_ok=True)
                    dl_res = subprocess.run(
                        ["colab", "download", "-s", session_id, "/content/dense_neural_matrix.json", str(COLAB_OUTPUT_PATH)],
                        capture_output=True, text=True, shell=True, timeout=30
                    )
                    if dl_res.returncode == 0 and COLAB_OUTPUT_PATH.exists() and COLAB_OUTPUT_PATH.stat().st_size > 50:
                        print(f"[Watchdog] Successfully downloaded dense neural matrix to {COLAB_OUTPUT_PATH}")
                        downloaded_results = True
                    else:
                        # Try alternative filename
                        dl_res2 = subprocess.run(
                            ["colab", "download", "-s", session_id, "/content/dense_opportunity_matrix.json", str(COLAB_OUTPUT_PATH)],
                            capture_output=True, text=True, shell=True, timeout=30
                        )
                        if dl_res2.returncode == 0:
                            print(f"[Watchdog] Successfully downloaded matrix via secondary path to {COLAB_OUTPUT_PATH}")
                            downloaded_results = True
                        else:
                            print(f"[Watchdog] Download notice: {dl_res.stderr.strip() or dl_res.stdout.strip()}")

            # Check process exit
            if proc.poll() is not None:
                print(f"[Watchdog] Process finished with exit code {proc.returncode}.")
                break

            elapsed = time.time() - start_time

            # 4. Periodically inspect compute balance
            if elapsed > 15 and int(elapsed) % 15 < 2:
                curr_balance = get_colab_balance()
                if curr_balance is not None:
                    cu_used = initial_balance - curr_balance
                    print(f"[Watchdog Monitor] Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}m) | Balance: {curr_balance:.2f} CU (Used: {cu_used:.2f} CU)")
                    if cu_used >= MAX_CU_BUDGET:
                        print("\n" + "!" * 80)
                        print(f"[WATCHDOG TRIGGER] BUDGET CEILING REACHED ({cu_used:.2f} CU >= {MAX_CU_BUDGET:.2f} CU). Teardown.")
                        print("!" * 80)
                        break
                    if downloaded_results and cu_used > 0.05:
                        print("\n" + "!" * 80)
                        print(f"[WATCHDOG TRIGGER] Results secured and initial CU billed ({cu_used:.2f} CU). Auto-teardown initiated.")
                        print("!" * 80)
                        break

            # 5. Fallback Wall-clock timeout
            if elapsed >= MAX_WALL_TIME_SEC:
                print(f"\n[Watchdog] Max wall time ({MAX_WALL_TIME_SEC}s) reached. Initiating auto-teardown.")
                break

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[Watchdog] Received manual interrupt.")
    finally:
        # Guarantee session teardown
        stop_colab_session(session_id)
        final_balance = get_colab_balance() or initial_balance
        total_time = time.time() - start_time
        print("\n" + "=" * 80)
        print("  AZMUTH A100 DENSE NEURAL MATCHER COMPLETED")
        print("=" * 80)
        print(f"- Run Duration:    {total_time:.1f}s ({total_time/60:.2f}m)")
        print(f"- Initial Balance: {initial_balance:.2f} CU")
        print(f"- Final Balance:   {final_balance:.2f} CU")
        print(f"- Consumed:        {initial_balance - final_balance:.2f} CU")
        print(f"- Output Artifact: {COLAB_OUTPUT_PATH}")
        print("=" * 80)


if __name__ == "__main__":
    main()
