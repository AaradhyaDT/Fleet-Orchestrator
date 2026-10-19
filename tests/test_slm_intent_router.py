"""Tests for Local SLM Intent Router."""

from tools.slm_intent_router import SLMIntentRouter


def test_classify_intent_heuristic_audit():
    router = SLMIntentRouter()
    res = router.classify_intent("Audit the system for memory leaks and check control barrier function safety")
    assert res.intent_codon == "SYSTEM_AUDIT"
    assert res.target_skill == "cyber-forensics"
    assert res.latency_ms < 50.0


def test_classify_intent_heuristic_simulation():
    router = SLMIntentRouter()
    res = router.classify_intent("Run 30-day SDE stochastic simulation on A100 hyperburst")
    assert res.intent_codon == "FORESIGHT_SIMULATION"
    assert res.target_skill == "adaptive-workflow"
    assert res.latency_ms < 50.0


def test_classify_intent_heuristic_hardware():
    router = SLMIntentRouter()
    res = router.classify_intent("Calibrate ESP32 FreeRTOS queue and compute TinyML INT8 fall latency")
    assert res.intent_codon == "HARDWARE_SYNTH"
    assert res.target_skill == "edge-ai-model-forge"
    assert res.latency_ms < 50.0


def test_classify_intent_heuristic_vcs():
    router = SLMIntentRouter()
    res = router.classify_intent("Sync repository commits and open PR under issue #192")
    assert res.intent_codon == "VCS_SYNC"
    assert res.target_skill == "github-workflow"
    assert res.latency_ms < 50.0
