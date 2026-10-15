"""Unit tests for CodexCLIAdapter in Fleet-Orchestrator."""

from __future__ import annotations

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from client.adapters.codex_cli_adapter import CodexCLIAdapter


@pytest.mark.asyncio
async def test_codex_cli_init():
    adapter = CodexCLIAdapter(
        worker_id="codex-w1",
        nickname="Codex Worker 1",
        codex_path="codex.exe",
        workspace_dir="F:/tmp/workspace",
        model="gpt-5.4",
        reasoning_effort="high",
        timeout=120.0,
    )
    assert adapter.worker_id == "codex-w1"
    assert adapter.codex_path == "codex.exe"
    assert adapter.model == "gpt-5.4"
    assert adapter.reasoning_effort == "high"
    assert adapter.timeout == 120.0
    assert "code" in adapter.capabilities


@pytest.mark.asyncio
async def test_codex_cli_build_command():
    adapter = CodexCLIAdapter(
        worker_id="codex-w1",
        nickname="Codex Worker 1",
        codex_path="codex.exe",
        model="o3-mini",
        reasoning_effort="medium",
        sandbox="workspace-write",
        approval_policy="never",
    )
    cmd = adapter.build_cli_command("Fix unit tests")
    assert cmd[0] == "codex.exe"
    assert "--ask-for-approval" in cmd
    assert "never" in cmd
    assert "exec" in cmd
    assert "--json" in cmd
    assert "--sandbox" in cmd
    assert "workspace-write" in cmd
    assert "--model" in cmd
    assert "o3-mini" in cmd
    assert 'model_reasoning_effort="medium"' in cmd[-2]
    assert cmd[-1] == "Fix unit tests"


@pytest.mark.asyncio
async def test_codex_cli_parse_jsonl_output():
    jsonl_output = (
        '{"type": "item.completed", "item": {"type": "assistant_message", "text": "Step 1 complete"}}\n'
        '{"type": "item.completed", "item": {"type": "assistant_message", "text": "All tests passed"}}\n'
    )
    msg, failure = CodexCLIAdapter._parse_jsonl_output(jsonl_output)
    assert failure is None
    assert "Step 1 complete" in msg
    assert "All tests passed" in msg


@pytest.mark.asyncio
async def test_codex_cli_parse_jsonl_error():
    jsonl_output = (
        '{"type": "error", "message": "Rate limit exceeded"}\n'
    )
    msg, failure = CodexCLIAdapter._parse_jsonl_output(jsonl_output)
    assert failure == "Rate limit exceeded"


@pytest.mark.asyncio
async def test_codex_cli_check_health_success():
    adapter = CodexCLIAdapter(worker_id="codex-w1", nickname="Codex Worker 1")
    with patch("client.adapters.codex_cli_adapter.spawn_background", new_callable=AsyncMock) as mock_spawn, \
         patch("client.adapters.codex_cli_adapter.communicate_background", new_callable=AsyncMock) as mock_comm:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_spawn.return_value = mock_proc
        assert await adapter.check_health() is True


@pytest.mark.asyncio
async def test_codex_cli_check_health_failure():
    adapter = CodexCLIAdapter(worker_id="codex-w1", nickname="Codex Worker 1")
    with patch("client.adapters.codex_cli_adapter.spawn_background", new_callable=AsyncMock) as mock_spawn:
        mock_spawn.side_effect = FileNotFoundError("codex not found")
        assert await adapter.check_health() is False


@pytest.mark.asyncio
async def test_codex_cli_execute_task_success():
    adapter = CodexCLIAdapter(
        worker_id="codex-w1",
        nickname="Codex Worker 1",
        workspace_dir="F:/tmp/workspace",
    )
    sample_jsonl = '{"type": "item.completed", "item": {"type": "assistant_message", "text": "Resolved task successfully"}}\n'

    with patch("client.adapters.codex_cli_adapter.spawn_background", new_callable=AsyncMock) as mock_spawn, \
         patch("client.adapters.codex_cli_adapter.communicate_background", new_callable=AsyncMock) as mock_comm:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_spawn.return_value = mock_proc
        mock_comm.return_value = (sample_jsonl.encode("utf-8"), b"")

        res = await adapter.execute_task(
            task_id="task-test-01",
            spec="Refactor module",
            stage="code",
            context={},
        )
        assert res["success"] is True
        assert res["error"] is None
        assert "Resolved task successfully" in res["result_text"]
