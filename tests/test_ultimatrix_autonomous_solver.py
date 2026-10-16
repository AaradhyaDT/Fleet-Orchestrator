#!/usr/bin/env python3
"""tests/test_ultimatrix_autonomous_solver.py
-------------------------------------------
Unit tests for the Azmuth Ultimatrix Phase 3 Autonomous Solver Engine.
"""

from pathlib import Path
from unittest.mock import patch

from tools.ultimatrix_autonomous_solver import (
    load_solver_ledger,
    save_solver_ledger,
    get_unsolved_tasks,
    synthesize_python_solution,
    run_solution_verification,
    solve_task_autonomously,
)


def test_solver_ledger_roundtrip(tmp_path: Path):
    test_ledger = tmp_path / "test_solver_ledger.json"
    with patch("tools.ultimatrix_autonomous_solver.SOLVER_LEDGER", test_ledger):
        ledger = load_solver_ledger()
        assert ledger["version"] == 1
        ledger["tasks_attempted"] += 1
        ledger["solved_slugs"].append("test-task")
        save_solver_ledger(ledger)

        reloaded = load_solver_ledger()
        assert reloaded["tasks_attempted"] == 1
        assert "test-task" in reloaded["solved_slugs"]


def test_synthesize_python_solution_addition():
    task_info = {"slug": "custom-addition-task", "title": "Sum Two Numbers"}
    code = synthesize_python_solution(task_info)
    assert code is not None
    assert "a + b" in code

    samples = [("10 20", "30"), ("100 250", "350")]
    assert run_solution_verification(code, samples) is True


def test_synthesize_python_solution_gcd():
    task_info = {"slug": "binary-gcd", "title": "Greatest Common Divisor"}
    code = synthesize_python_solution(task_info)
    assert code is not None
    assert "math.gcd" in code

    samples = [("12 18", "6"), ("100 25", "25")]
    assert run_solution_verification(code, samples) is True


def test_synthesize_python_solution_acronyms():
    task_info = {"slug": "acronyms", "title": "Acronyms"}
    code = synthesize_python_solution(task_info)
    assert code is not None
    assert "Counter" in code

    # Sample test: 5 words, output should be 2
    sample_inp = "5\nabc\nbcad\ncabd\ncba\ndzzz"
    samples = [(sample_inp, "2")]
    assert run_solution_verification(code, samples) is True
