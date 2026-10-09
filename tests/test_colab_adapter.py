import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from client.adapters.colab_adapter import ColabCloudAdapter


def test_colab_adapter_init():
    adapter = ColabCloudAdapter(worker_id="colab-w1", default_gpu="L4")
    assert adapter.worker_id == "colab-w1"
    assert adapter.nickname == "colab-cloud"
    assert adapter.default_gpu == "L4"
    assert "cloud_gpu" in adapter.capabilities
    assert "colab" in adapter.capabilities


@pytest.mark.asyncio
async def test_colab_adapter_health_check_token_found():
    adapter = ColabCloudAdapter()
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", unittest.mock.mock_open(read_data='{"access_token": "mock-token"}')):
        health = await adapter.check_health()
        assert health is True


@pytest.mark.asyncio
async def test_colab_adapter_health_check_token_missing():
    adapter = ColabCloudAdapter()
    with patch("os.path.exists", return_value=False), \
         patch("asyncio.create_subprocess_exec", side_effect=Exception("not found")):
        health = await adapter.check_health()
        assert health is False


@pytest.mark.asyncio
async def test_colab_adapter_execute_code_lifecycle():
    adapter = ColabCloudAdapter()
    
    mock_new = AsyncMock()
    mock_new.communicate.return_value = (b"[colab] READY", b"")
    mock_new.returncode = 0

    mock_exec = AsyncMock()
    mock_exec.communicate.return_value = (b"Output: 42", b"")
    mock_exec.returncode = 0

    mock_stop = AsyncMock()
    mock_stop.communicate.return_value = (b"[colab] Stopped", b"")
    mock_stop.returncode = 0

    with patch("asyncio.create_subprocess_exec", side_effect=[mock_new, mock_exec, mock_stop]) as mock_subproc:
        res = await adapter.execute_task(
            task_id="test-1234",
            spec="Run computation",
            stage="compute",
            context={"code": "print('Output: 42')", "gpu": "T4"}
        )

        assert res["success"] is True
        assert "Output: 42" in res["result_text"]
        assert mock_subproc.call_count == 3


@pytest.mark.asyncio
async def test_colab_adapter_enforces_cleanup_on_error():
    adapter = ColabCloudAdapter()
    
    mock_new = AsyncMock()
    mock_new.communicate.return_value = (b"[colab] READY", b"")
    mock_new.returncode = 0

    mock_exec = AsyncMock()
    mock_exec.communicate.side_effect = asyncio.TimeoutError("Timeout executing remote cell")

    mock_stop = AsyncMock()
    mock_stop.communicate.return_value = (b"[colab] Stopped", b"")
    mock_stop.returncode = 0

    with patch("asyncio.create_subprocess_exec", side_effect=[mock_new, mock_exec, mock_stop]) as mock_subproc:
        res = await adapter.execute_task(
            task_id="test-5678",
            spec="Hanging task",
            stage="compute",
            context={"code": "while True: pass"}
        )

        assert res["success"] is False
        # Verify colab stop was still executed in finally block
        assert mock_subproc.call_count == 3
        # Check that the last call was 'stop'
        last_call_args = mock_subproc.call_args_list[-1][0]
        assert "stop" in last_call_args
