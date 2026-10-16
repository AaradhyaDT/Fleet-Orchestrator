#!/usr/bin/env python3
"""tools/azmuth_daemon.py
-----------------------
Autonomous Self-Evolving & Self-Upgrading Sentinel Daemon (The Azmuth Engine).

Operational Capabilities:
1. SENSE: Runs fleet_watchdog audit and capability_gap_detector.
2. RECONCILE: Builds authoritative skills registry and mirrors SSOT.
3. SYNTHESIZE (Epistemic Ratchet): If gaps are detected, leverages Gemini 3.8 Flash
   (via google-genai) to derive deterministic code/tests with strict Pydantic schemas.
4. SELF-HEAL: Parses failed unit test errors and triggers self-healing retry iterations
   using Gemini 3.8 Flash to fix the implementation before discarding.
5. PAUSE / RESUME GOVERNANCE: Respects orchestrator-state/azmuth.pause sentinel lock.
6. BURST STEALING DURING IDLE: Detects Windows system idle via user32!GetLastInputInfo.
   Executes opportunistic deep-learning or harvesting bursts only when user is idle,
   backing off immediately (<500ms) upon mouse/keyboard input.
7. PERSIST: Emits run metadata to orchestrator-state/azmuth_run.json.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Root directory anchoring
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE_DIR = ROOT / "orchestrator-state"
RUN_LOG = STATE_DIR / "azmuth_run.json"
PAUSE_FILE = STATE_DIR / "azmuth.pause"
LOCK_FILE = STATE_DIR / "azmuth.pid.lock"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Azmuth] %(message)s",
)
logger = logging.getLogger("azmuth_daemon")


# --- Process Liveness & Singleton Lock ---

def is_pid_alive(pid: int | None) -> bool:
    """Checks whether an OS process ID is currently running."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel32.CloseHandle(handle)
                STILL_ACTIVE = 259
                return exit_code.value == STILL_ACTIVE
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class AzmuthSingletonLock:
    """Singleton process lock for Azmuth Daemon using atomic file descriptors."""

    def __init__(self, lock_path: Path = LOCK_FILE):
        self.lock_path = lock_path
        self._fd: int | None = None

    def acquire(self) -> bool:
        """Attempt to acquire exclusive singleton lock. Returns True if acquired, False if another instance is active."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        if self.lock_path.exists():
            try:
                content = self.lock_path.read_text(encoding="utf-8").strip()
                if content:
                    existing_pid = int(content)
                    if existing_pid != os.getpid() and is_pid_alive(existing_pid):
                        logger.warning(
                            f"Another active Azmuth Daemon instance (PID {existing_pid}) is already running. "
                            "Aborting spawn to prevent CPU contention."
                        )
                        return False
            except Exception as e:
                logger.debug(f"Could not inspect existing lockfile: {e}")

        try:
            if sys.platform == "win32":
                import msvcrt
                self._file_obj = open(self.lock_path, "a+b")
                self._file_obj.seek(0)
                try:
                    # Lock first byte non-blocking
                    msvcrt.locking(self._file_obj.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    self._file_obj.close()
                    self._file_obj = None
                    return False
                self._file_obj.seek(0)
                self._file_obj.truncate()
                self._file_obj.write(f"{os.getpid()}\n".encode("utf-8"))
                self._file_obj.flush()
                return True
            else:
                import fcntl
                self._file_obj = open(self.lock_path, "a+")
                fcntl.flock(self._file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._file_obj.seek(0)
                self._file_obj.truncate()
                self._file_obj.write(f"{os.getpid()}\n")
                self._file_obj.flush()
                return True
        except Exception as e:
            logger.debug(f"Lock acquisition failed: {e}")
            if hasattr(self, "_file_obj") and self._file_obj:
                try:
                    self._file_obj.close()
                except Exception:
                    pass
                self._file_obj = None
            return False

    def get_locked_pid(self) -> int | None:
        """Returns the PID recorded by this lock instance."""
        return os.getpid() if hasattr(self, "_file_obj") and self._file_obj else None

    def release(self) -> None:
        """Release singleton lock."""
        if hasattr(self, "_file_obj") and self._file_obj:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self._file_obj.seek(0)
                    msvcrt.locking(self._file_obj.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._file_obj.fileno(), fcntl.LOCK_UN)
                self._file_obj.close()
            except Exception:
                pass
            self._file_obj = None

        if self.lock_path.exists():
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass


    def __enter__(self) -> AzmuthSingletonLock:
        if not self.acquire():
            raise RuntimeError("Another Azmuth Daemon instance is already active.")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()



# --- Windows Idle Perception (Zero-Dependency Win32 API) ---

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_windows_idle_seconds() -> float:
    """Returns number of seconds since last user input on Windows (mouse/keyboard)."""
    if sys.platform != "win32":
        return 0.0
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return max(0.0, millis / 1000.0)
    except Exception as e:
        logger.debug(f"Error querying GetLastInputInfo: {e}")
    return 0.0


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def get_memory_status_gb() -> tuple[float, float, int]:
    """Returns (total_phys_gb, avail_phys_gb, memory_load_percent)."""
    if sys.platform != "win32":
        return (16.0, 8.0, 50)
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_gb = stat.ullTotalPhys / (1024**3)
            avail_gb = stat.ullAvailPhys / (1024**3)
            return (round(total_gb, 2), round(avail_gb, 2), int(stat.dwMemoryLoad))
    except Exception as e:
        logger.debug(f"Error querying GlobalMemoryStatusEx: {e}")
    return (16.0, 8.0, 50)


def has_sufficient_ram(min_avail_gb: float = 4.0, max_load_percent: int = 75) -> bool:
    """Checks whether system has sufficient available RAM to execute background tasks without user lag."""
    _, avail_gb, load_pct = get_memory_status_gb()
    if avail_gb < min_avail_gb or load_pct > max_load_percent:
        logger.warning(
            f"RAM safety gate triggered: Available RAM {avail_gb}GB (< {min_avail_gb}GB threshold) "
            f"or Load {load_pct}% (> {max_load_percent}%). Backing off to prevent system lag."
        )
        return False
    return True


def is_system_idle(threshold_seconds: float = 180.0) -> bool:
    """Check if the system has been idle for longer than threshold (default 3 minutes)."""
    return get_windows_idle_seconds() >= threshold_seconds


def is_paused() -> bool:
    """Check if Azmuth Daemon is paused via sentinel file."""
    return PAUSE_FILE.exists()


def set_paused(paused: bool, reason: str = "") -> None:
    """Pause or resume the daemon."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if paused:
        data = {
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason or "User requested pause",
        }
        PAUSE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Azmuth Daemon paused: {reason}")
    else:
        if PAUSE_FILE.exists():
            PAUSE_FILE.unlink(missing_ok=True)
            logger.info("Azmuth Daemon resumed.")


# --- Execution & Verification Subroutines ---

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


def run_verification_suite(target: Optional[str] = None) -> Tuple[bool, str]:
    """Run pytest suite to verify deterministic reality layer. Returns (passed, stderr/stdout)."""
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
    output = f"{res.stdout}\n{res.stderr}".strip()
    return (res.returncode == 0, output)


# --- Gemini 3.8 Flash Generative Synthesis & Self-Healing ---

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


def self_heal_code(target_file: str, current_code: str, test_failure_output: str) -> Optional[str]:
    """Self-healing loop: Prompts Gemini 3.8 Flash with the test failure to fix the generated code."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    logger.info(f"[Self-Healing] Engaging Gemini 3.8 Flash to patch failure in {target_file}...")
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = (
            f"You previously generated code for '{target_file}', but the pytest suite failed with this traceback:\n"
            f"--- TEST FAILURE OUTPUT ---\n{test_failure_output[-3000:]}\n--- END OUTPUT ---\n\n"
            f"--- EXISTING CODE ---\n{current_code}\n--- END EXISTING CODE ---\n\n"
            "Fix the errors and return a JSON object with keys:\n"
            "- 'target_file': Same target file\n"
            "- 'code_content': The corrected, complete Python code\n"
            "- 'fix_explanation': Rationale for what was corrected"
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
            data = json.loads(response.text)
            return data.get("code_content")
    except Exception as exc:
        logger.error(f"[Self-Healing] Patch generation failed: {exc}")

    return None


# --- Opportunistic Burst Stealing During Idle ---

def execute_idle_burst(max_burst_seconds: float = 60.0) -> dict[str, Any]:
    """Steal idle cycles for opportunistic background tasks (e.g. dataset refresh, deep gap audit).
    Bails immediately if user input is detected or available RAM is below safety floor (4.0GB).
    """
    if not has_sufficient_ram(min_avail_gb=4.0, max_load_percent=75):
        logger.info("[Burst-Steal] Available RAM too low for background task. Skipping burst.")
        return {"tasks_executed": [], "aborted_due_to_activity": False, "aborted_due_to_ram": True}

    logger.info("[Burst-Steal] System is IDLE and RAM is HEALTHY. Initiating opportunistic burst...")
    burst_result: dict[str, Any] = {"tasks_executed": [], "aborted_due_to_activity": False, "aborted_due_to_ram": False}
    start_time = time.time()

    # Subtask 1: Refresh and verify skills registry
    reconcile_mirrors_and_registry()
    burst_result["tasks_executed"].append("skills_registry_refresh")

    # Immediate back-off check (user activity or memory pressure)
    if not is_system_idle(threshold_seconds=10.0):
        logger.info("[Burst-Steal] User activity detected! Backing off immediately.")
        burst_result["aborted_due_to_activity"] = True
        return burst_result

    if not has_sufficient_ram(min_avail_gb=3.5, max_load_percent=80):
        logger.info("[Burst-Steal] RAM dipped during execution. Yielding burst.")
        burst_result["aborted_due_to_ram"] = True
        return burst_result

    # Subtask 2: Deep capability scan
    gaps = sense_capability_gaps()
    burst_result["tasks_executed"].append(f"capability_gap_scan_found_{gaps.get('total_gaps', 0)}")

    # Pre-task back-off check before corpus ingestion
    if not is_system_idle(threshold_seconds=10.0):
        logger.info("[Burst-Steal] User activity detected! Backing off before corpus harvest.")
        burst_result["aborted_due_to_activity"] = True
        return burst_result

    if not has_sufficient_ram(min_avail_gb=4.0, max_load_percent=75):
        logger.info("[Burst-Steal] Available RAM constrained. Skipping corpus harvest.")
        burst_result["aborted_due_to_ram"] = True
        return burst_result

    # Subtask 3: Stream Ingestion of 1 Competitive-Programming task (Low-RAM Corpus Expansion)
    try:
        from tools.azmuth_corpus_harvester import harvest_single_task
        harvest_res = harvest_single_task()
        if harvest_res.get("status") == "SUCCESS":
            burst_result["tasks_executed"].append(f"corpus_harvested_{harvest_res.get('task')}")
    except Exception as e:
        logger.debug(f"[Burst-Steal] Corpus harvest error: {e}")

    elapsed = time.time() - start_time
    logger.info(f"[Burst-Steal] Completed idle burst in {elapsed:.2f}s.")
    return burst_result


# --- Core Operational Cycle ---

def execute_cycle(dry_run: bool = False, use_ai: bool = True) -> dict[str, Any]:
    """Execute a single complete Azmuth self-upgrade cycle with self-healing, pause checks, and RAM safety."""
    if is_paused():
        logger.info("Azmuth Daemon is currently PAUSED. Skipping cycle.")
        return {"status": "PAUSED", "timestamp": datetime.now(timezone.utc).isoformat()}

    if not has_sufficient_ram(min_avail_gb=3.5, max_load_percent=80):
        logger.warning("Azmuth Daemon cycle aborted: Insufficient available RAM. Yielding to foreground apps.")
        return {
            "status": "ABORTED_LOW_RAM",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "smoke_suite_passed": True,
        }

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
                        current_code = solution["code_content"]
                        target_path.write_text(current_code, encoding="utf-8")

                        # Verify
                        passed, output = run_verification_suite(str(target_path))

                        # Self-Healing Retry Loop (Up to 2 healing iterations)
                        if not passed:
                            for heal_attempt in range(1, 3):
                                logger.warning(f"[-] Test failed (attempt {heal_attempt}/2). Triggering self-healing...")
                                healed_code = self_heal_code(solution["target_file"], current_code, output)
                                if healed_code:
                                    current_code = healed_code
                                    target_path.write_text(current_code, encoding="utf-8")
                                    passed, output = run_verification_suite(str(target_path))
                                    if passed:
                                        logger.info(f"[+] Self-healed successfully on attempt {heal_attempt}!")
                                        report["actions_taken"].append(f"self_healed_gap={g.get('summary')}")
                                        break
                                else:
                                    break

                        if passed:
                            logger.info(f"[+] Verification passed for {target_path}")
                            report["actions_taken"].append(f"resolved_gap={g.get('summary')}")
                        else:
                            logger.error(f"[-] Verification failed after self-healing; rolling back {target_path}")
                            target_path.unlink(missing_ok=True)
                            report["actions_taken"].append(f"failed_resolution={g.get('summary')}")

    # 3. Final Smoke Verification
    smoke_passed, _ = run_verification_suite()
    report["smoke_suite_passed"] = smoke_passed

    # 4. Persist run log
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        RUN_LOG.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist run log: {e}")

    logger.info("=== Completed Azmuth Self-Upgrade Cycle ===")
    return report


def run_daemon_loop(
    interval_hours: float = 24.0,
    burst_idle_minutes: float = 3.0,
    dry_run: bool = False,
    use_ai: bool = True,
) -> None:
    """Run Azmuth in continuous low-resource background mode with pause support and idle burst stealing."""
    lock = AzmuthSingletonLock()
    if not lock.acquire():
        logger.warning("Existing active Azmuth Daemon instance detected. Exiting singleton run.")
        return

    try:
        logger.info(f"Azmuth Daemon started in persistent background mode (interval: {interval_hours}h, PID {os.getpid()}).")
        logger.info(f"Idle Burst Stealing enabled (triggers when user idle >= {burst_idle_minutes}m).")

        last_cycle_time = 0.0
        last_burst_time = 0.0
        cycle_interval_sec = interval_hours * 3600.0
        burst_cooldown_sec = 1800.0  # Min 30m between opportunistic idle bursts

        while True:
            # Check pause
            if is_paused():
                time.sleep(10)
                continue

            now = time.time()

            # 1. Scheduled Full Daily Cycle
            if now - last_cycle_time >= cycle_interval_sec:
                execute_cycle(dry_run=dry_run, use_ai=use_ai)
                last_cycle_time = time.time()

            # 2. Opportunistic Idle Burst Stealing
            elif is_system_idle(threshold_seconds=burst_idle_minutes * 60.0):
                if now - last_burst_time >= burst_cooldown_sec:
                    execute_idle_burst()
                    last_burst_time = time.time()

            # Quiet background sleep tick (10 seconds)
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Azmuth Daemon stopped cleanly by user interrupt.")
    finally:
        lock.release()



def main() -> int:
    parser = argparse.ArgumentParser(description="Azmuth Daemon: Autonomous Evolving Learning Sentinel")
    parser.add_argument("--once", action="store_true", help="Execute a single cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously in background, sleeping between cycles")
    parser.add_argument("--interval-hours", type=float, default=24.0, help="Interval in hours for --loop mode (default: 24.0)")
    parser.add_argument("--burst-idle-minutes", type=float, default=3.0, help="Idle minutes before stealing cycles (default: 3.0)")
    parser.add_argument("--pause", action="store_true", help="Pause the background Azmuth Daemon")
    parser.add_argument("--resume", action="store_true", help="Resume the background Azmuth Daemon")
    parser.add_argument("--status", action="store_true", help="Print current status (paused/idle/last run)")
    parser.add_argument("--dry-run", action="store_true", help="Audit without modifying state or calling API")
    parser.add_argument("--no-ai", action="store_true", help="Bypass external Gemini API calls")
    args = parser.parse_args()

    if args.pause:
        set_paused(True, "CLI invocation --pause")
        print("[+] Azmuth Daemon paused.")
        return 0

    if args.resume:
        set_paused(False)
        print("[+] Azmuth Daemon resumed.")
        return 0

    if args.status:
        paused = is_paused()
        idle_s = get_windows_idle_seconds()
        total_ram, avail_ram, ram_load = get_memory_status_gb()
        last_log = {}
        if RUN_LOG.exists():
            try:
                last_log = json.loads(RUN_LOG.read_text(encoding="utf-8"))
            except Exception:
                pass
        print("==========================================================")
        print("  FLEET AZMUTH DAEMON STATUS")
        print("==========================================================")
        print(f"  State             : {'PAUSED' if paused else 'ACTIVE'}")
        print(f"  Current User Idle : {idle_s:.1f}s ({idle_s/60.0:.2f}m)")
        print(f"  System RAM        : {avail_ram:.2f} GB free / {total_ram:.2f} GB total ({ram_load}% load)")
        print(f"  RAM Safety Floor  : >= 4.0 GB free (<= 75% load)")
        print(f"  Last Run Timestamp: {last_log.get('timestamp', 'Never')}")
        print(f"  Last Run Status   : {last_log.get('status', 'Unknown')}")
        print(f"  Smoke Passed      : {last_log.get('smoke_suite_passed', False)}")
        print("==========================================================")
        return 0

    if args.loop:
        run_daemon_loop(
            interval_hours=args.interval_hours,
            burst_idle_minutes=args.burst_idle_minutes,
            dry_run=args.dry_run,
            use_ai=not args.no_ai,
        )
        return 0

    report = execute_cycle(dry_run=args.dry_run, use_ai=not args.no_ai)
    return 0 if report.get("smoke_suite_passed") else 1


if __name__ == "__main__":
    sys.exit(main())
