"""Unit tests for OllamaLocalAdapter."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from client.adapters.ollama_local_adapter import OllamaLocalAdapter


def test_ollama_local_adapter_init():
    adapter = OllamaLocalAdapter(
        worker_id="ollama-w1",
        nickname="Ollama Worker",
        base_url="http://localhost:11434",
        model="qwen2.5:7b",
    )
    assert adapter.worker_id == "ollama-w1"
    assert adapter.nickname == "Ollama Worker"
    assert adapter.model == "qwen2.5:7b"
    assert "research" in adapter.capabilities
    assert "writing" in adapter.capabilities


@pytest.mark.asyncio
async def test_ollama_local_adapter_health():
    adapter = OllamaLocalAdapter("ollama-w1", "Ollama Worker")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        assert await adapter.check_health() is True

    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        assert await adapter.check_health() is False


@pytest.mark.asyncio
async def test_ollama_local_adapter_execution_success():
    adapter = OllamaLocalAdapter("ollama-w1", "Ollama Worker")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "response": "Extracted key facts from local model output.",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await adapter.execute_task(
            task_id="task-456",
            spec="Summarize research notes",
            stage="research",
            context={},
        )
        assert res["success"] is True
        assert res["result_text"] == "Extracted key facts from local model output."
        assert res["error"] is None


@pytest.mark.asyncio
async def test_ollama_local_adapter_execution_error():
    adapter = OllamaLocalAdapter("ollama-w1", "Ollama Worker")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await adapter.execute_task(
            task_id="task-456",
            spec="Summarize research notes",
            stage="research",
            context={},
        )
        assert res["success"] is False
        assert "Ollama HTTP 500" in res["error"]
