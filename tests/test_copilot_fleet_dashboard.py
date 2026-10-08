"""
test_copilot_fleet_dashboard.py
-------------------------------
Unit tests for Copilot Fleet Quota Tracking Dashboard, Autonomous Task Submission,
and Standalone Batch Execution.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from tools.copilot_fleet import (
    get_fleet_quota_metrics,
    cmd_dashboard,
    cmd_submit,
    cmd_batch,
    create_task_payload,
)


@pytest.fixture
def mock_fleet_state(tmp_path: Path) -> Path:
    state_dir = tmp_path / "orchestrator-state"
    state_dir.mkdir(parents=True)
    tasks_dir = state_dir / "tasks"
    tasks_dir.mkdir()
    checkpoints_dir = state_dir / "checkpoints"
    checkpoints_dir.mkdir()
    live_status_dir = state_dir / "live-status"
    live_status_dir.mkdir()

    # Create dummy live status files
    (live_status_dir / "copilot-w1.json").write_text(
        json.dumps({
            "account": "copilot-w1",
            "status": "idle",
            "credits_used": 15,
            "monthly_credits": 200,
            "credits_remaining": 185,
            "note": "Ready",
        }),
        encoding="utf-8",
    )
    (live_status_dir / "copilot-w2.json").write_text(
        json.dumps({
            "account": "copilot-w2",
            "status": "cooldown",
            "credits_used": 200,
            "monthly_credits": 200,
            "credits_remaining": 0,
            "cooldown_until": "2099-01-01T00:00:00Z",
            "note": "Quota exhausted",
        }),
        encoding="utf-8",
    )

    return state_dir


def test_get_fleet_quota_metrics(mock_fleet_state: Path):
    metrics = get_fleet_quota_metrics(state_dir=mock_fleet_state)

    fleet = metrics["fleet"]
    assert fleet["total_registered_accounts"] >= 2
    assert fleet["total_credits_used"] >= 215
    assert fleet["burn_rate_pct"] > 0
    assert fleet["status_counts"]["cooldown"] >= 1


def test_cmd_dashboard_json_and_stdout(mock_fleet_state: Path):
    # Test JSON mode
    args_json = argparse.Namespace(state_dir=str(mock_fleet_state), json=True)
    stdout_buf = io.StringIO()
    with patch("sys.stdout", stdout_buf):
        cmd_dashboard(args_json)

    out = stdout_buf.getvalue()
    data = json.loads(out)
    assert "fleet" in data
    assert "workers" in data

    # Test ASCII table mode
    args_table = argparse.Namespace(state_dir=str(mock_fleet_state), json=False)
    stdout_buf_table = io.StringIO()
    with patch("sys.stdout", stdout_buf_table):
        cmd_dashboard(args_table)

    table_out = stdout_buf_table.getvalue()
    assert "COPILOT MULTI-ACCOUNT CLI FLEET QUOTA & BURN-RATE DASHBOARD" in table_out
    assert "copilot-w1" in table_out
    assert "COOLDOWN" in table_out


def test_cmd_submit_autonomous(mock_fleet_state: Path):
    tasks_dir = mock_fleet_state / "tasks"

    args = argparse.Namespace(
        state_dir=str(mock_fleet_state),
        spec="Add auth middleware",
        file=None,
        kind="code",
        task_id="task_custom_099",
    )
    cmd_submit(args)

    task_file = tasks_dir / "task_custom_099.json"
    assert task_file.exists()
    with open(task_file, "r", encoding="utf-8") as f:
        t = json.load(f)
    assert t["id"] == "task_custom_099"
    assert t["spec"] == "Add auth middleware"
    assert t["status"] == "pending"


@pytest.mark.asyncio
async def test_cmd_batch_execution(mock_fleet_state: Path):
    args = argparse.Namespace(
        state_dir=str(mock_fleet_state),
        specs=["Feature 1", "Feature 2"],
        file=None,
        concurrency=2,
        dry_run=True,
    )

    await cmd_batch(args)

    checkpoints_dir = mock_fleet_state / "checkpoints"
    cps = list(checkpoints_dir.glob("task_*.json"))
    assert len(cps) >= 2
