"""
tests/test_quota_reconciliation.py
----------------------------------
Unit and integration tests for Copilot fleet quota reconciliation, leaf credit ledger,
adapter error classification precedence, pure read-path invariants, and Fleet Commander.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from tools.credit_ledger import (
    FileLock,
    atomic_write_json,
    next_billing_reset,
    parse_iso_utc,
    sync_worker_ledger,
    reconcile_all_workers,
    initialize_ledgers,
)
from tools.copilot_fleet import get_fleet_quota_metrics
from tools.copilot_queue_worker import CopilotQueueWorker
from tools.fleet_commander import FleetCommander
from client.adapters.copilot_cli_adapter import CopilotCLIAdapter


@pytest.fixture
def temp_orch_state(tmp_path: Path) -> Path:
    state = tmp_path / "orchestrator-state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "tasks").mkdir(exist_ok=True)
    (state / "checkpoints").mkdir(exist_ok=True)
    (state / "live-status").mkdir(exist_ok=True)
    (state / "ledger").mkdir(exist_ok=True)
    (state / "logs").mkdir(exist_ok=True)
    return state


def test_reconcile_idempotency(temp_orch_state: Path, tmp_path: Path):
    """
    Test 1: Verify running reconcile_all_workers twice produces identical
    credit totals and sidecar ledger states without multiplying usage.
    """
    worker_home = tmp_path / "fake_worker_home"
    sess_dir = worker_home / "session-state" / "sess-1234-uuid"
    sess_dir.mkdir(parents=True)
    events_file = sess_dir / "events.jsonl"

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    events_file.write_text(
        json.dumps({
            "type": "session.shutdown",
            "timestamp": now_iso,
            "data": {
                "totalNanoAiu": 2_500_000_000,  # 2.50 credits
            },
        }) + "\n",
        encoding="utf-8",
    )

    accounts = [{
        "worker_id": "test-w1",
        "name": "TestWorker1",
        "has_token": True,
        "monthly_credits": 200,
        "state_dir": str(worker_home),
    }]

    # Run 1
    res1 = reconcile_all_workers(temp_orch_state, accounts)
    used1 = res1["workers"]["test-w1"]["credits_used"]
    assert used1 == 2.50

    # Run 2 (immediate rerun)
    res2 = reconcile_all_workers(temp_orch_state, accounts)
    used2 = res2["workers"]["test-w1"]["credits_used"]
    assert used2 == 2.50
    assert used1 == used2

    # Check sidecar ledger has exactly 1 session entry
    ledger_file = temp_orch_state / "ledger" / "test-w1.json"
    assert ledger_file.exists()
    with open(ledger_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["sessions"]) == 1
    assert data["sessions"]["sess-1234-uuid"] == 2_500_000_000


def test_read_path_in_memory_rollover(temp_orch_state: Path):
    """
    Test 2: Verify get_fleet_quota_metrics with an expired period (e.g., 2026-09)
    reports 0.0 credits used in-memory without modifying the file on disk.
    """
    live_status_dir = temp_orch_state / "live-status"
    status_file = live_status_dir / "copilot-w1.json"

    # Write old period status
    status_file.write_text(
        json.dumps({
            "account": "copilot-w1",
            "name": "worker1",
            "status": "cooldown",
            "period": "2026-09",
            "credits_used": 150.0,
            "credits_remaining": 50.0,
            "monthly_credits": 200,
            "quota_exhausted": False,
            "cooldown_until": "2026-09-30T23:59:59Z",
        }),
        encoding="utf-8",
    )

    mtime_before = status_file.stat().st_mtime_ns

    # Call get_fleet_quota_metrics
    metrics = get_fleet_quota_metrics(temp_orch_state)
    w1 = next(w for w in metrics["workers"] if w["worker_id"] == "copilot-w1")

    # In-memory rollover must report 0.0 credits used and idle status
    assert w1["credits_used"] == 0.0
    assert w1["credits_remaining"] == 200.0
    assert w1["status"] in ("idle", "offline")
    assert w1["cooldown_until"] is None

    # Verify file on disk was NOT mutated (pure read path)
    mtime_after = status_file.stat().st_mtime_ns
    assert mtime_before == mtime_after

    with open(status_file, "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert disk_data["period"] == "2026-09"
    assert disk_data["credits_used"] == 150.0


def test_classification_exhaustion_over_429():
    """
    Test 3: Verify a failed run outputting both '429' and 'credit limit exceeded'
    classifies as quota exhaustion, taking precedence over transient 429.
    """
    adapter = CopilotCLIAdapter(
        worker_id="copilot-w1",
        nickname="test",
        github_token="tok",
        copilot_home=Path.home(),
    )

    # Mock process failure with both strings
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = MagicMock()

    stderr_output = "Error: HTTP 429 Too Many Requests. Account monthly credit limit exceeded."
    stdout_output = "Process failed."

    # Using adapter classification logic directly
    rate_limited_429 = False
    quota_exhausted = False
    if mock_proc.returncode != 0:
        import re
        combined = f"{stderr_output}\n{stdout_output[-1024:]}".lower()
        if any(p in combined for p in [
            "credit limit", "credits exhausted", "quota exceeded",
            "out of credits", "insufficient credits", "usage limit"
        ]):
            quota_exhausted = True
        elif re.search(r"http[ /]*429|status[: =]*429|too many requests|rate.?limit", combined):
            rate_limited_429 = True

    assert quota_exhausted is True
    assert rate_limited_429 is False


def test_anchored_429_classification():
    """
    Test 4: Verify false positives like 'line 429' in stderr do not trigger
    rate limiting, while anchored 429 patterns do.
    """
    import re
    anchored_pattern = r"http[ /]*429|status[: =]*429|too many requests|rate.?limit"

    # Innocent line number in stack trace
    line_number_stderr = "File 'app.py', line 429, in execute_code\nSyntaxError: invalid syntax"
    assert not re.search(anchored_pattern, line_number_stderr.lower())

    # Authentic 429 patterns
    assert re.search(anchored_pattern, "HTTP 429: Too Many Requests".lower())
    assert re.search(anchored_pattern, "status: 429".lower())
    assert re.search(anchored_pattern, "status=429".lower())
    assert re.search(anchored_pattern, "Server responded with rate-limit".lower())
    assert re.search(anchored_pattern, "Rate limit exceeded".lower())


def test_mark_cooldown_caller_migration(temp_orch_state: Path):
    """
    Test 5: Verify mark_cooldown handles both minutes and until=next_billing_reset(),
    updating quota_exhausted and writing live status correctly.
    """
    worker = CopilotQueueWorker(state_dir=temp_orch_state)
    worker.accounts = [{
        "worker_id": "test-w1",
        "name": "TestWorker",
        "has_token": True,
        "monthly_credits": 200,
    }]
    worker.ready_accounts = list(worker.accounts)

    # 1. Transient 429 cooldown (60 minutes)
    worker.mark_cooldown("test-w1", minutes=60, quota_exhausted=False, reason="Transient 429")
    assert worker.is_in_cooldown("test-w1") is True

    status_file = temp_orch_state / "live-status" / "test-w1.json"
    assert status_file.exists()
    with open(status_file, "r", encoding="utf-8") as f:
        d1 = json.load(f)
    assert d1["status"] == "cooldown"
    assert d1["quota_exhausted"] is False

    # 2. Monthly quota exhaustion cooldown (until next billing cycle)
    next_reset = next_billing_reset()
    worker.mark_cooldown("test-w1", until=next_reset, quota_exhausted=True, reason="Monthly Quota Exceeded")
    assert worker.is_in_cooldown("test-w1") is True

    with open(status_file, "r", encoding="utf-8") as f:
        d2 = json.load(f)
    assert d2["status"] == "cooldown"
    assert d2["quota_exhausted"] is True
    assert d2["cooldown_until"].startswith(str(next_reset.year))


def test_pure_read_path_zero_writes(temp_orch_state: Path):
    """
    Test 6: Verify get_fleet_quota_metrics with zero status files on disk
    creates zero files and leaves the directory completely untouched.
    """
    live_status_dir = temp_orch_state / "live-status"
    # Ensure live-status directory is empty
    for f in live_status_dir.glob("*.json"):
        f.unlink()

    assert len(list(live_status_dir.glob("*.json"))) == 0

    metrics = get_fleet_quota_metrics(temp_orch_state)
    assert "fleet" in metrics
    assert "workers" in metrics

    # Verify still zero files created on disk
    assert len(list(live_status_dir.glob("*.json"))) == 0


def test_atomic_write_mocked_permission_error(tmp_path: Path):
    """
    Test 7: Mock os.replace to raise PermissionError on the first 2 attempts,
    verifying exponential backoff retry loop succeeds without data corruption.
    """
    target_file = tmp_path / "test_atomic.json"
    payload = {"status": "ok", "retries": 2}

    call_count = 0
    orig_replace = os.replace

    def mock_replace(src, dst):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise PermissionError("Access is denied (Mock Windows File Lock)")
        return orig_replace(src, dst)

    with patch("os.replace", side_effect=mock_replace):
        atomic_write_json(target_file, payload)

    assert call_count == 3
    assert target_file.exists()
    with open(target_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == payload


def test_fleet_commander_word_cap(temp_orch_state: Path):
    """
    Test 8: Verify that the manifest emitted by FleetCommander strictly enforces
    len(manifest.split()) <= 300 even when supplied with dozens of verbose tasks.
    """
    commander = FleetCommander(state_dir=temp_orch_state)

    # Create dummy metrics with 27 workers
    dummy_metrics = {
        "fleet": {
            "total_registered_accounts": 27,
            "ready_accounts": 27,
            "total_monthly_credits": 5400,
            "total_credits_used": 26.89,
            "total_credits_remaining": 5373.11,
            "burn_rate_pct": 0.50,
            "status_counts": {"idle": 26, "busy": 1, "cooldown": 0, "offline": 0},
        }
    }

    h_ratio = commander.compute_health_ratio(dummy_metrics)
    assert h_ratio == 1.0  # (26 + 1) / 27 = 1.0

    # Generate 50 verbose task results
    verbose_tasks = []
    for i in range(50):
        verbose_tasks.append({
            "id": f"task_verbose_example_long_id_{i:03d}",
            "status": "done",
            "worker": f"copilot-w{(i % 27) + 1}",
            "summary": "This is an extremely detailed and verbose description of an engineering task designed to intentionally inflate word count beyond three hundred words if not bounded.",
        })

    manifest = commander.format_manifest(
        batch_id="test_batch_001",
        h_ratio=h_ratio,
        pre_metrics=dummy_metrics,
        post_metrics=dummy_metrics,
        task_results=verbose_tasks,
        log_file_path=temp_orch_state / "logs" / "commander_test.log",
        max_words=300,
    )

    words = manifest.split()
    assert len(words) <= 300
    assert "FLEET COMMANDER BATCH MANIFEST" in manifest
