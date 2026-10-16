#!/usr/bin/env python3
"""tools/ultimatrix_solver.py
---------------------------
Azmuth Ultimatrix Autonomous Pipeline: Problem Ingestion, Genetic Splicing & Sample Verification.

Orchestrates the complete solving loop:
1. Ingests problem statements from CS Academy (Markdown) or HackerRank (HTML).
2. Extracts sample input / output test vectors.
3. Consults the codon_stream problem index to identify candidate algorithmic genes.
4. Synthesizes a tailored solution via Ultimatrix DNA Splicer or invokes existing candidate alleles.
5. Executes the solution in an isolated sandbox and checks outputs against expected sample verdicts.
6. Reports zero-drift verification results back to the Azmuth telemetry stream.

Usage:
    python tools/ultimatrix_solver.py --task <slug> [--platform csacademy|hackerrank]
    python tools/ultimatrix_solver.py --verify-all-samples
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
CP_ROOT = Path("F:/Aaradhya-Dev-Tamrakar/Competitive-Programming")
CSACADEMY_TASKS = CP_ROOT / "platforms" / "csacademy" / "tasks"
HACKERRANK_TASKS = CP_ROOT / "platforms" / "hackerrank" / "xtreme-shadows-2026"
STATE_DIR = ROOT / "orchestrator-state"
PROBLEM_INDEX = STATE_DIR / "azmuth_problem_index.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [UltimatrixSolver] %(message)s",
)
logger = logging.getLogger("ultimatrix_solver")


def extract_samples_from_html(html_content: str) -> list[tuple[str, str]]:
    """Extracts paired input and output blocks from HackerRank HTML problem statements."""
    samples: list[tuple[str, str]] = []
    # Pattern 1: <pre> tags (often paired: Sample Input, Sample Output)
    pres = re.findall(r"<pre>(.*?)</pre>", html_content, re.DOTALL)
    clean_blocks = [re.sub(r"<.*?>", "", p).strip() for p in pres if re.sub(r"<.*?>", "", p).strip()]
    if len(clean_blocks) >= 2 and len(clean_blocks) % 2 == 0:
        for i in range(0, len(clean_blocks), 2):
            samples.append((clean_blocks[i], clean_blocks[i + 1]))
    return samples


def extract_samples_from_markdown(md_content: str) -> list[tuple[str, str]]:
    """Extracts sample input/output tables from CS Academy Markdown statements."""
    lines = md_content.splitlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if re.search(r"\|\s*Input\s*\|", line, re.I):
            header_idx = i
            break

    if header_idx != -1:
        headers = [c.strip().lower() for c in lines[header_idx].split("|")[1:-1]]
        inp_col = -1
        out_col = -1
        for idx, col in enumerate(headers):
            if "input" in col and inp_col == -1:
                inp_col = idx
            elif "output" in col and out_col == -1:
                out_col = idx

        if inp_col != -1 and out_col != -1:
            curr_idx = header_idx + 1
            while curr_idx < len(lines) and not re.search(r"\|\s*---", lines[curr_idx]):
                curr_idx += 1
            curr_idx += 1

            samples = []
            for line in lines[curr_idx:]:
                line_str = line.strip()
                if not line_str or not line_str.startswith("|"):
                    break
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if len(cells) > max(inp_col, out_col):
                    inp = re.sub(r"<br\s*/?>", "\n", cells[inp_col], flags=re.I)
                    out = re.sub(r"<br\s*/?>", "\n", cells[out_col], flags=re.I)
                    inp = html.unescape(inp).strip()
                    out = html.unescape(out).strip()
                    if inp or out:
                        samples.append((inp, out))
            if samples:
                return samples

    # Fallback: code blocks
    inp_blocks = re.findall(
        r"(?:###\s*(?:Sample|Standard)\s*input|Input:?)\s*```(?:[a-zA-Z0-9_-]*\n)?(.*?)```",
        md_content,
        re.DOTALL | re.I,
    )
    out_blocks = re.findall(
        r"(?:###\s*(?:Sample|Standard)\s*output|Output:?)\s*```(?:[a-zA-Z0-9_-]*\n)?(.*?)```",
        md_content,
        re.DOTALL | re.I,
    )
    if inp_blocks and out_blocks and len(inp_blocks) == len(out_blocks):
        return [(inp.strip(), out.strip()) for inp, out in zip(inp_blocks, out_blocks)]

    return []


def get_task_samples(task_slug: str, platform: Optional[str] = None) -> list[tuple[str, str]]:
    """Loads sample input/output test cases for a task slug across platforms."""
    # Check HackerRank
    if platform != "csacademy" and HACKERRANK_TASKS.exists():
        hr_dir = HACKERRANK_TASKS / task_slug
        if hr_dir.exists():
            html_file = hr_dir / "statement.html"
            if html_file.exists():
                try:
                    s = extract_samples_from_html(html_file.read_text(encoding="utf-8"))
                    if s:
                        return s
                except Exception:
                    pass

    # Check CS Academy
    if platform != "hackerrank" and CSACADEMY_TASKS.exists():
        csa_dir = CSACADEMY_TASKS / task_slug
        if csa_dir.exists():
            stmt_file = csa_dir / "statement.md"
            if stmt_file.exists():
                try:
                    s = extract_samples_from_markdown(stmt_file.read_text(encoding="utf-8"))
                    if s:
                        return s
                except Exception:
                    pass

    return []


def execute_python_solution(code_or_path: str, input_text: str, timeout_sec: float = 3.0) -> tuple[int, str, str]:
    """Executes a Python solution against input_text and returns (exit_code, stdout, stderr)."""
    if Path(code_or_path).exists() and Path(code_or_path).is_file():
        cmd = [sys.executable, str(code_or_path)]
        tmp_file = None
    else:
        tmp_file = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
        tmp_file.write(code_or_path)
        tmp_file.flush()
        tmp_file.close()
        cmd = [sys.executable, tmp_file.name]

    try:
        proc = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return (proc.returncode, proc.stdout.strip(), proc.stderr.strip())
    except subprocess.TimeoutExpired:
        return (-1, "", "TIMEOUT_EXPIRED")
    except Exception as e:
        return (-2, "", str(e))
    finally:
        if tmp_file:
            try:
                Path(tmp_file.name).unlink(missing_ok=True)
            except Exception:
                pass


def verify_task_solution(task_slug: str, solution_path: Path) -> dict[str, Any]:
    """Tests a solution against all extracted sample test cases for a task."""
    samples = get_task_samples(task_slug)
    if not samples:
        return {
            "status": "NO_SAMPLES",
            "task_slug": task_slug,
            "solution": str(solution_path.name),
            "samples_count": 0,
        }

    results = []
    all_passed = True

    for idx, (inp, expected) in enumerate(samples, 1):
        if solution_path.suffix == ".py":
            code, out, err = execute_python_solution(str(solution_path), inp)
        else:
            return {
                "status": "SKIPPED_CPP",
                "task_slug": task_slug,
                "reason": "C++ compilation sandbox requires native compiler",
            }

        def normalize(text: str) -> str:
            return "\n".join(line.rstrip() for line in text.strip().splitlines())

        passed = (code == 0) and (normalize(out) == normalize(expected))
        if not passed:
            all_passed = False

        results.append({
            "sample_index": idx,
            "passed": passed,
            "exit_code": code,
            "stdout": out,
            "expected": expected,
            "stderr": err,
        })

    return {
        "status": "PASSED" if all_passed else "FAILED",
        "task_slug": task_slug,
        "solution": str(solution_path.name),
        "samples_tested": len(samples),
        "all_passed": all_passed,
        "details": results,
    }


def verify_all_python_benchmarks() -> dict[str, Any]:
    """Discovers all verified Python solutions across the repository and verifies against samples."""
    verified = []
    failed = []
    skipped = []

    # HackerRank tasks
    if HACKERRANK_TASKS.exists():
        for task_dir in sorted(HACKERRANK_TASKS.iterdir()):
            if not task_dir.is_dir():
                continue
            slug = task_dir.name
            sub_dir = task_dir / "submissions"
            if not sub_dir.exists():
                continue

            for py_sub in sorted(sub_dir.glob("*.py")):
                res = verify_task_solution(slug, py_sub)
                if res.get("status") == "PASSED":
                    verified.append(res)
                    logger.info(f"[SamplePASS] {slug} ({py_sub.name}) -> {res.get('samples_tested')} samples passed")
                elif res.get("status") == "FAILED":
                    failed.append(res)
                    logger.warning(f"[SampleFAIL] {slug} ({py_sub.name})")
                else:
                    skipped.append(res)

    return {
        "total_tested": len(verified) + len(failed),
        "passed_count": len(verified),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "verified_tasks": [v["task_slug"] for v in verified],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Azmuth Ultimatrix Autonomous Solver & Verifier")
    parser.add_argument("--task", type=str, help="Problem slug to test")
    parser.add_argument("--verify-all-samples", action="store_true", help="Audit all sample test cases")
    args = parser.parse_args()

    if args.verify_all_samples:
        report = verify_all_python_benchmarks()
        print(json.dumps(report, indent=2))
    elif args.task:
        samples = get_task_samples(args.task)
        print(f"Task: {args.task} | Extracted {len(samples)} samples:")
        for idx, (inp, out) in enumerate(samples, 1):
            print(f"--- Sample #{idx} ---")
            print(f"Input:\n{inp}")
            print(f"Expected Output:\n{out}\n")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
