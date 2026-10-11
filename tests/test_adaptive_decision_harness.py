"""Unit tests for adaptive_decision_harness and Banker's memory concurrency."""

import pytest
from tools.adaptive_decision_harness import AdaptiveDecisionEngine, verify_l3_local_llm_client, verify_l5_ram_and_banker_gates


def test_banker_concurrency_reserve_floor():
    assert AdaptiveDecisionEngine.compute_banker_concurrency(1800) == 0
    assert AdaptiveDecisionEngine.compute_banker_concurrency(2048) == 0
    assert AdaptiveDecisionEngine.compute_banker_concurrency(2304) == 1
    assert AdaptiveDecisionEngine.compute_banker_concurrency(3072) == 4
    assert AdaptiveDecisionEngine.compute_banker_concurrency(4096) == 8
    assert AdaptiveDecisionEngine.compute_banker_concurrency(8192) == 24
    assert AdaptiveDecisionEngine.compute_banker_concurrency(12288) == 27
    assert AdaptiveDecisionEngine.compute_banker_concurrency(32768) == 27  # velocity cap


def test_tier_zero_fast_path_detection():
    fast = AdaptiveDecisionEngine.detect_fast_path("run pytest tests/")
    assert fast is not None
    assert fast["is_fast_path"] is True
    assert fast["backend"] == "shell"
    assert fast["execution_tier"] == "Tier 0"

    non_fast = AdaptiveDecisionEngine.detect_fast_path("Implement new authentication route with jwt tokens")
    assert non_fast is None


def test_decision_engine_matrix_volume_and_criticality():
    # 2 files, leaf code -> (V0, R0)
    v, count = AdaptiveDecisionEngine.compute_volume(["file1.py", "file2.py"])
    assert v == "V0"
    assert count == 2

    # >15 files -> V2
    v_large, count_large = AdaptiveDecisionEngine.compute_volume([f"f_{i}.py" for i in range(18)])
    assert v_large == "V2"
    assert count_large == 18

    # access.js or AGENTS.md -> R2
    r_crit, score = AdaptiveDecisionEngine.compute_criticality(["access.js"], "update access.js")
    assert r_crit == "R2"
    assert score >= 0.35


def test_l3_local_llm_fixtures():
    res = verify_l3_local_llm_client()
    assert res["passed"] is True
    assert res["fixture_pass_count"] == "6/6"


def test_l5_ram_bands_validation():
    res = verify_l5_ram_and_banker_gates()
    assert res["passed"] is True
    assert len(res["simulation_bands"]) == 7
