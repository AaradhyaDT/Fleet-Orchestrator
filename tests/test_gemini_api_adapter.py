from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from google.genai import errors, types

from client.adapters.gemini_api_adapter import (
    DEPRECATED_MODEL_MAP,
    GeminiAPIAdapter,
)
from client.adapters.gemini_free_adapter import GeminiFreeAdapter


def test_gemini_adapter_init_defaults():
    adapter = GeminiAPIAdapter(
        worker_id="test_gemini_1",
        nickname="Gemini Test Worker",
        api_key="mock",
    )
    assert adapter.worker_id == "test_gemini_1"
    assert adapter.nickname == "Gemini Test Worker"
    assert adapter.model == "gemini-3.8-flash"
    assert "research" in adapter.capabilities
    assert "qa" in adapter.capabilities
    assert "code_review" in adapter.capabilities


def test_gemini_adapter_deprecated_model_translation():
    # Deprecated models automatically map to modern Gemini models
    adapter_flash = GeminiAPIAdapter(
        worker_id="w1",
        nickname="n1",
        api_key="mock",
        model="gemini-2.5-flash",
    )
    assert adapter_flash.model == "gemini-3.8-flash"

    adapter_pro = GeminiAPIAdapter(
        worker_id="w2",
        nickname="n2",
        api_key="mock",
        model="gemini-1.5-pro",
    )
    assert adapter_pro.model == "gemini-3.1-pro-preview"

    adapter_lite = GeminiAPIAdapter(
        worker_id="w3",
        nickname="n3",
        api_key="mock",
        model="gemini-3.5-flash-lite",
    )
    assert adapter_lite.model == "gemini-3.5-flash-lite"


@pytest.mark.asyncio
async def test_gemini_adapter_check_health():
    adapter_healthy = GeminiAPIAdapter("w", "n", api_key="valid")
    assert await adapter_healthy.check_health() is True

    adapter_unhealthy = GeminiAPIAdapter("w", "n", api_key="")
    assert await adapter_unhealthy.check_health() is False


@pytest.mark.asyncio
async def test_gemini_adapter_missing_api_key():
    adapter = GeminiAPIAdapter("w", "n", api_key="")
    res = await adapter.execute_task(
        task_id="t_missing",
        spec="Test spec",
        stage="research",
        context={},
    )
    assert res["success"] is False
    assert res["error"] == "Missing GEMINI_API_KEY"
    assert res["result_text"] == ""


@pytest.mark.asyncio
async def test_gemini_adapter_successful_execution_mocked():
    adapter = GeminiAPIAdapter("w", "n", api_key="mock", model="gemini-3.8-flash")

    mock_response = MagicMock()
    mock_response.text = "Comprehensive synthesis output."
    mock_meta = MagicMock()
    mock_meta.prompt_token_count = 120
    mock_meta.candidates_token_count = 350
    mock_meta.total_token_count = 470
    mock_response.usage_metadata = mock_meta

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    adapter._client = mock_client

    res = await adapter.execute_task(
        task_id="t_success",
        spec="Synthesize research papers",
        stage="research",
        context={"temperature": 0.4, "max_output_tokens": 2048},
    )

    assert res["success"] is True
    assert res["error"] is None
    assert res["result_text"] == "Comprehensive synthesis output."
    assert res["summary"] == "Completed research via gemini-3.8-flash"
    assert res["tokens"] == {
        "prompt": 120,
        "candidates": 350,
        "total": 470,
    }

    mock_client.aio.models.generate_content.assert_awaited_once()
    _, kwargs = mock_client.aio.models.generate_content.call_args
    assert kwargs["model"] == "gemini-3.8-flash"
    assert isinstance(kwargs["config"], types.GenerateContentConfig)
    assert kwargs["config"].temperature == 0.4
    assert kwargs["config"].max_output_tokens == 2048


@pytest.mark.asyncio
async def test_gemini_adapter_rate_limit_429_handling():
    adapter = GeminiAPIAdapter("w", "n", api_key="mock")

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=errors.APIError(429, "Resource exhausted (quota exceeded)")
    )
    adapter._client = mock_client

    res = await adapter.execute_task(
        task_id="t_429",
        spec="Heavy load",
        stage="writing",
        context={},
    )

    assert res["success"] is False
    assert res["error"] == "RATE_LIMIT_429"
    assert "Resource exhausted" in res.get("details", "")


@pytest.mark.asyncio
async def test_gemini_adapter_generic_apierror():
    adapter = GeminiAPIAdapter("w", "n", api_key="mock")

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=errors.APIError(500, "Internal Server Error")
    )
    adapter._client = mock_client

    res = await adapter.execute_task(
        task_id="t_500",
        spec="Test spec",
        stage="qa",
        context={},
    )

    assert res["success"] is False
    assert "APIError 500" in res["error"]


@pytest.mark.asyncio
async def test_gemini_adapter_generic_exception():
    adapter = GeminiAPIAdapter("w", "n", api_key="mock")

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Connection socket reset by peer")
    )
    adapter._client = mock_client

    res = await adapter.execute_task(
        task_id="t_err",
        spec="Test spec",
        stage="qa",
        context={},
    )

    assert res["success"] is False
    assert "Gemini execution error" in res["error"]
    assert "Connection socket reset by peer" in res["error"]


def test_gemini_free_adapter_inheritance():
    free_adapter = GeminiFreeAdapter(
        worker_id="free_01",
        nickname="Free Worker",
        api_key="mock",
        model="gemini-2.5-flash",
    )
    assert isinstance(free_adapter, GeminiAPIAdapter)
    # Automatically upgraded from 2.5 to 3.8
    assert free_adapter.model == "gemini-3.8-flash"
    assert free_adapter.worker_id == "free_01"


@pytest.mark.asyncio
async def test_gemini_free_adapter_invariant_b_compat():
    """Verify Invariant B (INV-WSR-002) behavior when executed with bad_key."""
    adapter = GeminiFreeAdapter(
        worker_id="test_gemini",
        nickname="Test Gemini",
        api_key="bad_key",
    )
    res = await adapter.execute_task(
        task_id="t_inv_b",
        spec="Test spec",
        stage="research",
        context={},
    )
    assert res["success"] is False
    assert res["error"] is not None
