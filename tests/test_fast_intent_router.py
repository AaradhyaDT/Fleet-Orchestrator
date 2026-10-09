import pytest
from tools.fast_intent_router import route_intent, _compute_time_allocation


def test_compute_time_allocation():
    alloc_micro = _compute_time_allocation("status", "ENGINEERING_DEV", "Tier 1", "DIRECT_FAST")
    assert alloc_micro["tier"] == "T0_MICRO"
    assert alloc_micro["estimated_duration_s"] == 12
    assert alloc_micro["execution_route"] == "DIRECT_FAST"

    alloc_fleet = _compute_time_allocation("dispatch swarm across workers", "SWARM_ORCHESTRATION", "Tier 2", "FLEET_SWARM")
    assert alloc_fleet["tier"] == "T3_LONG"
    assert alloc_fleet["estimated_duration_s"] == 240
    assert alloc_fleet["execution_route"] == "FLEET_WORKER"


def test_route_intent_heuristic_fallback():
    result = route_intent("Scaffold IOE semester IV-II notes for CE 752 and share via super-nlm")
    assert "archetype" in result
    assert result["archetype"] == "RESEARCH_ACADEMIC"
    assert "time_allocation" in result
    
    ta = result["time_allocation"]
    assert "tier" in ta
    assert "estimated_duration_s" in ta
    assert "timeout_ceiling_s" in ta
    assert "cpm_weight" in ta
    assert "execution_route" in ta
    assert ta["estimated_duration_s"] > 0
    assert ta["timeout_ceiling_s"] >= 30
    assert "latency_ms" in result
