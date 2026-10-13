"""Bounded Windows console/lifecycle probes. No model calls or credential access."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.process_runtime import run_background, popen_background, spawn_background, communicate_background

CONSOLE_PROBE = (
    "import ctypes,json,os,time; "
    "h=ctypes.windll.kernel32.GetConsoleWindow(); "
    "print(json.dumps({'pid':os.getpid(),'console':bool(h),"
    "'visible':bool(h and ctypes.windll.user32.IsWindowVisible(h))}),flush=True); time.sleep(.15)"
)


async def timeout_probe() -> bool:
    import psutil

    proc = await spawn_background(
        sys.executable,
        "-c",
        "import time; time.sleep(30)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    pid = proc.pid
    try:
        await communicate_background(proc, 0.05)
    except asyncio.TimeoutError:
        return not psutil.pid_exists(pid)
    return False


def matrix(compare_legacy: bool) -> dict:
    result = {}
    if compare_legacy:
        probe = subprocess.run([sys.executable, "-c", CONSOLE_PROBE], capture_output=True, text=True, check=True)
        result["legacy_unsuppressed_child"] = json.loads(probe.stdout)
    probe = run_background([sys.executable, "-c", CONSOLE_PROBE], capture_output=True, text=True, check=True)
    result["background_child"] = json.loads(probe.stdout)
    from tools.fleet_accounts import binary_for

    probes = {}
    for provider in ("agy_cli", "codex_cli", "opencode_cli"):
        binary = binary_for({"provider": provider})
        started = time.monotonic()
        try:
            completed = run_background(
                [binary, "--help" if provider == "agy_cli" else "--version"], capture_output=True, timeout=10
            )
            probes[provider] = {
                "exit_code": completed.returncode,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        except (OSError, subprocess.TimeoutExpired):
            probes[provider] = {"exit_code": None, "error": "probe_failed"}
    result["native_health_probes"] = probes
    git = run_background(["git", "--version"], capture_output=True, timeout=10)
    result["verification_command_exit_code"] = git.returncode
    result["timeout_cleanup"] = asyncio.run(timeout_probe())
    with tempfile.TemporaryDirectory(prefix="fleet-persistence-") as directory:
        marker = Path(directory) / "done"
        child_code = (
            "import sys,time; from pathlib import Path; time.sleep(.4); Path(sys.argv[1]).write_text('survived')"
        )
        parent_code = "import sys; from client.process_runtime import popen_background; popen_background([sys.executable,'-c',sys.argv[1],sys.argv[2]],stdin=-3,stdout=-3,stderr=-3)"
        run_background(
            [sys.executable, "-c", parent_code, child_code, str(marker)], cwd=PROJECT_ROOT, check=True, timeout=10
        )
        for _ in range(40):
            if marker.exists():
                break
            time.sleep(0.05)
        result["survives_submitting_parent_exit"] = marker.exists()
    # Explicit interactive login mode deliberately gets a console.
    interactive = subprocess.run(
        [sys.executable, "-c", CONSOLE_PROBE],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        capture_output=True,
        text=True,
        check=True,
    )
    result["interactive_login_console"] = json.loads(interactive.stdout)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compare-legacy", action="store_true", help="Reproduce one brief legacy console flash for comparison"
    )
    parser.add_argument("--child-matrix", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if os.name != "nt":
        print("These console probes require Windows", file=sys.stderr)
        return 1
    if args.child_matrix:
        result = matrix(args.compare_legacy)
    else:
        command = [sys.executable, "-m", "tools.fleet_process_diagnostics", "--child-matrix"]
        if args.compare_legacy:
            command.append("--compare-legacy")
        child = run_background(command, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True, timeout=20)
        result = json.loads(child.stdout)
    result["passed"] = (
        not result["background_child"]["console"]
        and result["timeout_cleanup"]
        and result["survives_submitting_parent_exit"]
        and result["interactive_login_console"]["console"]
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
