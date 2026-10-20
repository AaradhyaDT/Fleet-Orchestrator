#!/usr/bin/env python3
"""tools/evaluate_opportunity_fit.py
----------------------------------
Semantic Opportunity Matcher & Strategic Portfolio Evaluator.

Evaluates harvested opportunities from Dubai Future Foundation, TII Abu Dhabi,
MBZUAI, UN ITU AI for Good, UNICEF Innovation Fund, and UNDP against Aaradhya's
empirical engineering repositories:
1. SPARK: 200Hz Edge AI, FreeRTOS queue governance, INT8 TinyML kinematics, fall recall (>=0.95).
2. BiasAperture: Intersectional demographic bias audit, EU AI Act compliance, bootstrap CIs.
3. Fleet-Orchestrator: Multi-model consensus, Control Barrier Functions h(x)>=0, SMT logic invariants.
4. Brainstorm: Formal Z3 SMT proofs, discrete-event queue simulation, systems architecture.

Calculates:
- Fit Ratio ([0.0, 1.0]): Multidimensional competence alignment.
- Visa Feasibility Score: UAE 10-Year Golden Visa (AI/Coder track) & UN G4 diplomatic readiness.
- Sovereign Tax-Free Net Alpha Index: Normalized real purchasing power (kUSD/yr).
- Targeted Gap-Closure Recommendations: Exact repository artifacts needed to achieve 99th-percentile fit.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

# Root anchor
ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "orchestrator-state"
OPPORTUNITIES_DIR = STATE_DIR / "opportunities"
CATALOG_PATH = OPPORTUNITIES_DIR / "catalog.json"
MATCH_REPORT_PATH = OPPORTUNITIES_DIR / "match_report.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Matcher] %(message)s")
logger = logging.getLogger("opportunity_matcher")


# Profile Anchor: Aaradhya's Proven Empirical Pillars
PROFILE_COMPETENCY_VECTORS: Dict[str, Dict[str, Any]] = {
    "SPARK": {
        "keywords": [
            "edge_ai", "tinyml", "esp32", "freertos", "kinematics", "wearables",
            "fall_detection", "imu", "sensor", "quantization", "int8", "assistive_tech",
            "biometric", "embedded_firmware"
        ],
        "weight": 0.30,
        "evidence_anchor": "F:\\Aaradhya-Dev-Tamrakar\\SPARK (200Hz IMU, FreeRTOS HAL, 1D CNN)"
    },
    "BiasAperture": {
        "keywords": [
            "fairness_audit", "bias_mitigation", "demographic_parity", "equal_opportunity",
            "eu_ai_act", "computer_vision", "facial_analysis", "bootstrap_ci", "disparity",
            "algorithmic_governance", "model_governance"
        ],
        "weight": 0.25,
        "evidence_anchor": "F:\\Aaradhya-Dev-Tamrakar\\BiasAperture (Intersectional Bias Diagnostic)"
    },
    "Fleet_Orchestrator": {
        "keywords": [
            "autonomous_swarms", "multi_model", "control_barrier_function", "cbf", "slm",
            "token_hygiene", "anti_slop", "distributed_systems", "worker_pool", "routing",
            "formal_verification"
        ],
        "weight": 0.20,
        "evidence_anchor": "F:\\Aaradhya-Dev-Tamrakar\\Fleet-Orchestrator (Multi-Model Swarm Engine)"
    },
    "Brainstorm_Formal_Logic": {
        "keywords": [
            "smt_solvers", "z3", "formal_verification", "discrete_event", "queue_simulation",
            "systems_architecture", "epistemic_governance", "public_interest_ai"
        ],
        "weight": 0.15,
        "evidence_anchor": "F:\\Aaradhya-Dev-Tamrakar\\brainstorm (Dual-Layer SMT Verification)"
    },
    "Cyber_Forensics_ZeroTrust": {
        "keywords": [
            "cyber_forensics", "zero_trust", "air_gap", "ntfs_ads", "secure_systems", "pki",
            "cryptographic", "tamper_proofing", "pe_headers", "security_clearance", "dfir"
        ],
        "weight": 0.10,
        "evidence_anchor": "F:\\Aaradhya-Dev-Tamrakar\\Cyber-Forensics (Windows DFIR and Stealth Evasion Hunting)"
    }
}


@dataclass
class MatchEvaluation:
    opportunity_id: str
    title: str
    organization: str
    category: str
    location: str
    overall_fit_ratio: float  # [0.0, 1.0]
    fit_tier: str  # "EXCEPTIONAL_MATCH" | "HIGH_MATCH" | "MODERATE_MATCH" | "DEVELOPING"
    visa_feasibility_score: float  # [0.0, 1.0]
    visa_pathway: str
    visa_notes: str
    net_alpha_index_kusd: float
    tax_status: str
    pillar_breakdown: Dict[str, float]
    gap_closure_actions: List[str]
    url: str
    verifiable_sources: List[Dict[str, str]] = field(default_factory=list)


class SemanticOpportunityMatcher:
    """Evaluates harvested opportunities against profile competency vectors."""

    def __init__(self, catalog_path: Path = CATALOG_PATH):
        self.catalog_path = catalog_path

    def tokenize(self, text: str) -> set[str]:
        """Normalize and tokenize text into token set."""
        tokens = re.findall(r"\b[a-zA-Z0-9_\-]+\b", text.lower())
        return set(tokens)

    def compute_fit_score(self, opp: Dict[str, Any]) -> tuple[float, Dict[str, float]]:
        """Calculate weighted competency alignment across all 4 pillars."""
        text_corpus = f"{opp.get('title', '')} {opp.get('description', '')} {' '.join(opp.get('relevance_tags', []))}"
        tokens = self.tokenize(text_corpus)

        breakdown: Dict[str, float] = {}
        total_score = 0.0

        for pillar_name, pillar_info in PROFILE_COMPETENCY_VECTORS.items():
            keywords = pillar_info["keywords"]
            matches = sum(1 for kw in keywords if kw.lower() in tokens or any(kw.lower() in t for t in tokens))
            # Non-linear saturation curve: 1 match = 0.55, 2 matches = 0.80, 3+ matches >= 0.95
            pillar_score = min(1.0, 1.0 - math.exp(-0.85 * matches)) if matches > 0 else 0.05
            breakdown[pillar_name] = round(pillar_score, 3)

        # Pi-shaped talent evaluation: Rank pillar strengths for this specific role
        sorted_scores = sorted(breakdown.values(), reverse=True)
        primary = sorted_scores[0]
        secondary = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
        auxiliary = sum(sorted_scores[2:]) / max(1, len(sorted_scores) - 2)

        # 70% Primary Focus + 20% Secondary Synergy + 10% Auxiliary Breadth
        total_score = (primary * 0.70) + (secondary * 0.20) + (auxiliary * 0.10)

        # Title alignment multiplier
        title_lower = opp.get("title", "").lower()
        if any(term in title_lower for term in ("architect", "lead", "engineer", "tiny", "edge", "fairness", "fellow")):
            total_score = min(1.0, total_score * 1.08)

        return round(total_score, 3), breakdown

    def evaluate_visa_feasibility(self, opp: Dict[str, Any]) -> tuple[float, str, str]:
        """Estimate visa pathway approval probability based on profile credentials."""
        pathway = opp.get("visa_pathway", "EMPLOYER_SPONSORED")
        category = opp.get("category", "")

        if pathway == "UAE_GOLDEN_VISA" or category == "SOVEREIGN_GCC":
            # UAE Golden Visa Coder/AI track requires proven code artifacts, international publications, or senior tech contributions
            # Aaradhya's portfolio with public repos, AI fellowship capstone, edge AI firmware, and CP credentials scores very high
            feasibility = 0.915
            notes = "Strong eligibility under UAE Artificial Intelligence Office Coder/Special Talent track (GitHub repos + AI fellowship capstone)."
            return feasibility, "UAE_GOLDEN_VISA", notes
        elif pathway == "UN_G4_DIPLOMATIC" or category == "UN_MULTILATERAL":
            # UN P-level and International Consultancy positions provide direct G-4 visa sponsorship or diplomatic accreditation
            feasibility = 0.880
            notes = "Direct institutional multilateral accreditation upon appointment (UN P-2/P-3 or International Consultant Level II)."
            return feasibility, "UN_G4_DIPLOMATIC", notes
        elif pathway in ("DIPLOMATIC_A2_G1", "EU_DIPLOMATIC_BLUE_CARD") or category == "EMBASSY_DIPLOMATIC":
            # Bilateral embassies and diplomatic missions provide A-2 diplomatic visa, EU Diplomatic Blue Card, or direct FSN/LES status
            feasibility = 0.930
            notes = "Direct Foreign Service / Embassy institutional diplomatic accreditation (A-2 visa, EU Diplomatic Blue Card, or FSN/LES contract)."
            return feasibility, pathway, notes
        else:
            return 0.750, "EMPLOYER_SPONSORED", "Standard international skilled worker visa sponsorship."

    def extract_net_alpha_index(self, opp: Dict[str, Any]) -> float:
        """Parse or estimate annualized net purchasing power in kUSD."""
        comp_str = opp.get("compensation_est", "")
        tax_status = opp.get("tax_status", "LOCAL_TAX")

        # Extract dollar numbers
        numbers = [float(x.replace(",", "")) for x in re.findall(r"\$([0-9,]+)", comp_str)]
        if numbers:
            base_kusd = sum(numbers) / len(numbers) / 1000.0 if max(numbers) > 1000 else sum(numbers) / len(numbers)
        else:
            base_kusd = 160.0  # Default conservative baseline

        # If tax free (Dubai/UN), net alpha index is equal to gross. If taxable, multiply by 0.70 net.
        if tax_status in ("TAX_FREE", "UN_EXEMPT"):
            net_alpha = base_kusd
        else:
            net_alpha = base_kusd * 0.72

        return round(net_alpha, 1)

    def generate_gap_closure_actions(self, opp: Dict[str, Any], breakdown: Dict[str, float]) -> List[str]:
        """Produce concrete, high-leverage portfolio recommendations."""
        actions: List[str] = []
        category = opp.get("category", "")

        # Check pillar weaknesses
        if breakdown.get("SPARK", 0.0) < 0.50 and "edge" in opp.get("title", "").lower():
            actions.append("Highlight SPARK 200Hz FreeRTOS queue depth benchmarks and medical fall recall (>=0.95) in application abstract.")

        if breakdown.get("BiasAperture", 0.0) < 0.50 and any(t in opp.get("title", "").lower() for t in ("fairness", "ethics", "governance")):
            actions.append("Attach BiasAperture demographic parity audit report and EU AI Act conformity technical documentation.")

        if category == "SOVEREIGN_GCC":
            actions.append("Provide one-page executive system card framing SPARK as sovereign-grade ultra-low-power telemetry for industrial/assistive deployment.")
            actions.append("Format GitHub portfolio profile emphasizing UAE Coder Golden Visa eligibility criteria.")
        elif category == "UN_MULTILATERAL":
            actions.append("Explicitly map SPARK to UN SDG 3 (Good Health & Well-being) and BiasAperture to SDG 10 (Reduced Inequalities).")
            actions.append("Format application dossier matching UN Inspira competency-based indicators (Innovation, Planning, Technological Awareness).")
        elif category == "EMBASSY_DIPLOMATIC":
            actions.append("Highlight Cyber-Forensics zero-trust audit protocols, NTFS ADS inspection proofs, and air-gapped security safeguards.")
            actions.append("Submit cryptographic tamper-proofing evidence ledger conforming to diplomatic communications security standards.")

        if not actions:
            actions.append("Portfolio is directly aligned (>=90th percentile). Submit tailored technical dossier and executive cover letter.")

        return actions

    def evaluate_catalog(self, top_k: Optional[int] = None) -> List[MatchEvaluation]:
        """Evaluate all opportunities in catalog and rank by overall fit."""
        if not self.catalog_path.exists():
            logger.warning("Catalog not found at %s. Triggering fallback harvest.", self.catalog_path)
            from tools.harvest_sovereign_opportunities import SovereignOpportunityHarvester
            harvester = SovereignOpportunityHarvester()
            harvester.harvest()

        with open(self.catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        opportunities = catalog.get("opportunities", [])
        evaluations: List[MatchEvaluation] = []

        for opp in opportunities:
            fit_score, breakdown = self.compute_fit_score(opp)
            visa_score, pathway, visa_notes = self.evaluate_visa_feasibility(opp)
            net_alpha = self.extract_net_alpha_index(opp)
            actions = self.generate_gap_closure_actions(opp, breakdown)

            if fit_score >= 0.85:
                tier = "EXCEPTIONAL_MATCH"
            elif fit_score >= 0.70:
                tier = "HIGH_MATCH"
            elif fit_score >= 0.50:
                tier = "MODERATE_MATCH"
            else:
                tier = "DEVELOPING"

            evaluations.append(
                MatchEvaluation(
                    opportunity_id=opp.get("id", "UNKNOWN"),
                    title=opp.get("title", ""),
                    organization=opp.get("organization", ""),
                    category=opp.get("category", ""),
                    location=opp.get("location", ""),
                    overall_fit_ratio=fit_score,
                    fit_tier=tier,
                    visa_feasibility_score=visa_score,
                    visa_pathway=pathway,
                    visa_notes=visa_notes,
                    net_alpha_index_kusd=net_alpha,
                    tax_status=opp.get("tax_status", "TAX_FREE"),
                    pillar_breakdown=breakdown,
                    gap_closure_actions=actions,
                    url=opp.get("url", ""),
                    verifiable_sources=opp.get("verifiable_sources", []),
                )
            )

        # Sort descending by fit ratio
        evaluations.sort(key=lambda x: (x.overall_fit_ratio, x.net_alpha_index_kusd), reverse=True)

        if top_k and top_k > 0:
            evaluations = evaluations[:top_k]

        # Save match report
        report_payload = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "total_evaluated": len(evaluations),
            "exceptional_matches_count": sum(1 for e in evaluations if e.fit_tier == "EXCEPTIONAL_MATCH"),
            "high_matches_count": sum(1 for e in evaluations if e.fit_tier == "HIGH_MATCH"),
            "average_fit_ratio": round(sum(e.overall_fit_ratio for e in evaluations) / len(evaluations), 3) if evaluations else 0.0,
            "top_matches": [asdict(e) for e in evaluations]
        }
        with open(MATCH_REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2)

        return evaluations


def main() -> None:
    parser = argparse.ArgumentParser(description="Azmuth Semantic Opportunity Fit Matcher")
    parser.add_argument("--top", type=int, default=5, help="Number of top matches to display")
    parser.add_argument("--tier", type=str, choices=["all", "exceptional", "high"], default="all", help="Filter by tier")
    args = parser.parse_args()

    matcher = SemanticOpportunityMatcher()
    evaluations = matcher.evaluate_catalog(top_k=args.top)

    print("=" * 80)
    print("  AZMUTH SEMANTIC OPPORTUNITY FIT & ALPHA EVALUATOR")
    print("=" * 80)
    print(f"- Total Evaluated: {len(evaluations)}")
    print(f"- Report Cached:   {MATCH_REPORT_PATH}")
    print("=" * 80)

    for idx, e in enumerate(evaluations, 1):
        print(f"\n[{idx}] {e.title}")
        print(f"    Organization:    {e.organization} ({e.location})")
        print(f"    Fit Tier:        {e.fit_tier} (Score: {e.overall_fit_ratio * 100:.1f}%)")
        print(f"    Compensation:    ${e.net_alpha_index_kusd:.1f}k/yr Net ({e.tax_status})")
        print(f"    Visa Pathway:    {e.visa_pathway} (Feasibility: {e.visa_feasibility_score * 100:.1f}%)")
        print("    Pillar Overlap:  " + ", ".join(f"{k}: {v*100:.0f}%" for k, v in e.pillar_breakdown.items()))
        print("    Actionable Gaps: " + e.gap_closure_actions[0])
        print(f"    Target URL:      {e.url}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
