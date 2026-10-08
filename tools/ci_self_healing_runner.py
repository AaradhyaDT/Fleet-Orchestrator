#!/usr/bin/env python3
"""
Self-Healing CI Test Runner for Fleet-Orchestrator.
Executes pytest test suites with automated transient error triage,
isolated retry loops, and GitHub Actions step summary generation.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Execute subprocess command and capture output."""
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def parse_pytest_failures(output: str) -> list[str]:
    """Extract failed test names from pytest terminal summary."""
    failed = []
    in_summary = False
    for line in output.splitlines():
        if "short test summary info" in line:
            in_summary = True
            continue
        if in_summary:
            if line.startswith("FAILED "):
                parts = line.split()
                if len(parts) >= 2:
                    test_id = parts[1].split(" - ")[0].strip()
                    failed.append(test_id)
            elif line.startswith("="):
                break
    return failed


def generate_step_summary(
    passed_initially: bool,
    self_healed: bool,
    initial_failures: list[str],
    final_failures: list[str],
    duration: float,
    stdout: str,
) -> None:
    """Generate Markdown summary for GitHub Actions $GITHUB_STEP_SUMMARY."""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = [
        "## 🧪 Test Execution & Verification Gate",
        "",
        f"- **Status**: {'✅ Passed' if (passed_initially or self_healed) else '❌ Failed'}",
        f"- **Self-Healing Active**: {'🔄 Self-Healed' if self_healed else ('None needed' if passed_initially else 'Unresolved')}",
        f"- **Duration**: `{duration:.2f}s`",
        "",
    ]

    if passed_initially:
        lines.extend([
            "> [!NOTE]",
            "> All test suites passed cleanly on the initial run with zero retries required.",
            "",
        ])
    elif self_healed:
        lines.extend([
            "> [!TIP]",
            "> **Self-Healing Alert**: Transient test failures were automatically triaged and passed upon retry.",
            "",
            "### Healed Tests",
            "| Test Name | Initial Result | Retry Result |",
            "|---|---|---|",
        ])
        for test in initial_failures:
            if test not in final_failures:
                lines.append(f"| `{test}` | ❌ Failed | ✅ Healed |")
        lines.append("")
    else:
        lines.extend([
            "> [!WARNING]",
            "> **Failure Diagnostic**: Tests failed and could not be self-healed.",
            "",
            "### Unresolved Failures",
            "| Test Name | Status |",
            "|---|---|",
        ])
        for test in final_failures:
            lines.append(f"| `{test}` | ❌ Persistent Failure |")
        lines.append("")

    # Extract short failure trace snippets if any failed
    if final_failures:
        lines.extend([
            "<details><summary><b>Inspect Failure Tracebacks</b></summary>",
            "",
            "```text",
            stdout[-3000:] if len(stdout) > 3000 else stdout,
            "```",
            "</details>",
            "",
        ])

    try:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"[self-healing] Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-healing test runner")
    parser.add_argument("--max-retries", type=int, default=2, help="Max retry attempts for failed tests")
    parser.add_argument("--pytest-args", nargs=argparse.REMAINDER, default=[], help="Extra arguments to pass to pytest")
    args = parser.parse_args()

    start_time = time.time()
    base_cmd = [sys.executable, "-m", "pytest"] + (args.pytest_args or [])
    print(f"[*] [self-healing] Executing initial test run: {' '.join(base_cmd)}...")

    code, out, err = run_command(base_cmd)
    print(out)
    if err:
        print(err, file=sys.stderr)

    if code == 0:
        elapsed = time.time() - start_time
        print(f"[+] [self-healing] All tests passed cleanly on initial attempt ({elapsed:.2f}s).")
        generate_step_summary(True, False, [], [], elapsed, out)
        return 0

    initial_failures = parse_pytest_failures(out)
    print(f"\n[!] [self-healing] Initial run reported {len(initial_failures)} failure(s):")
    for f in initial_failures:
        print(f"    - {f}")

    # Self-healing retry phase
    self_healed = False
    final_failures = list(initial_failures)
    
    for attempt in range(1, args.max_retries + 1):
        if not final_failures:
            self_healed = True
            break

        print(f"\n[*] [self-healing] Attempt {attempt}/{args.max_retries}: Retrying {len(final_failures)} failed test(s)...")
        retry_cmd = [sys.executable, "-m", "pytest", "--tb=short"] + final_failures
        r_code, r_out, r_err = run_command(retry_cmd)
        print(r_out)

        if r_code == 0:
            print(f"[+] [self-healing] All tests healed and passed on retry attempt {attempt}!")
            final_failures = []
            self_healed = True
            break
        else:
            final_failures = parse_pytest_failures(r_out)
            print(f"[-] [self-healing] Attempt {attempt} finished with {len(final_failures)} remaining failure(s).")

    elapsed = time.time() - start_time
    generate_step_summary(False, self_healed, initial_failures, final_failures, elapsed, out)

    if self_healed:
        print(f"[+] [self-healing] Test suite completed successfully with self-healing recovery.")
        return 0
    else:
        print(f"[!] [self-healing] Execution failed. {len(final_failures)} persistent failure(s) require code fixes.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
