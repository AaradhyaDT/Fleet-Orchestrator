"""Unit tests for tools/cpm_solver.py (INV-CPM-SOLVER)."""

import pytest
from tools.cpm_solver import DeterministicCPMSolver, format_cpm_output


def test_cpm_solver_linear_chain():
    tasks = [
        {"id": "A", "duration": 5, "dependencies": []},
        {"id": "B", "duration": 10, "dependencies": ["A"]},
        {"id": "C", "duration": 3, "dependencies": ["B"]},
    ]
    res = DeterministicCPMSolver.solve(tasks)
    assert res["makespan"] == 18.0
    assert res["critical_path"] == ["A", "B", "C"]
    assert res["tasks_count"] == 3
    assert res["schedule"]["A"]["ES"] == 0.0
    assert res["schedule"]["A"]["EF"] == 5.0
    assert res["schedule"]["B"]["ES"] == 5.0
    assert res["schedule"]["B"]["EF"] == 15.0
    assert res["schedule"]["C"]["ES"] == 15.0
    assert res["schedule"]["C"]["EF"] == 18.0


def test_cpm_solver_parallel_branches_with_slack():
    tasks = [
        {"id": "Start", "duration": 2, "dependencies": []},
        {"id": "BranchFast", "duration": 3, "dependencies": ["Start"]},
        {"id": "BranchSlow", "duration": 8, "dependencies": ["Start"]},
        {"id": "End", "duration": 4, "dependencies": ["BranchFast", "BranchSlow"]},
    ]
    res = DeterministicCPMSolver.solve(tasks)
    assert res["makespan"] == 14.0  # 2 + 8 + 4
    assert res["critical_path"] == ["Start", "BranchSlow", "End"]
    # Fast branch total slack must be 5.0
    assert res["schedule"]["BranchFast"]["TS"] == 5.0
    assert res["schedule"]["BranchFast"]["is_critical"] is False
    assert res["schedule"]["BranchSlow"]["TS"] == 0.0
    assert res["schedule"]["BranchSlow"]["is_critical"] is True


def test_cpm_solver_cycle_detection():
    tasks = [
        {"id": "A", "duration": 1, "dependencies": ["B"]},
        {"id": "B", "duration": 1, "dependencies": ["A"]},
    ]
    with pytest.raises(ValueError, match="Cycle detected"):
        DeterministicCPMSolver.solve(tasks)


def test_cpm_format_output():
    tasks = [{"id": "Task1", "duration": 2, "dependencies": []}]
    res = DeterministicCPMSolver.solve(tasks)
    formatted = format_cpm_output(res)
    assert "MATHEMATICAL CPM DAG SCHEDULE" in formatted
    assert "Task1" in formatted
