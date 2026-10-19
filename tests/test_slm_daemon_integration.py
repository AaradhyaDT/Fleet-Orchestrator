"""Unit tests for Master Control Fast-Path SLM Router Integration into fleet_daemon.py."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tools.fleet_daemon import FleetDaemon
from tools.slm_intent_router import SLMIntentRouter, IntentRoutingResult


@pytest.fixture
def temp_daemon_env(tmp_path: Path):
    """Fixture providing isolated state_dir and worktrees for FleetDaemon."""
    state_dir = tmp_path / "orchestrator-state"
    state_dir.mkdir(parents=True)
    tasks_dir = state_dir / "tasks"
    tasks_dir.mkdir()
    checkpoints_dir = state_dir / "checkpoints"
    checkpoints_dir.mkdir()
    live_status_dir = state_dir / "live-status"
    live_status_dir.mkdir()

    daemon = FleetDaemon(
        state_dir=state_dir,
        concurrency=1,
        dry_run=True,
        fast_path_enabled=True,
    )
    return daemon, state_dir, tasks_dir, checkpoints_dir


def test_classify_and_annotate_task_latency_and_codons(temp_daemon_env):
    """Verifies task classification runs within <50ms and annotates codon & target skill."""
    daemon, _, tasks_dir, _ = temp_daemon_env

    specs_and_expected = [
        ("Audit the system for memory leaks and check control barrier function safety", "SYSTEM_AUDIT", "cyber-forensics"),
        ("Run 30-day SDE stochastic simulation on A100 hyperburst with Azmuth", "FORESIGHT_SIMULATION", "adaptive-workflow"),
        ("Calibrate ESP32 FreeRTOS queue and compute TinyML INT8 fall latency on IMU", "HARDWARE_SYNTH", "edge-ai-model-forge"),
        ("Sync repository commits and open PR under issue #192", "VCS_SYNC", "github-workflow"),
        ("Draft a research thesis report in LaTeX on multi-model swarms", "RESEARCH_SYNTHESIS", "writing-like-claude"),
        ("Refactor the parser function and fix failing unit test cases", "CODE_REFACTOR", "github-workflow"),
    ]

    for spec, expected_codon, expected_skill in specs_and_expected:
        task = {
            "id": f"task_test_{int(time.time() * 1000)}",
            "spec": spec,
            "kind": "code",
            "status": "pending",
        }
        t0 = time.perf_counter()
        res = daemon.classify_and_annotate_task(task)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert elapsed_ms < 50.0, f"Classification exceeded 50ms latency target: {elapsed_ms:.2f}ms"
        assert res.intent_codon == expected_codon
        assert res.target_skill == expected_skill
        assert task["intent_codon"] == expected_codon
        assert task["target_skill"] == expected_skill
        assert "slm_route" in task["metadata"]
        assert task["metadata"]["slm_route"]["intent_codon"] == expected_codon


@pytest.mark.asyncio
async def test_fast_path_slm_execution_without_worker_teardown(temp_daemon_env):
    """Verifies that fast-path eligible tasks execute directly in-process without worker teardown."""
    daemon, state_dir, tasks_dir, checkpoints_dir = temp_daemon_env

    task_id = "task_fast_path_001"
    task_payload = {
        "id": task_id,
        "spec": "Audit the system for memory leaks and verify forensic safety",
        "kind": "code",
        "status": "pending",
        "execution_route": "LOCAL_SLM",
    }
    task_file = tasks_dir / f"{task_id}.json"
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(task_payload, f)

    account = {"worker_id": "copilot-w1", "name": "Worker 1"}

    # Execute task through daemon
    result = await daemon.execute_task(task_payload, account)

    assert result["success"] is True
    assert result["fast_path"] is True
    assert result["intent_codon"] == "SYSTEM_AUDIT"
    assert result["target_skill"] == "cyber-forensics"
    assert len(daemon.fast_path_history) == 1
    assert daemon.fast_path_history[0]["task_id"] == task_id


@pytest.mark.asyncio
async def test_fast_path_via_flag(temp_daemon_env):
    """Verifies fast_path: true flag bypasses heavy execution."""
    daemon, _, _, _ = temp_daemon_env

    task_id = "task_fast_path_flag"
    task_payload = {
        "id": task_id,
        "spec": "Run Azmuth foresight simulation across U0-U5 universes",
        "kind": "code",
        "status": "pending",
        "fast_path": True,
    }
    account = {"worker_id": "copilot-w2", "name": "Worker 2"}

    result = await daemon.execute_task(task_payload, account)
    assert result["success"] is True
    assert result["fast_path"] is True
    assert result["intent_codon"] == "FORESIGHT_SIMULATION"
    assert result["target_skill"] == "adaptive-workflow"


@pytest.mark.asyncio
async def test_end_to_end_daemon_process_one_task(temp_daemon_env):
    """Verifies end-to-end task claiming, SLM annotation, checkpointing, and completion."""
    daemon, state_dir, tasks_dir, checkpoints_dir = temp_daemon_env

    # Mock accounts in daemon
    daemon.ready_accounts = [{"worker_id": "copilot-w1", "name": "Worker 1", "monthly_credits": 200}]

    task_id = "task_e2e_slm_001"
    task_payload = {
        "id": task_id,
        "spec": "Calibrate ESP32 FreeRTOS queue and compute TinyML INT8 fall latency",
        "kind": "code",
        "status": "pending",
        "execution_route": "LOCAL_SLM",
    }
    task_file = tasks_dir / f"{task_id}.json"
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(task_payload, f)

    processed = await daemon.process_one_task(target_task_id=task_id)
    assert processed is True

    # Check task status updated to done
    with open(task_file, "r", encoding="utf-8") as f:
        updated = json.load(f)
    assert updated["status"] == "done"

    # Check checkpoint generated
    cp_file = checkpoints_dir / f"{task_id}.json"
    assert cp_file.exists()


def test_daemon_disabled_fast_path_falls_back():
    """Verifies disabling fast-path still annotates tasks but allows fallback."""
    daemon = FleetDaemon(fast_path_enabled=False, dry_run=True)
    task = {"id": "t1", "spec": "Refactor codebase", "execution_route": "LOCAL_SLM"}
    res = daemon.classify_and_annotate_task(task)
    assert res.intent_codon == "CODE_REFACTOR"
    assert daemon.is_fast_path_eligible(task, res) is False
