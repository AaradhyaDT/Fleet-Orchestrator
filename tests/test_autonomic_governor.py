"""tests/test_autonomic_governor.py
----------------------------------
Unit test suite verifying the Azmuth Autonomic Trigger engine and closed-loop mitigation invariants.
"""

import json
from pathlib import Path
import pytest

from tools.azmuth_autonomic_trigger import AzmuthAutonomicTrigger


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Path:
    state_dir = tmp_path / "orchestrator-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def test_autonomic_nominal_state(temp_state_dir: Path):
    """When h(x) is high and safe, no mitigation is triggered."""
    trigger = AzmuthAutonomicTrigger(threshold_h=0.20, state_dir=temp_state_dir, dry_run=True)
    cbf_telemetry = {
        "status": "SAFE",
        "system_invariance_satisfied": True,
        "min_barrier_h_value": 8.5,
        "active_mitigation_actions": [],
    }
    verdict = trigger.evaluate_and_dispatch(custom_cbf_telemetry=cbf_telemetry)
    assert not verdict.mitigation_required
    assert verdict.action_type == "NONE"
    assert verdict.dispatch_success
    assert "NOMINAL" in verdict.summary


def test_autonomic_breach_trigger_dry_run(temp_state_dir: Path):
    """When h(x) < 0.20, the trigger activates and consults CelestialsapienGate."""
    trigger = AzmuthAutonomicTrigger(threshold_h=0.20, state_dir=temp_state_dir, dry_run=True)
    cbf_telemetry = {
        "status": "NOCICEPTIVE_BREACH",
        "system_invariance_satisfied": False,
        "min_barrier_h_value": 0.05,
        "active_mitigation_actions": [
            {
                "action_type": "THROTTLE_WORKER_POOL",
                "trigger_node": "u6_cpu_thermal_celsius",
                "severity": "CRITICAL",
                "description": "Thermal breach",
            }
        ],
    }
    verdict = trigger.evaluate_and_dispatch(custom_cbf_telemetry=cbf_telemetry)
    assert verdict.mitigation_required
    assert verdict.action_type == "THROTTLE_WORKER_POOL"
    assert verdict.target_node == "u6_cpu_thermal_celsius"
    assert verdict.simulated
    assert verdict.dispatch_success
    assert trigger.log_path.exists()


def test_autonomic_insufficient_reserve_blocks_cloud(temp_state_dir: Path):
    """If Colab balance falls below reserve floor, cloud dispatch is strictly blocked."""
    # Write empty or low balance cache
    bal_file = temp_state_dir / "colab_balance_cache.json"
    with open(bal_file, "w", encoding="utf-8") as f:
        json.dump({"balance_units": 10.0}, f)

    trigger = AzmuthAutonomicTrigger(
        threshold_h=0.20,
        min_cu_reserve=50.0,
        state_dir=temp_state_dir,
        dry_run=False,
    )
    cbf_telemetry = {
        "status": "NOCICEPTIVE_BREACH",
        "system_invariance_satisfied": False,
        "min_barrier_h_value": -0.15,
        "active_mitigation_actions": [
            {
                "action_type": "DISPATCH_EMERGENCY_A100_BURST",
                "trigger_node": "u2_vram_saturation_pct",
                "severity": "CRITICAL",
                "description": "VRAM overflow",
            }
        ],
    }
    verdict = trigger.evaluate_and_dispatch(custom_cbf_telemetry=cbf_telemetry)
    assert verdict.mitigation_required
    assert not verdict.compute_reserve_verified
    assert not verdict.dispatch_success
    assert "VETOED" in verdict.summary
