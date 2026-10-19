"""Unit tests for tools/celestialsapien_gate.py (Alien X Consensus Gate)."""

from pathlib import Path
from tools.celestialsapien_gate import (
    CelestialsapienGate,
)


def test_celestialsapien_gate_unanimous_consensus(tmp_path: Path):
    """When Bellicus, Serena, and Azmuth CBF Barrier agree, action is granted."""
    gate = CelestialsapienGate(state_dir=tmp_path)
    ctx = {
        "has_rollback_plan": True,
        "backup_verified": True,
        "backward_compatible": True,
        "ecosystem_notified": True,
        "documentation_updated": True,
        "blast_radius": "LOW",
    }
    barrier_telemetry = {
        "min_barrier_h_value": 4.5,
        "system_invariance_satisfied": True,
    }

    decision = gate.arbitrate(
        action_type="GIT_FORCE_PUSH",
        target_payload="origin/main",
        context=ctx,
        barrier_override=barrier_telemetry,
    )

    assert decision.consensus_granted is True
    assert "CELESTIALSAPIEN_CONSENSUS_ACHIEVED" in decision.reason
    assert decision.bellicus.approved is True
    assert decision.serena.approved is True
    assert decision.azmuth_barrier.satisfied is True
    assert decision.azmuth_barrier.h_value == 4.5


def test_celestialsapien_gate_bellicus_adversarial_veto(tmp_path: Path):
    """Bellicus dissents if there is no rollback plan or verified backup on destructive action."""
    gate = CelestialsapienGate(state_dir=tmp_path)
    ctx = {
        "has_rollback_plan": False,  # Missing rollback!
        "backup_verified": False,
        "backward_compatible": True,
        "ecosystem_notified": True,
    }
    barrier_telemetry = {
        "min_barrier_h_value": 5.0,
        "system_invariance_satisfied": True,
    }

    decision = gate.arbitrate(
        action_type="CLOUD_CLUSTER_DELETE",
        target_payload="us-east-1-prod-cluster",
        context=ctx,
        barrier_override=barrier_telemetry,
    )

    assert decision.consensus_granted is False
    assert "BELLICUS_DISSENT" in decision.reason
    assert decision.bellicus.approved is False
    assert len(decision.bellicus.edge_risks_identified) >= 2


def test_celestialsapien_gate_serena_harmony_veto(tmp_path: Path):
    """Serena dissents if backward compatibility or architectural harmony is breached."""
    gate = CelestialsapienGate(state_dir=tmp_path)
    ctx = {
        "has_rollback_plan": True,
        "backup_verified": True,
        "backward_compatible": False,  # Breaking change!
        "ecosystem_notified": False,
    }
    barrier_telemetry = {
        "min_barrier_h_value": 8.0,
        "system_invariance_satisfied": True,
    }

    decision = gate.arbitrate(
        action_type="BREAKING_REFACTOR",
        target_payload="core/api/v2",
        context=ctx,
        barrier_override=barrier_telemetry,
    )

    assert decision.consensus_granted is False
    assert "SERENA_DISSENT" in decision.reason
    assert decision.serena.approved is False
    assert "backward compatibility" in decision.serena.edge_risks_identified[0]


def test_celestialsapien_gate_azmuth_barrier_veto(tmp_path: Path):
    """Azmuth Barrier hard vetoes execution when h(x) < 0, regardless of voice harmony."""
    gate = CelestialsapienGate(state_dir=tmp_path)
    ctx = {
        "has_rollback_plan": True,
        "backup_verified": True,
        "backward_compatible": True,
        "ecosystem_notified": True,
        "documentation_updated": True,
    }
    barrier_telemetry = {
        "min_barrier_h_value": -2.35,  # Barrier breach!
        "system_invariance_satisfied": False,
        "min_node": "THERMAL_CPU_ZONE",
    }

    decision = gate.arbitrate(
        action_type="DATABASE_DROP",
        target_payload="analytics_shadow_db",
        context=ctx,
        barrier_override=barrier_telemetry,
    )

    assert decision.consensus_granted is False
    assert "AZMUTH_BARRIER_BREACH" in decision.reason
    assert decision.azmuth_barrier.satisfied is False
    assert decision.azmuth_barrier.h_value == -2.35
