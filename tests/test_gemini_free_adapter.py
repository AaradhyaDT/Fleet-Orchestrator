"""Unit tests for GeminiFreeAdapter."""

import pytest
from client.adapters.gemini_free_adapter import GeminiFreeAdapter


def test_gemini_free_adapter_init():
    adapter = GeminiFreeAdapter(
        worker_id="gemini-free-1",
        nickname="Gemini Free Worker",
        api_key="your_gemini_api_key_here",
        model="gemini-3.8-flash",
    )
    assert adapter.worker_id == "gemini-free-1"
    assert adapter.nickname == "Gemini Free Worker"
    assert adapter.model == "gemini-3.8-flash"
    assert "writing" in adapter.capabilities
    assert "qa" in adapter.capabilities
    assert "research" in adapter.capabilities


@pytest.mark.asyncio
async def test_gemini_free_adapter_health():
    adapter = GeminiFreeAdapter(
        worker_id="gemini-free-1",
        nickname="Gemini Free Worker",
        api_key="your_gemini_api_key_here",
    )
    assert await adapter.check_health() is True
