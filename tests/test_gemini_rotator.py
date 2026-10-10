from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from google.genai import errors

from client.adapters.gemini_fleet_rotator import GeminiKeyRotator, GeminiKeySlot


def test_gemini_rotator_initialization():
    rotator = GeminiKeyRotator(api_keys=["key_A", "key_B", "key_C"])
    assert rotator.total_keys == 3
    assert rotator.healthy_keys == 3
    assert len(rotator._slots) == 3
    assert rotator._slots[0].masked_key == "key_...ey_A" or rotator._slots[0].key_id == "gemini-key-1"


@pytest.mark.asyncio
async def test_gemini_rotator_round_robin_selection():
    rotator = GeminiKeyRotator(api_keys=["key_1", "key_2", "key_3"])
    
    slot1 = await rotator.get_next_slot()
    slot2 = await rotator.get_next_slot()
    slot3 = await rotator.get_next_slot()
    slot4 = await rotator.get_next_slot()
    
    assert slot1.api_key == "key_1"
    assert slot2.api_key == "key_2"
    assert slot3.api_key == "key_3"
    assert slot4.api_key == "key_1"  # Cycles back


@pytest.mark.asyncio
async def test_gemini_rotator_burst_cooldown():
    rotator = GeminiKeyRotator(api_keys=["key_1", "key_2"])
    
    # Mark key 1 in cooldown
    rotator.mark_burst_cooldown("gemini-key-1", cooldown_seconds=10.0, error_msg="Mock 429")
    assert rotator.healthy_keys == 1
    
    # Next slot must skip key 1 and return key 2
    slot = await rotator.get_next_slot()
    assert slot.api_key == "key_2"
    
    # If key 2 is also in cooldown, both are cooling down
    rotator.mark_burst_cooldown("gemini-key-2", cooldown_seconds=0.1)
    # Fast forward time to test auto-recovery
    slot_1 = rotator._slots[0]
    slot_1.cooldown_until = time.time() - 1.0  # Expired
    assert slot_1.is_available is True
    assert rotator.healthy_keys >= 1


@pytest.mark.asyncio
async def test_gemini_rotator_execute_with_retry_on_429():
    rotator = GeminiKeyRotator(api_keys=["key_fail", "key_success"])
    
    # Setup call_fn that fails on key_fail and succeeds on key_success
    call_counts = {"key_fail": 0, "key_success": 0}

    async def mock_call(client, slot: GeminiKeySlot):
        call_counts[slot.api_key] += 1
        if slot.api_key == "key_fail":
            # Simulate 429 RESOURCE_EXHAUSTED APIError
            mock_err = errors.APIError(429, "RESOURCE_EXHAUSTED: rate limit exceeded")
            raise mock_err
        return "SUCCESS_DATA"

    result = await rotator.execute_with_retry(mock_call)
    
    assert result == "SUCCESS_DATA"
    assert call_counts["key_fail"] == 1
    assert call_counts["key_success"] == 1
    # Key fail should now be in burst cooldown
    assert rotator._slots[0].status == "BURST_COOLDOWN"
    assert rotator.healthy_keys == 1


def test_gemini_rotator_status_telemetry():
    rotator = GeminiKeyRotator(api_keys=["k1", "k2"])
    rotator._slots[0].total_calls = 5
    rotator._slots[0].total_tokens = 1200
    
    status = rotator.get_status()
    assert status["provider"] == "google_gemini_fleet"
    assert status["total_keys"] == 2
    assert status["healthy_keys"] == 2
    assert status["pooled_rpm_capacity"] == 30  # 2 * 15
    assert status["total_calls_served"] == 5
    assert status["total_tokens_served"] == 1200
    assert len(status["keys"]) == 2
