import pytest
from tools.fast_intent_router import route_intent, _compute_time_allocation


def test_compute_time_allocation():
    alloc_micro = _compute_time_allocation("status", "ENGINEERING_DEV", "Tier 1", "DIRECT_FAST")
    assert alloc_micro["tier"] == "T0_MICRO"
    assert alloc_micro["estimated_duration_s"] == 12
    assert alloc_micro["execution_route"] == "LOCAL_SLM"

    alloc_fleet = _compute_time_allocation("dispatch swarm across workers", "SWARM_ORCHESTRATION", "Tier 2", "FLEET_SWARM")
    assert alloc_fleet["tier"] == "T3_LONG"
    assert alloc_fleet["estimated_duration_s"] == 240
    assert alloc_fleet["execution_route"] == "FLEET_WORKER"


def test_route_intent_heuristic_fallback(monkeypatch):
    # Ensure is_online is False so it tests heuristic fallback cleanly regardless of background LM Studio state
    import client.local_llm
    monkeypatch.setattr(client.local_llm, "is_online", lambda *args, **kwargs: False)

    result = route_intent("Scaffold IOE semester IV-II notes for CE 752 and share via super-nlm")
    assert "archetype" in result
    assert result["archetype"] == "RESEARCH_ACADEMIC"
    assert "time_allocation" in result
    assert "auto_tier" in result
    assert result["auto_tier"] in ["efficiency", "balance", "intelligence"]
    assert "recommended_copilot_model" in result
    
    ta = result["time_allocation"]
    assert "tier" in ta
    assert "estimated_duration_s" in ta
    assert "timeout_ceiling_s" in ta
    assert "cpm_weight" in ta
    assert "execution_route" in ta
    assert ta["estimated_duration_s"] > 0
    assert ta["timeout_ceiling_s"] >= 30
    assert "latency_ms" in result


def test_route_intent_lm_studio_success(monkeypatch):
    import client.local_llm
    monkeypatch.setattr(client.local_llm, "is_online", lambda *args, **kwargs: True)
    
    mock_payload = '```json\n{"archetype": "FRONTEND_PRODUCT", "matrix_cell": "(V0, R1)", "policy": "BRANCH_GUARD"}\n```'
    monkeypatch.setattr(client.local_llm, "chat_completion", lambda *args, **kwargs: mock_payload)

    result = route_intent("Build responsive navbar with anthracite palette")
    assert result["archetype"] == "FRONTEND_PRODUCT"
    assert result["policy"] == "BRANCH_GUARD"
    assert "lm_studio_" in result["source"]
    assert "time_allocation" in result

