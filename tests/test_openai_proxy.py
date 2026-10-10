from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from server.main import app
from client.adapters.gemini_fleet_rotator import GeminiKeyRotator, GeminiKeySlot


@pytest.fixture
def mock_rotator():
    rotator = GeminiKeyRotator(api_keys=["mock_key_1", "mock_key_2"])
    return rotator


@pytest.mark.asyncio
async def test_openai_proxy_models_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/v1/models")
        assert res.status_code == 200
        data = res.json()
        assert data["object"] == "list"
        model_ids = [m["id"] for m in data["data"]]
        assert "gemini-3.8-flash" in model_ids
        assert "gpt-4o" in model_ids


@pytest.mark.asyncio
async def test_openai_proxy_fleet_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/v1/fleet/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "gemini_fleet" in data
        assert "copilot_fleet" in data


@pytest.mark.asyncio
async def test_openai_proxy_chat_completions_non_streaming():
    mock_resp = MagicMock()
    mock_resp.text = "Hello from Antigravity Gemini Fleet!"
    mock_meta = MagicMock()
    mock_meta.total_token_count = 150
    mock_resp.usage_metadata = mock_meta

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

    with patch("server.api.routes_openai_proxy.get_gemini_rotator") as mock_get_rotator:
        rotator = GeminiKeyRotator(api_keys=["test_key"])
        slot = rotator._slots[0]
        slot._client = mock_client
        mock_get_rotator.return_value = rotator

        payload = {
            "model": "gemini-3.8-flash",
            "messages": [
                {"role": "system", "content": "You are a test assistant"},
                {"role": "user", "content": "Ping"},
            ],
            "stream": False,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post("/v1/chat/completions", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["object"] == "chat.completion"
            assert data["choices"][0]["message"]["content"] == "Hello from Antigravity Gemini Fleet!"
            assert data["usage"]["total_tokens"] == 150

        # Verify system prompt included Antigravity directives
        call_args = mock_client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert "Antigravity" in config.system_instruction
        assert "You are a test assistant" in config.system_instruction


@pytest.mark.asyncio
async def test_openai_proxy_chat_completions_streaming():
    mock_chunk1 = MagicMock()
    mock_chunk1.text = "Streaming "
    mock_chunk2 = MagicMock()
    mock_chunk2.text = "tokens."

    async def mock_stream_iter(*args, **kwargs):
        yield mock_chunk1
        yield mock_chunk2

    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(return_value=mock_stream_iter())

    with patch("server.api.routes_openai_proxy.get_gemini_rotator") as mock_get_rotator:
        rotator = GeminiKeyRotator(api_keys=["test_key"])
        slot = rotator._slots[0]
        slot._client = mock_client
        mock_get_rotator.return_value = rotator

        payload = {
            "model": "gpt-4o",  # Should translate to gemini-3.8-flash
            "messages": [{"role": "user", "content": "Stream test"}],
            "stream": True,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post("/v1/chat/completions", json=payload)
            assert res.status_code == 200
            body = res.text
            assert "data: " in body
            assert "Streaming " in body
            assert "tokens." in body
            assert "data: [DONE]" in body
