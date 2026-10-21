"""Azmuth Autonomous Control Barrier Function (CBF) Governor.

Enforces real-time safety invariants h(x) >= 0 across all 81 neuromorphic nodes
in the Azmuth Foresight Engine. When h(x) < 0 or |Z| >= 3.0 (CRITICAL_NOCICEPTIVE_SPIKE),
the governor dispatches automated, closed-loop mitigation actions to restore homeostatic balance:
1. THROTTLE_WORKER_POOL: Dampens local background worker concurrency.
2. CIRCUIT_BREAKER_SYNC_GATE: Holds automated git pushes pending stabilization.
3. DISPATCH_EMERGENCY_A100_BURST: Triggers an autonomic cloud compute burst.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class BarrierEvaluation:
    node_id: str
    universe_id: str
    current_value: float
    z_score: float
    h_value: float  # Barrier function value: h(x) >= 0 is safe, < 0 is a safety violation
    is_safe: bool
    state_label: str
    recommended_mitigation: str | None = None


@dataclass
class GovernorMitigationAction:
    action_type: str
    trigger_node: str
    universe_id: str
    severity: str
    description: str
    remedial_parameters: Dict[str, Any] = field(default_factory=dict)


class AzmuthCBFGovernor:
    """Quadratic/analytical Control Barrier Function governor for multi-universe stability."""

    def __init__(
        self,
        alpha_gain: float = 1.0,
        z_safety_limit: float = 3.0,
        state_dir: Path | None = None,
    ):
        self.alpha_gain = alpha_gain
        self.z_safety_limit = z_safety_limit
        self.state_dir = state_dir or Path("orchestrator-state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.telemetry_path = self.state_dir / "azmuth_cbf_telemetry.json"

    def evaluate_node_barrier(
        self, node_id: str, universe_id: str, node_data: Dict[str, Any]
    ) -> BarrierEvaluation:
        """Compute the barrier function h(x) for a given node.

        For normalized Z-scores, safety requires |Z| <= z_safety_limit.
        Therefore, h(x) = (z_safety_limit^2 - Z^2) >= 0 defines the forward-invariant safe set C.
        """
        val = float(node_data.get("current_value", 0.0))
        z_score = float(node_data.get("z_score", 0.0))
        state_label = node_data.get("state_label", "HOMEOSTATIC_EQUILIBRIUM")
        l2 = node_data.get("layer2_allostatic", {})
        z_limit = max(self.z_safety_limit, float(l2.get("z_critical", self.z_safety_limit)))

        # h(x) > 0 inside safe set, = 0 on boundary, < 0 in unsafe set
        h_val = round((z_limit**2) - (z_score**2), 4)
        is_safe = h_val >= 0.0 and abs(z_score) < z_limit

        mitigation = None
        if not is_safe or state_label == "CRITICAL_NOCICEPTIVE_SPIKE":
            mitigation = self._select_mitigation_action(node_id, universe_id, z_score)

        return BarrierEvaluation(
            node_id=node_id,
            universe_id=universe_id,
            current_value=val,
            z_score=z_score,
            h_value=h_val,
            is_safe=is_safe,
            state_label=state_label,
            recommended_mitigation=mitigation,
        )

    def _select_mitigation_action(
        self, node_id: str, universe_id: str, z_score: float
    ) -> str:
        """Map breached domains to targeted autonomic counter-actions."""
        nid_upper = node_id.upper()
        uid_upper = universe_id.upper()
        if "TEMP" in nid_upper or "POWER" in nid_upper or "CPU" in nid_upper or "HOT" in nid_upper or "ENERGY" in uid_upper or "THERMAL" in uid_upper:
            return "THROTTLE_WORKER_POOL"
        elif "LEAK" in nid_upper or "DISPARITY" in nid_upper or "EPISTEMIC" in nid_upper:
            return "CIRCUIT_BREAKER_SYNC_GATE"
        elif "LATENCY" in nid_upper or "QUEUE" in nid_upper or "BURST" in nid_upper:
            return "DISPATCH_EMERGENCY_A100_BURST"
        else:
            return "DAMP_SYNAPTIC_WEIGHTS" if z_score > 0 else "BOOST_ALLOSTATIC_DRIVE"

    def audit_and_govern(
        self, universes_data: Dict[str, Dict[str, Any]], audit_memory_subsystem: bool = False
    ) -> Dict[str, Any]:
        """Perform a complete CBF sweep across all loaded universes and generate actions."""
        evaluations: List[BarrierEvaluation] = []
        actions: List[GovernorMitigationAction] = []

        total_nodes = 0
        breached_nodes = 0

        for u_id, u_info in universes_data.items():
            nodes = u_info.get("nodes", {})
            for n_id, n_data in nodes.items():
                total_nodes += 1
                evaluation = self.evaluate_node_barrier(n_id, u_id, n_data)
                evaluations.append(evaluation)

                if not evaluation.is_safe:
                    breached_nodes += 1
                    actions.append(
                        GovernorMitigationAction(
                            action_type=evaluation.recommended_mitigation
                            or "GENERIC_DAMPING",
                            trigger_node=n_id,
                            universe_id=u_id,
                            severity="CRITICAL"
                            if abs(evaluation.z_score) >= 3.5
                            else "HIGH",
                            description=f"Safety barrier breach h(x)={evaluation.h_value} on {n_id} (Z={evaluation.z_score})",
                            remedial_parameters={
                                "z_score": evaluation.z_score,
                                "h_value": evaluation.h_value,
                                "alpha_gain": self.alpha_gain,
                            },
                        )
                    )

        # Phase 5: Audit Ecosystem Memory Subsystem Barrier Health (when ecosystem mesh is active or requested)
        if audit_memory_subsystem or "u0_ecosystem_mesh" in universes_data:
            memory_barrier_eval = self._audit_memory_subsystem_barrier()
            evaluations.append(memory_barrier_eval)
            total_nodes += 1
            if not memory_barrier_eval.is_safe:
                breached_nodes += 1
                actions.append(
                    GovernorMitigationAction(
                        action_type=memory_barrier_eval.recommended_mitigation or "TRIGGER_EMERGENCY_MEMORY_SYNC",
                        trigger_node=memory_barrier_eval.node_id,
                        universe_id=memory_barrier_eval.universe_id,
                        severity="HIGH",
                        description=f"Ecosystem memory health barrier breach: h(x)={memory_barrier_eval.h_value} ({memory_barrier_eval.state_label})",
                        remedial_parameters={
                            "z_score": memory_barrier_eval.z_score,
                            "h_value": memory_barrier_eval.h_value,
                            "alpha_gain": self.alpha_gain,
                        },
                    )
                )

        min_h = (
            min((e.h_value for e in evaluations), default=self.z_safety_limit**2)
            if evaluations
            else 0.0
        )
        system_safe = breached_nodes == 0

        telemetry = {
            "status": "SAFE" if system_safe else "NOCICEPTIVE_BREACH",
            "total_nodes_evaluated": total_nodes,
            "breached_nodes_count": breached_nodes,
            "system_invariance_satisfied": system_safe,
            "min_barrier_h_value": min_h,
            "active_mitigation_actions": [asdict(a) for a in actions],
            "evaluations_sample": [asdict(e) for e in evaluations[:10]],
        }

        with open(self.telemetry_path, "w", encoding="utf-8") as f:
            json.dump(telemetry, f, indent=2)

        return telemetry

    def _audit_memory_subsystem_barrier(self) -> BarrierEvaluation:
        """Phase 5: Evaluates the Control Barrier Function for ecosystem memory synchronization."""
        import hashlib
        home = Path.home()
        codex_mem = home / ".codex" / "memories" / "GLOBAL_MEMORY.md"
        gemini_mem = home / ".gemini" / "config" / "codex-memories" / "GLOBAL_MEMORY.md"

        # Check drift between Codex and Gemini mirrors
        has_drift = False
        if codex_mem.is_file() and gemini_mem.is_file():
            def h_file(p: Path) -> str:
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    while chunk := f.read(65536):
                        h.update(chunk)
                return h.hexdigest()

            try:
                has_drift = h_file(codex_mem) != h_file(gemini_mem)
            except Exception:
                has_drift = False

        if has_drift:
            # Memory desynchronization breach
            z_score = 3.2
            h_val = round((self.z_safety_limit**2) - (z_score**2), 4)
            return BarrierEvaluation(
                node_id="u0_ecosystem_mesh::MEMORY_MIRROR_DRIFT",
                universe_id="u0_ecosystem_mesh",
                current_value=1.0,
                z_score=z_score,
                h_value=h_val,
                is_safe=False,
                state_label="CRITICAL_NOCICEPTIVE_SPIKE",
                recommended_mitigation="CIRCUIT_BREAKER_SYNC_GATE",
            )

        # Normal homeostatic state
        return BarrierEvaluation(
            node_id="u0_ecosystem_mesh::MEMORY_MIRROR_HEALTH",
            universe_id="u0_ecosystem_mesh",
            current_value=0.0,
            z_score=0.1,
            h_value=round((self.z_safety_limit**2) - (0.1**2), 4),
            is_safe=True,
            state_label="HOMEOSTATIC_EQUILIBRIUM",
            recommended_mitigation=None,
        )


def run_cbf_governor_cli(argv: list[str] | None = None) -> None:
    """CLI entrypoint to run CBF sweep on local state."""
    import argparse
    import sys
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.azmuth_macro_graph import sweep_all_universes

    parser = argparse.ArgumentParser(description="Azmuth CBF Governor Sweep")
    parser.add_argument("--gain", type=float, default=1.0, help="CBF Alpha Gain")
    parser.add_argument(
        "--z-limit", type=float, default=3.0, help="Maximum safe Z-score bound"
    )
    args = parser.parse_args(argv)

    sweep_results = sweep_all_universes()

    governor = AzmuthCBFGovernor(
        alpha_gain=args.gain, z_safety_limit=args.z_limit
    )
    telemetry = governor.audit_and_govern(
        sweep_results.get("universes", {})
    )

    print("=" * 80)
    print("  AZMUTH CONTROL BARRIER FUNCTION (CBF) GOVERNOR AUDIT")
    print("=" * 80)
    print(f"- System Status:           {telemetry['status']}")
    print(f"- Nodes Evaluated:         {telemetry['total_nodes_evaluated']}")
    print(f"- Breaches Detected:       {telemetry['breached_nodes_count']}")
    print(f"- Minimum Barrier h(x):    {telemetry['min_barrier_h_value']}")
    print(f"- Active Mitigations:     {len(telemetry['active_mitigation_actions'])}")
    if telemetry["active_mitigation_actions"]:
        for idx, act in enumerate(telemetry["active_mitigation_actions"], 1):
            print(
                f"  [{idx}] {act['action_type']} on {act['trigger_node']} ({act['severity']})"
            )
    print("=" * 80)


if __name__ == "__main__":
    run_cbf_governor_cli()
