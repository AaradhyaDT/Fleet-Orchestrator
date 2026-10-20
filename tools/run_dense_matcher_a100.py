#!/usr/bin/env python3
"""tools/run_dense_matcher_a100.py
----------------------------------
High-Value A100 Dense Neural Matcher Watchdog & Cloud Execution Harness.

Target:
- NVIDIA A100-SXM4-40GB GPU + High-RAM VM shape on Google Cloud (`colab run --gpu A100 --high-mem --keep`)
- Multi-Hub Frontier ATS (Ashby, Greenhouse, RemoteOK, Himalayas, Remotive, Jobicy, WWR, UN, GCC)
- Real SentenceTransformer (all-MiniLM-L6-v2) on A100 Tensor Cores
- Hard wall-clock ceiling: 870s (14.5m, strictly <15 min)
- Continuous CU monitoring with safe auto-teardown
- Automatic download of /content/dense_neural_matrix.json to orchestrator-state
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
MAX_CU_BUDGET = 1.40  # Generous headroom for <15 min A100 run (~1.32 CU max at 5.30 CU/hr)
MAX_WALL_TIME_SEC = 870  # 14.5 minutes (<15 min constraint)

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
        subprocess.run(["colab", "stop", "-s", session_name], capture_output=True, text=True, shell=True, timeout=25)
        logger.info("Colab session '%s' terminated successfully.", session_name)
    except Exception as e:
        logger.error("Error stopping session '%s': %s", session_name, e)


def main() -> None:
    session_id = f"azmuth-a100-highmem-{int(time.time())}"
    script_path = ROOT / "tools" / "colab_dense_neural_matcher.py"

    print("=" * 80)
    print("  AZMUTH HIGH-VALUE A100 HIGH-RAM DENSE NEURAL MATCHER & MINING RUN")
    print("=" * 80)

    # 1. Check Initial Balance
    initial_balance = get_colab_balance()
    if initial_balance is None:
        print("[ERROR] Unable to reach Colab CLI or query compute units. Aborting.")
        sys.exit(1)

    print(f"- Initial Compute Unit Balance: {initial_balance:.2f} CU")
    print(f"- Session Name Target:          {session_id}")
    print(f"- Target Accelerator:           NVIDIA A100 GPU (High-RAM Shape)")
    print(f"- Max Budget Ceiling:           {MAX_CU_BUDGET:.2f} CU")
    print(f"- Max Execution Timeout:        {MAX_WALL_TIME_SEC}s ({MAX_WALL_TIME_SEC/60:.1f}m < 15m)")
    print("=" * 80)

    # 2. Launch Background Session with --high-mem and --keep
    cmd = [
        "colab", "run",
        "--session", session_id,
        "--gpu", "A100",
        "--high-mem",
        "--keep",
        "--timeout", "1200",
        str(script_path)
    ]

    print("\n[Watchdog] Spawning A100 GPU High-RAM worker on Google Cloud...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)

    start_time = time.time()
    downloaded_results = False

    try:
        # 3. Read output lines streaming
        while True:
            line = proc.stdout.readline() if proc.stdout else ""
            if line:
                clean_line = line.strip()
                print(f"  [A100] {clean_line}")
                if ("AZMUTH DENSE NEURAL REPORT" in clean_line or "[Persistent Watchdog Mode Active]" in clean_line) and not downloaded_results:
                    # Give remote filesystem 3 seconds to flush to disk
                    time.sleep(3)
                    print("\n[Watchdog] Neural matching report ready! Downloading results from remote A100...")
                    OPPORTUNITIES_DIR.mkdir(parents=True, exist_ok=True)
                    dl_res = subprocess.run(
                        ["colab", "download", "-s", session_id, "/content/dense_neural_matrix.json", str(COLAB_OUTPUT_PATH)],
                        capture_output=True, text=True, shell=True, timeout=40
                    )
                    if dl_res.returncode == 0 and COLAB_OUTPUT_PATH.exists() and COLAB_OUTPUT_PATH.stat().st_size > 50:
                        print(f"[Watchdog] Successfully downloaded dense neural matrix to {COLAB_OUTPUT_PATH}")
                        downloaded_results = True
                    else:
                        # Try secondary path
                        dl_res2 = subprocess.run(
                            ["colab", "download", "-s", session_id, "/content/dense_opportunity_matrix.json", str(COLAB_OUTPUT_PATH)],
                            capture_output=True, text=True, shell=True, timeout=40
                        )
                        if dl_res2.returncode == 0 and COLAB_OUTPUT_PATH.exists() and COLAB_OUTPUT_PATH.stat().st_size > 50:
                            print(f"[Watchdog] Successfully downloaded matrix via secondary path to {COLAB_OUTPUT_PATH}")
                            downloaded_results = True
                        else:
                            print(f"[Watchdog] Download notice: {dl_res.stderr.strip() or dl_res.stdout.strip()}")

            # Check process exit
            if proc.poll() is not None:
                print(f"[Watchdog] Remote process finished with exit code {proc.returncode}.")
                break

            elapsed = time.time() - start_time

            # 4. Periodically inspect compute balance every 25s
            if elapsed > 20 and int(elapsed) % 25 < 2:
                curr_balance = get_colab_balance()
                if curr_balance is not None:
                    cu_used = initial_balance - curr_balance
                    print(f"[Watchdog Monitor] Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}m) | Balance: {curr_balance:.2f} CU (Used: {cu_used:.2f} CU)")
                    if cu_used >= MAX_CU_BUDGET:
                        print("\n" + "!" * 80)
                        print(f"[WATCHDOG TRIGGER] BUDGET CEILING REACHED ({cu_used:.2f} CU >= {MAX_CU_BUDGET:.2f} CU). Teardown.")
                        print("!" * 80)
                        break
                    if downloaded_results and elapsed >= 800:
                        print("\n" + "!" * 80)
                        print(f"[WATCHDOG TRIGGER] Approaching 14-min mark with results secured. Auto-teardown initiated.")
                        print("!" * 80)
                        break

            # 5. Hard Wall-clock timeout enforcing <15 min
            if elapsed >= MAX_WALL_TIME_SEC:
                print(f"\n[Watchdog] Hard wall time ceiling ({MAX_WALL_TIME_SEC}s / {MAX_WALL_TIME_SEC/60:.1f}m) reached. Auto-teardown.")
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
        print("  AZMUTH HIGH-VALUE A100 RUN COMPLETED")
        print("=" * 80)
        print(f"- Run Duration:    {total_time:.1f}s ({total_time/60:.2f}m)")
        print(f"- Initial Balance: {initial_balance:.2f} CU")
        print(f"- Final Balance:   {final_balance:.2f} CU")
        print(f"- Consumed:        {initial_balance - final_balance:.2f} CU")
        print(f"- Output Artifact: {COLAB_OUTPUT_PATH}")
        print("=" * 80)


if __name__ == "__main__":
    main()
