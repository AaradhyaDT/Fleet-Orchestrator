"""Tests for Azmuth Control Barrier Function (CBF) Governor."""

from pathlib import Path
from tools.azmuth_cbf_governor import AzmuthCBFGovernor


def test_evaluate_node_barrier_safe():
    governor = AzmuthCBFGovernor(z_safety_limit=3.0)
    node_data = {
        "current_value": 1.2,
        "z_score": 0.5,
        "state_label": "HOMEOSTATIC_EQUILIBRIUM",
    }
    evaluation = governor.evaluate_node_barrier("TEST_NODE", "u0_test", node_data)
    assert evaluation.is_safe is True
    assert evaluation.h_value > 0.0
    assert evaluation.recommended_mitigation is None


def test_evaluate_node_barrier_breach_and_mitigation():
    governor = AzmuthCBFGovernor(z_safety_limit=3.0)
    node_data = {
        "current_value": 95.0,
        "z_score": 3.8,
        "state_label": "CRITICAL_NOCICEPTIVE_SPIKE",
    }
    evaluation = governor.evaluate_node_barrier("HOST_CPU_PACKAGE_TEMP_C", "u6_energy", node_data)
    assert evaluation.is_safe is False
    assert evaluation.h_value < 0.0
    assert evaluation.recommended_mitigation == "THROTTLE_WORKER_POOL"


def test_audit_and_govern_sweep(tmp_path: Path):
    governor = AzmuthCBFGovernor(state_dir=tmp_path)
    universes_data = {
        "u6_energy": {
            "nodes": {
                "NORMAL_NODE": {"current_value": 10.0, "z_score": 0.2, "state_label": "HOMEOSTATIC_EQUILIBRIUM"},
                "HOT_NODE": {"current_value": 85.0, "z_score": 3.2, "state_label": "CRITICAL_NOCICEPTIVE_SPIKE"},
            }
        }
    }
    telemetry = governor.audit_and_govern(universes_data)
    assert telemetry["status"] == "NOCICEPTIVE_BREACH"
    assert telemetry["total_nodes_evaluated"] == 2
    assert telemetry["breached_nodes_count"] == 1
    assert len(telemetry["active_mitigation_actions"]) == 1
    assert telemetry["active_mitigation_actions"][0]["action_type"] == "THROTTLE_WORKER_POOL"
