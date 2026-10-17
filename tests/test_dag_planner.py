#!/usr/bin/env python3
"""
tests/test_dag_planner.py
Unit tests for Deterministic Critical Path Method (CPM) DAG Planner.
"""

import json
from pathlib import Path
import pytest
import tempfile

from tools.dag_planner import (
    DeterministicCPMSolver,
    DAGCycleError,
    check_predecessors_satisfied,
    submit_dag_bundle,
)


def test_cpm_linear_chain():
    tasks = [
        {"id": "t1", "duration": 2, "predecessors": []},
        {"id": "t2", "duration": 3, "predecessors": ["t1"]},
        {"id": "t3", "duration": 4, "predecessors": ["t2"]},
    ]
    res = DeterministicCPMSolver.calculate_schedule(tasks)
    assert res["project_duration"] == 9.0
    assert res["critical_path"] == ["t1", "t2", "t3"]
    assert res["parallel_slack"] == []
    assert res["tasks"]["t1"]["ES"] == 0.0
    assert res["tasks"]["t1"]["EF"] == 2.0
    assert res["tasks"]["t2"]["ES"] == 2.0
    assert res["tasks"]["t2"]["EF"] == 5.0
    assert res["tasks"]["t3"]["ES"] == 5.0
    assert res["tasks"]["t3"]["EF"] == 9.0


def test_cpm_diamond_dag_with_slack():
    # Canonical diamond DAG:
    # A (3) -> B (2), C (4)
    # B -> D (3)
    # C -> D (3)
    # Critical Path: A (3) -> C (4) -> D (3) = 10.0
    # Slack: B has Total Float (TF) = 2.0
    tasks = [
        {"id": "A", "duration": 3, "predecessors": []},
        {"id": "B", "duration": 2, "predecessors": ["A"]},
        {"id": "C", "duration": 4, "predecessors": ["A"]},
        {"id": "D", "duration": 3, "predecessors": ["B", "C"]},
    ]
    res = DeterministicCPMSolver.calculate_schedule(tasks)
    assert res["project_duration"] == 10.0
    assert res["critical_path"] == ["A", "C", "D"]
    assert res["parallel_slack"] == ["B"]

    t_b = res["tasks"]["B"]
    assert t_b["ES"] == 3.0
    assert t_b["EF"] == 5.0
    assert t_b["LS"] == 5.0
    assert t_b["LF"] == 7.0
    assert t_b["TS"] == 2.0
    assert not t_b["is_critical"]

    t_c = res["tasks"]["C"]
    assert t_c["ES"] == 3.0
    assert t_c["EF"] == 7.0
    assert t_c["LS"] == 3.0
    assert t_c["LF"] == 7.0
    assert t_c["TS"] == 0.0
    assert t_c["is_critical"]


def test_cpm_cycle_detection():
    # A -> B -> C -> A
    tasks = [
        {"id": "A", "duration": 2, "predecessors": ["C"]},
        {"id": "B", "duration": 2, "predecessors": ["A"]},
        {"id": "C", "duration": 2, "predecessors": ["B"]},
    ]
    with pytest.raises(DAGCycleError) as exc_info:
        DeterministicCPMSolver.calculate_schedule(tasks)
    assert "Directed cycle detected" in str(exc_info.value)


def test_cpm_unknown_predecessor_error():
    tasks = [
        {"id": "A", "duration": 2, "predecessors": ["NON_EXISTENT"]},
    ]
    with pytest.raises(ValueError) as exc_info:
        DeterministicCPMSolver.calculate_schedule(tasks)
    assert "unknown predecessor" in str(exc_info.value)


def test_check_predecessors_satisfied():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_dir = Path(tmp_dir)
        tasks_dir = state_dir / "tasks"
        checkpoints_dir = state_dir / "checkpoints"
        tasks_dir.mkdir()
        checkpoints_dir.mkdir()

        task = {
            "id": "child",
            "predecessors": ["parent1", "parent2"],
        }

        # Case 1: Neither satisfied
        sat, unres = check_predecessors_satisfied(task, state_dir)
        assert not sat
        assert set(unres) == {"parent1", "parent2"}

        # Case 2: Parent 1 has checkpoint
        (checkpoints_dir / "parent1.json").write_text("{}", encoding="utf-8")
        sat, unres = check_predecessors_satisfied(task, state_dir)
        assert not sat
        assert unres == ["parent2"]

        # Case 3: Parent 2 marked done in tasks
        (tasks_dir / "parent2.json").write_text(json.dumps({"status": "done"}), encoding="utf-8")
        sat, unres = check_predecessors_satisfied(task, state_dir)
        assert sat
        assert unres == []


def test_submit_dag_bundle_dry_run_and_real():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dag_file = tmp_path / "test_dag.json"
        dag_content = {
            "bundle_id": "test_bundle_001",
            "tasks": [
                {"id": "task_1", "duration": 1, "spec": "Prepare scaffold"},
                {"id": "task_2", "duration": 2, "predecessors": ["task_1"], "spec": "Write code"},
            ]
        }
        dag_file.write_text(json.dumps(dag_content), encoding="utf-8")

        state_dir = tmp_path / "orchestrator_state"

        # 1. Dry run
        dry_res = submit_dag_bundle(dag_file, state_dir=state_dir, dry_run=True)
        assert dry_res["bundle_id"] == "test_bundle_001"
        assert dry_res["enqueued_count"] == 2
        assert dry_res["project_duration"] == 3.0
        assert not (state_dir / "tasks" / "task_1.json").exists()

        # 2. Real submission
        real_res = submit_dag_bundle(dag_file, state_dir=state_dir, dry_run=False)
        assert real_res["enqueued_count"] == 2
        t1_file = state_dir / "tasks" / "task_1.json"
        t2_file = state_dir / "tasks" / "task_2.json"
        assert t1_file.exists()
        assert t2_file.exists()

        t2_data = json.loads(t2_file.read_text(encoding="utf-8"))
        assert t2_data["predecessors"] == ["task_1"]
        assert t2_data["cpm"]["is_critical"] is True
