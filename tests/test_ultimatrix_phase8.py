#!/usr/bin/env python3
"""tests/test_ultimatrix_phase8.py
---------------------------------
Unit and integration test suite for Phase 8:
Spliced-DNA Fallback Synthesis & Empirical Judge Sandbox.

Validates:
1. Spliced-DNA template generation via splice_python_dna in fallback mode.
2. Self-healing repair loop in run_solution_verification_with_details.
3. EMPIRICAL_SANDBOX benchmarking in benchmark_allele when task samples exist.
4. Seamless fallback to ANALYTICAL_MODEL when code or samples are absent.
5. End-to-end solve_task_autonomously behavior with fallback mocking.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.ultimatrix_arena import benchmark_allele
from tools.ultimatrix_autonomous_solver import (
    run_solution_verification_with_details,
    solve_task_autonomously,
    synthesize_with_spliced_dna_and_llm,
)


def test_empirical_sandbox_benchmarking(tmp_path: Path):
    """Verifies benchmark_allele executes code in empirical sandbox mode when samples exist."""
    py_code = """import sys
def solve():
    tokens = sys.stdin.read().split()
    if tokens:
        print(int(tokens[0]) + int(tokens[1]))
if __name__ == '__main__':
    solve()
"""
    allele = {
        "allele_id": "test_py_addition",
        "code_template": py_code,
        "complexity_time": "O(1)",
        "complexity_space": "O(1)",
        "environmental_triggers": ["python", "addition"],
    }

    # Mock get_task_samples to return addition test cases
    with patch("tools.ultimatrix_solver.get_task_samples", return_value=[("10 20", "30"), ("5 7", "12")]):
        bench = benchmark_allele(allele, gene_id="TASK_ADDITION")
        assert bench["benchmark_mode"] == "EMPIRICAL_SANDBOX"
        assert bench["runtime_ms"] >= 0.0
        assert "Empirical Judge Sample Vector Suite" in bench["benchmark_input"]


def test_analytical_model_fallback_on_missing_samples():
    """Verifies benchmark_allele falls back to analytical modeling when no samples exist."""
    allele = {
        "allele_id": "test_cpp_dijkstra",
        "code_template": "void dijkstra() {}",
        "complexity_time": "O(N*LOGN)",
        "complexity_space": "O(N)",
        "environmental_triggers": ["cpp"],
    }

    bench = benchmark_allele(allele, gene_id="DIJKSTRA_SHORTEST_PATH")
    assert bench["benchmark_mode"] == "ANALYTICAL_MODEL"
    assert bench["runtime_ms"] > 0.0
    assert "N=2000" in bench["benchmark_input"]


def test_verification_with_details_captures_mismatch():
    """Verifies run_solution_verification_with_details returns structured failure info."""
    buggy_code = """import sys
def solve():
    print("WRONG_ANSWER")
if __name__ == '__main__':
    solve()
"""
    samples = [("1 2", "3")]
    passed, failure = run_solution_verification_with_details(buggy_code, samples)
    assert not passed
    assert failure["expected"] == "3"
    assert failure["actual"] == "WRONG_ANSWER"
    assert failure["sample_idx"] == 1


def test_spliced_dna_llm_synthesis_mocked():
    """Verifies synthesize_with_spliced_dna_and_llm builds correct prompt and strips markdown fences."""
    task_info = {
        "slug": "custom-graph-reachability",
        "title": "Custom Graph Reachability",
        "candidate_genes": ["FAST_IO_STREAM_UNTIE", "DISJOINT_SET_UNION"],
        "samples": [("3 2\n1 2\n2 3", "YES")],
    }

    mock_response = MagicMock()
    mock_response.text = "```python\nimport sys\ndef solve():\n    print('YES')\nif __name__ == '__main__':\n    solve()\n```"

    with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy_test_key"}), \
         patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

        code = synthesize_with_spliced_dna_and_llm(task_info)
        assert code is not None
        assert "def solve():" in code
        assert not code.startswith("```")


def test_solve_task_autonomously_self_healing_success(tmp_path: Path):
    """Verifies self-healing repair pass succeeds when candidate initially fails sample test."""
    slug = "mock-repairable-task"
    samples = [("10 20", "30")]

    buggy_code = "import sys\ndef solve():\n    print(10)\nif __name__ == '__main__':\n    solve()\n"
    fixed_code = "import sys\ndef solve():\n    t = sys.stdin.read().split()\n    print(int(t[0]) + int(t[1]))\nif __name__ == '__main__':\n    solve()\n"

    tmp_ledger = tmp_path / "mock_ledger.json"
    with patch("tools.ultimatrix_solver.get_task_samples", return_value=samples), \
         patch("tools.ultimatrix_autonomous_solver.synthesize_python_solution", return_value=buggy_code), \
         patch("tools.ultimatrix_autonomous_solver.self_heal_solution", return_value=fixed_code), \
         patch("tools.ultimatrix_autonomous_solver.SOLVER_LEDGER", tmp_ledger), \
         patch("tools.ultimatrix_autonomous_solver.CSACADEMY_TASKS", tmp_path):

        res = solve_task_autonomously(slug)
        assert res["status"] == "SUCCESS"
        assert res["samples_passed"] == 1
        sol_file = tmp_path / slug / "solutions" / "solution.py"
        assert sol_file.exists()
        assert "int(t[0]) + int(t[1])" in sol_file.read_text(encoding="utf-8")
