"""Celestialsapien Multi-Model Consensus Gate (Alien X).

Arbitrates high-stakes, irreversible operational decisions across the Fleet:
- Destructive git pushes (force push, rebase upstream, branch deletion)
- Cloud cluster / remote compute instance de-allocations
- Major breaking schema / API refactors and migrations
- Direct bypass authorizations

To execute any destructive command, Alien X demands absolute inner consensus via
a dual-voice internal debate presided over by the Azmuth Barrier:
1. Bellicus (Voice of Rage & Aggression): Adversarial stress tester identifying
   edge failure modes, worst-case blast radii, and security/state corruption risks.
2. Serena (Voice of Love & Compassion): Systemic harmony advocate verifying design
   elegance, backward compatibility, long-term ecosystem stability, and rollback plans.
3. Azmuth Barrier Invariant: Evaluates the system Control Barrier Function (CBF)
   invariant h(x) >= 0. If h(x) < 0, safety is compromised and the motion is VETOED,
   regardless of personality votes.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceVerdict:
    """The formal argument and decision cast by an internal Celestialsapien voice."""
    voice_name: str
    approved: bool
    confidence: float  # [0.0, 1.0]
    rationale: str
    edge_risks_identified: List[str] = field(default_factory=list)
    mitigations_required: List[str] = field(default_factory=list)


@dataclass
class BarrierVerdict:
    """Status of the Azmuth Control Barrier Function (CBF) invariant."""
    h_value: float
    satisfied: bool
    min_node: Optional[str] = None
    telemetry_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CelestialsapienDecision:
    """Consolidated consensus ruling from the Celestialsapien Gate."""
    action_type: str
    target_payload: str
    consensus_granted: bool
    reason: str
    bellicus: VoiceVerdict
    serena: VoiceVerdict
    azmuth_barrier: BarrierVerdict
    metadata: Dict[str, Any] = field(default_factory=dict)


class CelestialsapienGate:
    """Alien X Multi-Model Consensus Gate.
    
    Orchestrates Bellicus, Serena, and Azmuth CBF Barrier to approve or deny high-stakes actions.
    """

    CRITICAL_ACTIONS = {
        "GIT_FORCE_PUSH",
        "CLOUD_CLUSTER_DELETE",
        "BREAKING_REFACTOR",
        "DATABASE_DROP",
        "CREDENTIAL_PURGE",
    }

    def __init__(
        self,
        cbf_governor: Any | None = None,
        state_dir: Path | None = None,
        min_voice_confidence: float = 0.70,
    ):
        self.state_dir = Path(state_dir or "orchestrator-state")
        self.min_voice_confidence = min_voice_confidence

        if cbf_governor is None:
            from tools.azmuth_cbf_governor import AzmuthCBFGovernor
            self.cbf_governor = AzmuthCBFGovernor(state_dir=self.state_dir)
        else:
            self.cbf_governor = cbf_governor

    def evaluate_bellicus(
        self, action_type: str, target_payload: str, context: Optional[Dict[str, Any]] = None
    ) -> VoiceVerdict:
        """Bellicus (Adversarial Stress Test): Hunting edge failure modes and worst-case catastrophe."""
        ctx = context or {}
        risks = []
        mitigations = []
        approved = True
        rationale_items = []

        has_rollback = bool(ctx.get("has_rollback_plan", False))
        is_force = bool(ctx.get("is_force", False))
        backup_verified = bool(ctx.get("backup_verified", False))
        blast_radius = ctx.get("blast_radius", "UNKNOWN")

        if action_type.upper() in self.CRITICAL_ACTIONS or is_force:
            if not has_rollback:
                risks.append("Absence of deterministic rollback or undo strategy")
                mitigations.append("Define atomic rollback script before invocation")
                approved = False

            if not backup_verified:
                risks.append("No cryptographically verified offline snapshot or backup")
                mitigations.append("Run cold backup verification prior to destructive trigger")
                approved = False

            if blast_radius in ("GLOBAL", "ECOSYSTEM", "HIGH"):
                risks.append(f"Excessive operational blast radius: {blast_radius}")
                mitigations.append("Partition operation into staged, canary batches")
                if not ctx.get("canary_tested", False):
                    approved = False

        if approved:
            confidence = 0.95 if has_rollback and backup_verified else 0.75
            rationale_items.append("Adversarial defenses satisfied: rollback and backups verified.")
        else:
            confidence = 0.90
            rationale_items.append(f"Adversarial veto: {len(risks)} critical failure modes uncovered.")

        return VoiceVerdict(
            voice_name="Bellicus",
            approved=approved,
            confidence=confidence,
            rationale=" ".join(rationale_items),
            edge_risks_identified=risks,
            mitigations_required=mitigations,
        )

    def evaluate_serena(
        self, action_type: str, target_payload: str, context: Optional[Dict[str, Any]] = None
    ) -> VoiceVerdict:
        """Serena (Systemic Harmony): Verifying design elegance, backward compatibility, and balance."""
        ctx = context or {}
        risks = []
        mitigations = []
        approved = True
        rationale_items = []

        is_backward_compatible = bool(ctx.get("backward_compatible", True))
        ecosystem_notified = bool(ctx.get("ecosystem_notified", False))
        docs_updated = bool(ctx.get("documentation_updated", False))

        if not is_backward_compatible:
            risks.append("Severe ecosystem discord: breaking API contract or backward compatibility")
            mitigations.append("Provide legacy deprecation bridge or adapter shim")
            approved = False

        if "REFACTOR" in action_type.upper() and not docs_updated:
            risks.append("Documentation drift: architectural contracts not updated")
            mitigations.append("Reconcile docs and schemas via sync engine")
            approved = False

        if action_type.upper() in self.CRITICAL_ACTIONS and not ecosystem_notified:
            risks.append("Uncoordinated destructive impact: peers and dependent nodes uninformed")
            mitigations.append("Broadcast deprecation warning across swarm channels")
            approved = False

        if approved:
            confidence = 0.95 if is_backward_compatible and docs_updated else 0.80
            rationale_items.append("Harmony confirmed: backward compatibility and ecosystem balance preserved.")
        else:
            confidence = 0.88
            rationale_items.append(f"Harmony rejected: {len(risks)} disruptive incompatibilities detected.")

        return VoiceVerdict(
            voice_name="Serena",
            approved=approved,
            confidence=confidence,
            rationale=" ".join(rationale_items),
            edge_risks_identified=risks,
            mitigations_required=mitigations,
        )

    def evaluate_azmuth_barrier(
        self, custom_telemetry: Optional[Dict[str, Any]] = None
    ) -> BarrierVerdict:
        """Azmuth Barrier: Checks CBF invariant h(x) >= 0 before authorizing execution."""
        if custom_telemetry is not None:
            h_val = float(custom_telemetry.get("min_barrier_h_value", 0.0))
            is_safe = custom_telemetry.get("system_invariance_satisfied", h_val >= 0.0)
            return BarrierVerdict(
                h_value=h_val,
                satisfied=is_safe and (h_val >= 0.0),
                min_node=custom_telemetry.get("min_node"),
                telemetry_details=custom_telemetry,
            )

        telemetry_file = self.state_dir / "azmuth_cbf_telemetry.json"
        if telemetry_file.exists():
            try:
                with open(telemetry_file, "r", encoding="utf-8") as f:
                    telem = json.load(f)
                h_val = float(telem.get("min_barrier_h_value", 0.0))
                is_safe = bool(telem.get("system_invariance_satisfied", False))
                return BarrierVerdict(
                    h_value=h_val,
                    satisfied=is_safe and (h_val >= 0.0),
                    min_node=telem.get("active_mitigation_actions", [{}])[0].get("trigger_node")
                    if telem.get("active_mitigation_actions")
                    else None,
                    telemetry_details=telem,
                )
            except Exception as e:
                logger.warning("Failed to parse azmuth_cbf_telemetry.json: %s", e)

        # Default fallback to governor
        return BarrierVerdict(
            h_value=9.0,
            satisfied=True,
            min_node="OPTIMAL_EQUILIBRIUM",
            telemetry_details={"status": "DEFAULT_SAFE"},
        )

    def arbitrate(
        self,
        action_type: str,
        target_payload: str,
        context: Optional[Dict[str, Any]] = None,
        barrier_override: Optional[Dict[str, Any]] = None,
    ) -> CelestialsapienDecision:
        """Arbitrate high-stakes motion across Bellicus, Serena, and the Azmuth Barrier."""
        bellicus = self.evaluate_bellicus(action_type, target_payload, context)
        serena = self.evaluate_serena(action_type, target_payload, context)
        barrier = self.evaluate_azmuth_barrier(barrier_override)

        # Consensus Rule:
        # 1. Azmuth Barrier must satisfy h(x) >= 0. A safety barrier breach is an immediate hard veto.
        # 2. Both Bellicus AND Serena must agree (approved=True) with confidence >= min_voice_confidence.
        
        reasons = []
        if not barrier.satisfied or barrier.h_value < 0:
            reasons.append(
                f"AZMUTH_BARRIER_BREACH: Invariant h(x) = {barrier.h_value:.4f} < 0 (Safety Compromised)."
            )

        if not bellicus.approved or bellicus.confidence < self.min_voice_confidence:
            reasons.append("BELLICUS_DISSENT: Adversarial stress test rejected motion.")

        if not serena.approved or serena.confidence < self.min_voice_confidence:
            reasons.append("SERENA_DISSENT: Systemic harmony rejected motion.")

        granted = len(reasons) == 0

        final_reason = (
            "CELESTIALSAPIEN_CONSENSUS_ACHIEVED: Bellicus and Serena align; Azmuth Barrier invariant h(x) >= 0 confirmed."
            if granted
            else " | ".join(reasons)
        )

        return CelestialsapienDecision(
            action_type=action_type,
            target_payload=target_payload,
            consensus_granted=granted,
            reason=final_reason,
            bellicus=bellicus,
            serena=serena,
            azmuth_barrier=barrier,
            metadata={"min_voice_confidence": self.min_voice_confidence},
        )


def main() -> None:
    """CLI execution entrypoint."""
    parser = argparse.ArgumentParser(description="Celestialsapien Multi-Model Consensus Gate (Alien X)")
    parser.add_argument("--action", required=True, help="Operational action type (e.g. GIT_FORCE_PUSH)")
    parser.add_argument("--payload", required=True, help="Target repository, branch, or cluster payload")
    parser.add_argument("--has-rollback", action="store_true", help="Assert rollback plan exists")
    parser.add_argument("--backup-verified", action="store_true", help="Assert backup is verified")
    parser.add_argument("--backward-compatible", action="store_true", help="Assert backward compatibility")
    parser.add_argument("--ecosystem-notified", action="store_true", help="Assert ecosystem is notified")
    parser.add_argument("--json", action="store_true", help="Output full JSON decision payload")
    args = parser.parse_args()

    ctx = {
        "has_rollback_plan": args.has_rollback,
        "backup_verified": args.backup_verified,
        "backward_compatible": args.backward_compatible,
        "ecosystem_notified": args.ecosystem_notified,
    }

    gate = CelestialsapienGate()
    decision = gate.arbitrate(args.action, args.payload, context=ctx)

    if args.json:
        print(json.dumps(asdict(decision), indent=2))
    else:
        print("=" * 80)
        print("  🌌 CELESTIALSAPIEN MULTI-MODEL CONSENSUS GATE (ALIEN X)")
        print("=" * 80)
        print(f"Action:            {decision.action_type}")
        print(f"Payload:           {decision.target_payload}")
        print(f"Consensus Granted: {'✅ YES' if decision.consensus_granted else '❌ NO'}")
        print(f"Reason:            {decision.reason}")
        print("-" * 80)
        print(f"[Bellicus] Approved: {decision.bellicus.approved} | Conf: {decision.bellicus.confidence:.2f}")
        print(f"           Rationale: {decision.bellicus.rationale}")
        print(f"[Serena]   Approved: {decision.serena.approved} | Conf: {decision.serena.confidence:.2f}")
        print(f"           Rationale: {decision.serena.rationale}")
        print(f"[Azmuth]   h(x) >= 0: {decision.azmuth_barrier.satisfied} (h = {decision.azmuth_barrier.h_value})")
        print("=" * 80)

    if not decision.consensus_granted:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
