import pytest
from tools.npu_engine import TriHardwareEngine


def test_npu_engine_hardware_status():
    status = TriHardwareEngine.get_hardware_status()
    assert "platform" in status
    assert "Meteor Lake" in status["platform"]
    assert "intel_ai_boost_npu" in status
    assert "intel_arc_gpu" in status
    assert "intel_cpu_avx_vnni" in status
    assert "runtimes" in status
    assert "active_priority_target" in status["runtimes"]


def test_npu_engine_fallback_generation():
    engine = TriHardwareEngine()
    # When no model is loaded and LM Studio is offline, should gracefully fall back to Level 4
    res = engine.generate("test prompt")
    assert "text" in res
    assert "device" in res
    assert "latency_ms" in res
    assert "tier" in res
    assert res["latency_ms"] >= 0
