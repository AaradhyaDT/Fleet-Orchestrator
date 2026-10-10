import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from client.adapters.agy_adapter import AGYCLIAdapter


@pytest.mark.asyncio
async def test_agy_adapter_init():
    adapter = AGYCLIAdapter(
        worker_id="agy-w1",
        nickname="Lead",
        agy_path="agy.exe",
        model="gemini-3.8-flash",
        effort="high",
    )
    assert adapter.worker_id == "agy-w1"
    assert adapter.nickname == "Lead"
    assert adapter.model == "gemini-3.8-flash"
    assert adapter.effort == "high"
    assert adapter.dangerously_skip_permissions is True


@pytest.mark.asyncio
async def test_agy_adapter_command_building():
    adapter = AGYCLIAdapter(
        worker_id="agy-w2",
        nickname="Craftsman",
        agy_path="agy.exe",
        model="gemini-3.8-flash",
        effort="high",
        dangerously_skip_permissions=True,
    )
    cmd = adapter._build_command("test prompt")
    assert "agy.exe" in cmd[0]
    assert "-p" in cmd
    assert "test prompt" in cmd
    assert "--dangerously-skip-permissions" in cmd
    assert "--model" in cmd
    assert "gemini-3.8-flash" in cmd
    assert "--output-format" in cmd
    assert "json" in cmd


@pytest.mark.asyncio
async def test_agy_adapter_execute_task_success():
    adapter = AGYCLIAdapter(
        worker_id="agy-w3",
        nickname="QA",
        agy_path="agy.exe",
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (
        b'{"response": "Task completed successfully"}',
        b"",
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await adapter.execute_task(
            task_id="t-1",
            spec="Perform QA audit",
            stage="qa",
            context={},
        )
        assert result["success"] is True
        assert result["result_text"] == "Task completed successfully"
        assert "Completed qa via AGY" in result["summary"]


@pytest.mark.asyncio
async def test_agy_adapter_health_check_success():
    adapter = AGYCLIAdapter(
        worker_id="agy-w1",
        nickname="Lead",
        agy_path="agy.exe",
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Usage of agy.exe:\n", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        healthy = await adapter.check_health()
        assert healthy is True
