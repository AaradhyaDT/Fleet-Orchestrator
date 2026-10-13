from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from client import process_runtime
from client.cli_accounts import reported_retry_after


def test_background_flags_exclude_detachment_and_new_console():
    options = process_runtime.background_options()
    if sys.platform == "win32":
        assert options["creationflags"] == subprocess.CREATE_NO_WINDOW
        assert not options["creationflags"] & (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_CONSOLE)
        assert options["startupinfo"].wShowWindow == subprocess.SW_HIDE
    else:
        assert options == {}


def test_trace_records_sites_without_secrets_or_arguments(tmp_path, monkeypatch):
    target = tmp_path / "trace.jsonl"
    monkeypatch.setenv("FLEET_PROCESS_TRACE", str(target))
    completed = process_runtime.run_background(
        [sys.executable, "-c", "print('secret-value')"], capture_output=True, check=True
    )
    assert completed.stdout.strip() == b"secret-value"
    events = [json.loads(line) for line in target.read_text().splitlines()]
    assert [event["phase"] for event in events] == ["launch", "exit"]
    assert "secret-value" not in target.read_text()
    assert "print(" not in target.read_text()


@pytest.mark.asyncio
async def test_cancellation_stops_child_before_returning():
    proc = await process_runtime.spawn_background(
        sys.executable,
        "-c",
        "import time; time.sleep(30)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    task = asyncio.create_task(process_runtime.communicate_background(proc, 60))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert proc.returncode is not None


def test_provider_reported_retry_after_has_explicit_units():
    assert reported_retry_after('{"error":{"headers":{"retry-after":"120"}}}') == 120
    assert reported_retry_after('{"retry_after_seconds":45}') == 45
    assert reported_retry_after('{"retryAfter":120000}') is None
    assert reported_retry_after("malformed output") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("execution_started", [True, False])
async def test_supervisor_holds_partial_execution_for_recovery(tmp_path, monkeypatch, execution_started):
    from client import fleet_supervisor

    monkeypatch.setenv("FLEET_ACCOUNTS_HOME", str(tmp_path / "private"))
    monkeypatch.setattr(fleet_supervisor, "POLL_INTERVAL_SECONDS", 0.01)
    client = AsyncMock()
    stop = asyncio.Event()
    responses = []

    async def post(url, **kwargs):
        responses.append((url, kwargs.get("json")))
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = (
            {"claim_token": "claim", "task": {"id": "t", "stage": "code", "spec": "edit"}}
            if url.endswith("/acquire")
            else {}
        )
        if url.endswith("/block") or url.endswith("/release"):
            stop.set()
        return response

    client.post.side_effect = post
    adapter = AsyncMock()
    adapter.check_health.return_value = True
    adapter.execute_task.return_value = {
        "success": False,
        "error": "429 rate limit",
        "execution_started": execution_started,
        "auth_profile": "a",
        "result_text": "partial",
    }
    await asyncio.wait_for(
        fleet_supervisor.run_worker_loop("w", "worker", "writer", "codex_cli", adapter, client, stop), timeout=2
    )
    assert any(url.endswith("/block") for url, _ in responses) is execution_started
    assert any(url.endswith("/release") for url, _ in responses) is not execution_started
    if execution_started:
        checkpoints = list((tmp_path / "private" / "task-attempts").glob("*.json"))
        assert len(checkpoints) == 1
        assert json.loads(checkpoints[0].read_text())["auth_profile"] == "a"
