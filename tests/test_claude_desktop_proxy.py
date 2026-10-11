"""Unit tests for ClaudeDesktopProxyAdapter."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from client.adapters.claude_desktop_proxy import ClaudeDesktopProxyAdapter


@pytest.mark.asyncio
async def test_claude_desktop_proxy_init():
    adapter = ClaudeDesktopProxyAdapter("claude-p1", "Claude Profile 1", model="claude-3-5-sonnet")
    assert adapter.worker_id == "claude-p1"
    assert adapter.nickname == "Claude Profile 1"
    assert "writing" in adapter.capabilities
    assert "code" in adapter.capabilities
    assert adapter.model == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_claude_desktop_proxy_health():
    adapter = ClaudeDesktopProxyAdapter("claude-p1", "Claude Profile 1")
    assert await adapter.check_health() is True


@pytest.mark.asyncio
async def test_claude_desktop_proxy_execution_simulation():
    adapter = ClaudeDesktopProxyAdapter(
        "claude-p1",
        "Claude Profile 1",
        api_key=None,
        execution_mode="SIMULATION",
    )
    res = await adapter.execute_task(
        task_id="task-123",
        spec="Write markdown summary",
        stage="writing",
        context={},
    )
    assert res["success"] is True
    assert "[SIMULATION]" in res["summary"]


@pytest.mark.asyncio
async def test_claude_desktop_proxy_execution_api_mock():
    adapter = ClaudeDesktopProxyAdapter(
        "claude-p1",
        "Claude Profile 1",
        api_key="your_api_key_here",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": "Generated response from mock Claude API"}],
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await adapter.execute_task(
            task_id="task-123",
            spec="Draft technical spec",
            stage="writing",
            context={},
        )
        assert res["success"] is True
        assert res["result_text"] == "Generated response from mock Claude API"
