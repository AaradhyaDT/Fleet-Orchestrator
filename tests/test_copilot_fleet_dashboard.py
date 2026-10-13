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
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import pytest

import tools.copilot_fleet as copilot_fleet
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
    assert fleet["online_accounts"] == 0
    assert fleet["status_counts"]["cooldown"] >= 1


def _account(
    *,
    index: int = 1,
    worker_id: str = "copilot-w1",
    name: str = "worker1",
    has_token: bool = True,
) -> dict:
    return {
        "index": index,
        "worker_id": worker_id,
        "name": name,
        "token": "test-token" if has_token else "",
        "has_token": has_token,
        "monthly_credits": 200,
        "state_dir": Path("unused"),
    }


def _write_worker_status(state_dir: Path, **status: object) -> None:
    (state_dir / "live-status" / "copilot-w1.json").write_text(
        json.dumps(status),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def mock_fleet_configuration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(copilot_fleet, "load_env_fleet", lambda: {})
    monkeypatch.setattr(
        copilot_fleet,
        "discover_accounts",
        lambda _: [
            _account(),
            _account(index=2, worker_id="copilot-w2", name="worker2"),
        ],
    )


def test_fresh_busy_heartbeat_counts_runtime_worker_online(mock_fleet_state: Path):
    now = copilot_fleet.datetime.now(copilot_fleet.timezone.utc)
    _write_worker_status(
        mock_fleet_state,
        status="busy",
        current_task_id="task-running",
        heartbeat_at=now.isoformat(),
        credits_used=17.5,
    )

    with patch("tools.copilot_fleet.discover_accounts", return_value=[_account()]):
        metrics = get_fleet_quota_metrics(mock_fleet_state)

    worker = metrics["workers"][0]
    fleet = metrics["fleet"]
    assert fleet["configured_accounts"] == 1
    assert fleet["ready_accounts"] == 1
    assert fleet["online_accounts"] == 1
    assert fleet["credential_verification"] == "unknown"
    assert worker["credential_verification"] == "unknown"
    assert worker["online"] is True
    assert worker["status"] == "busy"


def test_stale_busy_heartbeat_is_offline_without_losing_usage(mock_fleet_state: Path):
    stale = copilot_fleet.datetime.now(copilot_fleet.timezone.utc) - timedelta(seconds=121)
    _write_worker_status(
        mock_fleet_state,
        status="busy",
        current_task_id="task-running",
        heartbeat_at=stale.isoformat(),
        credits_used=17.5,
    )

    with patch("tools.copilot_fleet.discover_accounts", return_value=[_account()]):
        metrics = get_fleet_quota_metrics(mock_fleet_state)

    worker = metrics["workers"][0]
    assert metrics["fleet"]["online_accounts"] == 0
    assert worker["online"] is False
    assert worker["status"] == "offline"
    assert worker["current_task_id"] is None
    assert worker["credits_used"] == 17.5


@pytest.mark.parametrize("credits_used", [-5, "not-a-number", float("nan"), float("inf")])
def test_malformed_or_negative_credits_are_ignored(
    mock_fleet_state: Path, credits_used: object
):
    now = copilot_fleet.datetime.now(copilot_fleet.timezone.utc)
    _write_worker_status(
        mock_fleet_state,
        status="idle",
        heartbeat_at=now.isoformat(),
        credits_used=credits_used,
    )

    with patch("tools.copilot_fleet.discover_accounts", return_value=[_account()]):
        metrics = get_fleet_quota_metrics(mock_fleet_state)

    worker = metrics["workers"][0]
    assert worker["credits_used"] == 0.0
    assert worker["credits_remaining"] == 200.0
    assert metrics["fleet"]["total_credits_used"] == 0.0


@pytest.mark.parametrize("heartbeat", [None, "not-a-timestamp"], ids=["missing", "malformed"])
def test_missing_or_malformed_heartbeat_is_not_online(mock_fleet_state: Path, heartbeat: str | None):
    status = {
        "status": "busy",
        "current_task_id": "task-running",
        "credits_used": 4.25,
    }
    if heartbeat is not None:
        status["heartbeat_at"] = heartbeat
    _write_worker_status(mock_fleet_state, **status)

    with patch("tools.copilot_fleet.discover_accounts", return_value=[_account()]):
        metrics = get_fleet_quota_metrics(mock_fleet_state)

    worker = metrics["workers"][0]
    assert metrics["fleet"]["online_accounts"] == 0
    assert worker["online"] is False
    assert worker["status"] == "offline"
    assert worker["credits_used"] == 4.25


def test_absent_credentials_remain_distinct_from_online_status(mock_fleet_state: Path):
    now = copilot_fleet.datetime.now(copilot_fleet.timezone.utc)
    _write_worker_status(mock_fleet_state, status="idle", heartbeat_at=now.isoformat())

    with patch("tools.copilot_fleet.discover_accounts", return_value=[_account(has_token=False)]):
        metrics = get_fleet_quota_metrics(mock_fleet_state)

    fleet = metrics["fleet"]
    worker = metrics["workers"][0]
    assert fleet["configured_accounts"] == 0
    assert fleet["ready_accounts"] == 0
    assert fleet["online_accounts"] == 1
    assert fleet["credential_verification"] == "unknown"
    assert worker["has_token"] is False
    assert worker["credential_verification"] == "unknown"
    assert worker["online"] is True
    assert worker["status"] == "idle"


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


def test_dashboard_displays_configured_and_fresh_online_counts(mock_fleet_state: Path):
    now = copilot_fleet.datetime.now(copilot_fleet.timezone.utc)
    _write_worker_status(mock_fleet_state, status="idle", heartbeat_at=now.isoformat())

    args = argparse.Namespace(state_dir=str(mock_fleet_state), json=False)
    stdout_buf = io.StringIO()
    with (
        patch("tools.copilot_fleet.discover_accounts", return_value=[_account()]),
        patch("sys.stdout", stdout_buf),
    ):
        cmd_dashboard(args)

    assert "1 Configured" in stdout_buf.getvalue()
    assert "1 Online" in stdout_buf.getvalue()


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
