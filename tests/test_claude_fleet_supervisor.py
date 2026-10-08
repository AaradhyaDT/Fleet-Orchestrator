"""
test_claude_fleet_supervisor.py
-------------------------------
Unit tests for ClaudeFleetSupervisor:
- Profile discovery and stage affinity selection.
- Cooldown tracking and serial handoff.
- Mock execution and scratchpad integration.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from client.claude_fleet_supervisor import ClaudeFleetSupervisor, discover_claude_profiles
from client.scratchpad_manager import ScratchpadManager


@pytest.fixture
def mock_profiles():
    return [
        {
            "profile_id": "user1",
            "worker_id": "claude-user1",
            "nickname": "adevtmr",
            "role": "orchestrator",
            "preferred_model": "Sonnet 5",
            "cdp_port": 9222,
            "profile_path": "C:\\fake\\user1",
        },
        {
            "profile_id": "user2",
            "worker_id": "claude-user2",
            "nickname": "dev83",
            "role": "orchestrator",
            "preferred_model": "Sonnet 5",
            "cdp_port": 9223,
            "profile_path": "C:\\fake\\user2",
        },
        {
            "profile_id": "user4",
            "worker_id": "claude-user4",
            "nickname": "adtbei79001",
            "role": "worker_reviewer",
            "preferred_model": "Haiku 4.5",
            "cdp_port": 9225,
            "profile_path": "C:\\fake\\user4",
        },
    ]


def test_supervisor_initialization(mock_profiles):
    sup = ClaudeFleetSupervisor(profiles=mock_profiles)
    assert len(sup.adapters) == 3
    assert "claude-user1" in sup.adapters
    assert "claude-user4" in sup.adapters


def test_stage_affinity_selection(mock_profiles):
    sup = ClaudeFleetSupervisor(profiles=mock_profiles)

    # Stage 'plan' should select an orchestrator profile
    plan_worker = sup.select_best_profile("plan")
    assert plan_worker is not None
    assert plan_worker.worker_id in ("claude-user1", "claude-user2")

    # Stage 'qa_review' should select the reviewer profile
    qa_worker = sup.select_best_profile("qa_review")
    assert qa_worker is not None
    assert qa_worker.worker_id == "claude-user4"


def test_cooldown_tracking_and_rotation(mock_profiles):
    sup = ClaudeFleetSupervisor(profiles=mock_profiles)

    assert not sup.is_in_cooldown("claude-user1")
    sup.mark_cooldown("claude-user1", minutes=30)
    assert sup.is_in_cooldown("claude-user1")

    # Now selecting for 'plan' should rotate to user2!
    next_worker = sup.select_best_profile("plan")
    assert next_worker is not None
    assert next_worker.worker_id == "claude-user2"


@pytest.mark.asyncio
async def test_execute_stage_with_handoff_success(mock_profiles, tmp_path):
    scratch_mgr = ScratchpadManager(base_dir=tmp_path / "scratchpads")
    with patch("client.claude_fleet_supervisor.scratchpad_mgr", scratch_mgr):
        sup = ClaudeFleetSupervisor(profiles=mock_profiles)

        job_id = "job_cdp_001"
        await scratch_mgr.init_scratchpad(job_id, "Test Job", "Test spec")

        # Mock adapter 1 to fail with rate limit, adapter 2 to succeed
        sup.adapters["claude-user1"].check_health = AsyncMock(return_value=True)
        sup.adapters["claude-user1"].execute_task = AsyncMock(return_value={
            "success": False,
            "error": "Usage limit reached for this profile",
            "summary": "",
            "result_text": "",
        })

        sup.adapters["claude-user2"].check_health = AsyncMock(return_value=True)
        sup.adapters["claude-user2"].execute_task = AsyncMock(return_value={
            "success": True,
            "error": None,
            "summary": "Plan generated",
            "result_text": "### Architectural Plan\n1. Module A\n2. Module B",
        })

        res = await sup.execute_stage_with_handoff(job_id, "plan", "Implement feature")
        assert res["success"] is True
        assert "Architectural Plan" in res["result_text"]

        # User1 was placed in cooldown
        assert sup.is_in_cooldown("claude-user1")

        # Verify scratchpad has the plan appended under section 2
        content = await scratch_mgr.read_scratchpad(job_id)
        assert "Architectural Plan" in content
        assert "claude-user2" in content
