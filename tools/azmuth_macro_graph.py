"""
Azmuth Neuromorphic, Temporal-Triad & Multi-Universe Foresight Engine.
Unified mathematical substrate for 6 swappable cortical cartridges (U0..U5).
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Invariant: Low RAM footprint (<15 MB), zero-division safe, and pure standard library.
LOCAL_BUNDLED_CARTRIDGES = Path(__file__).resolve().parent.parent / "data" / "universes"
SIBLING_CP_CARTRIDGES = Path(__file__).resolve().parent.parent.parent / "Competitive-Programming" / "runtimes" / "universes"
DEFAULT_CARTRIDGE_DIR = LOCAL_BUNDLED_CARTRIDGES if LOCAL_BUNDLED_CARTRIDGES.exists() else SIBLING_CP_CARTRIDGES
DEFAULT_STATE_DIR = Path(__file__).resolve().parent.parent / "orchestrator-state"

# Cross-Universe Inter-Lobe Synaptic Bridge Matrix
# Maps causal, regulatory, power, and algorithmic dependencies across universe boundaries
CROSS_UNIVERSE_BRIDGE_SYNAPSES = [
    # U4 (Macro Capital / Foundries) -> U5 (Physical MCU BOM)
    {"source": "u4_macro_capital_markets::TSM", "target": "u5_hardware_physics_bom::ESP32_S3_SRAM_ALLOCATED_KB", "weight": -0.75, "lag_days": 14, "edge_type": "FOUNDRY_SUPPLY_CONSTRAINT"},
    # U5 (Physical MCU BOM) -> U6 (Energy / Thermal Dynamics)
    {"source": "u5_hardware_physics_bom::IMU_SAMPLING_FREQ_HZ", "target": "u6_energy_thermal_power::ACTIVE_BURST_POWER_MW", "weight": 0.88, "lag_days": 1, "edge_type": "TRANSDUCER_POWER_DRAW"},
    {"source": "u5_hardware_physics_bom::BLE_TX_POWER_MA", "target": "u6_energy_thermal_power::LIPO_VOLTAGE_SAG_V", "weight": -0.82, "lag_days": 1, "edge_type": "CURRENT_SAG_COUPLING"},
    # U6 (Energy / Thermal) -> U2 (AI Compute Frontier)
    {"source": "u6_energy_thermal_power::HOST_CPU_PACKAGE_TEMP_C", "target": "u2_ai_compute_frontier::LOCAL_16GB_RAM_PRESSURE", "weight": 0.70, "lag_days": 1, "edge_type": "THERMAL_THROTTLING_PRESSURE"},
    # U7 (Cyber Resilience) -> U0 (Ecosystem Autonomic Mesh)
    {"source": "u7_cyber_resilience_dfir::SECRET_LEAK_PROBABILITY_SCORE", "target": "u0_ecosystem_mesh::Fleet-Orchestrator", "weight": -0.92, "lag_days": 1, "edge_type": "SECURITY_HALT_QUARANTINE"},
    {"source": "u7_cyber_resilience_dfir::HEADLESS_ELEVATION_ATTEMPTS", "target": "u0_ecosystem_mesh::Fleet-Orchestrator", "weight": -0.99, "lag_days": 1, "edge_type": "UAC_HEADLESS_PROHIBITION"},
    # U8 (Algorithmic Complexity) -> U0 (Ecosystem Autonomic Mesh) & U1 (Research Arbitrage)
    {"source": "u8_algorithmic_complexity_cp::GENE_MUTATION_PROMOTION_RATE_PCT", "target": "u0_ecosystem_mesh::Competitive-Programming", "weight": 0.85, "lag_days": 2, "edge_type": "CODON_SYNTHESIS_PIPELINE"},
    {"source": "u8_algorithmic_complexity_cp::ASYMPTOTIC_BIG_O_LATENCY_NS", "target": "u1_research_arbitrage::SPARK_TINYML_ACCURACY", "weight": -0.68, "lag_days": 3, "edge_type": "INFERENCE_BUDGET_PRESSURE"},
    # U9 (Regulatory & Epistemic Audit) -> U1 (Research Arbitrage) & U0 (BiasAperture)
    {"source": "u9_regulatory_epistemic_audit::BIAS_DISPARITY_MAX_DEVIATION", "target": "u0_ecosystem_mesh::BiasAperture", "weight": 0.94, "lag_days": 1, "edge_type": "AUDIT_PARITY_VERIFICATION"},
    {"source": "u9_regulatory_epistemic_audit::EPISTEMIC_UNBACKED_CLAIMS_COUNT", "target": "u1_research_arbitrage::BRL_LAB_ARXIV", "weight": -0.90, "lag_days": 1, "edge_type": "EPISTEMIC_GATE_BLOCK"},
    # U10 (SPARK Edge AI Telemetry) -> U5, U6, and U1
    {"source": "u5_hardware_physics_bom::MPU6050_IMU_DRIFT", "target": "u10_spark_edge_ai_telemetry::IMU_ACCEL_JERK_MAGNITUDE", "weight": -0.78, "lag_days": 1, "edge_type": "SENSOR_NOISE_INJECTION"},
    {"source": "u10_spark_edge_ai_telemetry::TINYML_INFERENCE_LATENCY_MS", "target": "u6_energy_thermal_power::ACTIVE_BURST_POWER_MW", "weight": 0.85, "lag_days": 1, "edge_type": "COMPUTE_ENERGY_BURN"},
    {"source": "u10_spark_edge_ai_telemetry::FALL_RECALL_SAFETY_RATIO", "target": "u1_research_arbitrage::SPARK_TINYML_ACCURACY", "weight": 0.92, "lag_days": 2, "edge_type": "BENCHMARK_GROUNDING"},
    # U11 (BiasAperture Vision Fairness Audit) -> U9 and U0
    {"source": "u11_bias_aperture_vision_audit::EQUAL_OPPORTUNITY_DISPARITY", "target": "u9_regulatory_epistemic_audit::BIAS_DISPARITY_MAX_DEVIATION", "weight": 0.95, "lag_days": 1, "edge_type": "REGULATORY_METRIC_FEED"},
    {"source": "u11_bias_aperture_vision_audit::DEMOGRAPHIC_PARITY_GAP", "target": "u0_ecosystem_mesh::BiasAperture", "weight": 0.88, "lag_days": 1, "edge_type": "AUDIT_FEEDBACK_LOOP"},
    # U12 (Sovereign GCC & Dubai AI Opportunity Cortex) -> U3, U4, U10
    {"source": "u12_sovereign_gcc_dubai_radar::UAE_GOLDEN_VISA_CODER_READINESS", "target": "u3_career_opportunity_alpha::GLOBAL_AI_SYSTEMS_LABS", "weight": 0.92, "lag_days": 14, "edge_type": "GLOBAL_RESIDENCY_ENABLEMENT"},
    {"source": "u10_spark_edge_ai_telemetry::FALL_RECALL_SAFETY_RATIO", "target": "u12_sovereign_gcc_dubai_radar::FOUNDING_ML_SYSTEMS_MATCH_SCORE", "weight": 0.89, "lag_days": 7, "edge_type": "PORTFOLIO_PROVENANCE_COUPLING"},
    {"source": "u12_sovereign_gcc_dubai_radar::DFF_DUBAI_FUTURE_FOUNDATION_RFP", "target": "u4_macro_capital_markets::NVDA_GPU_DEMAND", "weight": 0.72, "lag_days": 30, "edge_type": "SOVEREIGN_COMPUTE_ACCELERATION"},
    # U13 (UN & Multilateral Global Innovation Radar) -> U10, U11, U3, U7
    {"source": "u10_spark_edge_ai_telemetry::FALL_RECALL_SAFETY_RATIO", "target": "u13_un_multilateral_global_radar::UNICEF_INNOVATION_FUND_EDGE_AI", "weight": 0.94, "lag_days": 14, "edge_type": "ASSISTIVE_TECH_VALIDATION"},
    {"source": "u11_bias_aperture_vision_audit::EQUAL_OPPORTUNITY_DISPARITY", "target": "u13_un_multilateral_global_radar::ETHICAL_AI_MULTILATERAL_MANDATE", "weight": 0.96, "lag_days": 7, "edge_type": "FAIRNESS_FRAMEWORK_COMPLIANCE"},
    {"source": "u13_un_multilateral_global_radar::UN_P_LEVEL_ROSTER_QUALIFICATION", "target": "u3_career_opportunity_alpha::GLOBAL_AI_SYSTEMS_LABS", "weight": 0.88, "lag_days": 30, "edge_type": "MULTILATERAL_INSTITUTIONAL_ROSTER"},
    {"source": "u7_cyber_resilience_dfir::SECRET_LEAK_PROBABILITY_SCORE", "target": "u13_un_multilateral_global_radar::DIPLOMATIC_SECURE_CYBER_READINESS", "weight": -0.91, "lag_days": 1, "edge_type": "SECURE_FACILITY_ACCREDITATION"},
    {"source": "u13_un_multilateral_global_radar::EMBASSY_DIPLOMATIC_TECH_ROSTER", "target": "u3_career_opportunity_alpha::GLOBAL_AI_SYSTEMS_LABS", "weight": 0.86, "lag_days": 21, "edge_type": "BILATERAL_CAREER_CORRIDOR"},
    # U14 (Frontier Talent, ATS & Professional Social Networks) -> U3, U12, U0
    {"source": "u14_frontier_talent_ats_radar::ASHBY_FRONTIER_AI_RADAR", "target": "u3_career_opportunity_alpha::GLOBAL_AI_SYSTEMS_LABS", "weight": 0.93, "lag_days": 7, "edge_type": "FRONTIER_LAB_APPLICATION_CORRIDOR"},
    {"source": "u14_frontier_talent_ats_radar::GREENHOUSE_LEVER_ATS_OPENINGS", "target": "u3_career_opportunity_alpha::OPEN_SOURCE_MAINTAINER_PIPELINE", "weight": 0.87, "lag_days": 10, "edge_type": "ATS_OSS_MAINTAINER_ARBITRAGE"},
    {"source": "u14_frontier_talent_ats_radar::LINKEDIN_TALENT_GRAPH_VOLUME", "target": "u12_sovereign_gcc_dubai_radar::FOUNDING_ML_SYSTEMS_MATCH_SCORE", "weight": 0.85, "lag_days": 7, "edge_type": "SOCIAL_GRAPH_OPPORTUNITY_FEED"},
    {"source": "u14_frontier_talent_ats_radar::ENTERPRISE_REMOTE_TECH_VOLUME", "target": "u0_ecosystem_mesh::Fleet-Orchestrator", "weight": 0.81, "lag_days": 5, "edge_type": "REMOTE_INFRASTRUCTURE_DEMAND"},
]

# --- Phase 4: Active User Context & Memory Grounding ---

GLOBAL_MEMORY_PATH = Path.home() / ".gemini" / "config" / "codex-memories" / "GLOBAL_MEMORY.md"

def extract_active_memory_context(max_recent_lines: int = 50) -> dict[str, Any]:
    """Phase 4: Extracts active user focus and recent memory topics from GLOBAL_MEMORY.md.
    Enables foresight sweeps to dynamically ground universe prior weights in live human work.
    """
    context: dict[str, Any] = {
        "active_keywords": set(),
        "recent_notes": [],
        "universe_affinity": collections.defaultdict(float),
    }

    if not GLOBAL_MEMORY_PATH.is_file():
        return context

    try:
        text = GLOBAL_MEMORY_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()

        # Keyword to universe mapping heuristics
        affinity_rules = {
            "spark": ["u5_hardware_physics_bom", "u10_spark_edge_ai_telemetry"],
            "imu": ["u5_hardware_physics_bom", "u10_spark_edge_ai_telemetry"],
            "tinyml": ["u10_spark_edge_ai_telemetry", "u1_research_arbitrage"],
            "bias": ["u11_bias_aperture_vision_audit", "u9_regulatory_epistemic_audit"],
            "fairness": ["u11_bias_aperture_vision_audit", "u9_regulatory_epistemic_audit"],
            "fleet": ["u0_ecosystem_mesh", "u2_ai_compute_frontier"],
            "copilot": ["u0_ecosystem_mesh", "u2_ai_compute_frontier"],
            "worker": ["u0_ecosystem_mesh", "u2_ai_compute_frontier"],
            "competitive": ["u8_algorithmic_complexity_cp"],
            "cp": ["u8_algorithmic_complexity_cp"],
            "cyber": ["u7_cyber_resilience_dfir"],
            "forensics": ["u7_cyber_resilience_dfir"],
            "dubai": ["u12_sovereign_gcc_dubai_radar"],
            "gcc": ["u12_sovereign_gcc_dubai_radar"],
            "un": ["u13_un_multilateral_global_radar"],
            "ats": ["u14_frontier_talent_ats_radar"],
            "career": ["u3_career_opportunity_alpha", "u14_frontier_talent_ats_radar"],
        }

        # Inspect last lines for active signals
        for line in lines[-max_recent_lines:]:
            line_lower = line.lower()
            for kw, universes in affinity_rules.items():
                if kw in line_lower:
                    context["active_keywords"].add(kw)
                    for u in universes:
                        context["universe_affinity"][u] += 0.25

        context["active_keywords"] = sorted(list(context["active_keywords"]))
        context["universe_affinity"] = dict(context["universe_affinity"])
    except Exception as exc:
        pass

    return context


class HomeostaticBaselineNormalizer:
    """Evaluates raw observations against 4-layer homeostatic, allostatic, and nociceptive bounds."""

    @staticmethod
    def normalize_node(node: Dict[str, Any], habituate_threshold: float = 0.8) -> Dict[str, Any]:
        val = float(node.get("current_value", 0.0))
        l1 = node.get("layer1_homeostatic", {})
        l3 = node.get("layer3_nociceptive", {})

        mu0 = float(l1.get("mu0", 0.0))
        sigma0 = max(float(l1.get("sigma0", 1.0)), 1e-6)
        abs_min = float(l3.get("abs_min", -100.0))
        abs_max = float(l3.get("abs_max", 100.0))
        l2 = node.get("layer2_allostatic", {})
        z_crit = float(l2.get("z_critical", 3.0))

        z_score = (val - mu0) / sigma0
        span = max(abs_max - abs_min, 1e-6)
        abs_ratio = min(max((val - abs_min) / span, 0.0), 1.0)

        is_habituated = abs(z_score) < habituate_threshold
        if is_habituated:
            spikes = 0
            state_label = "HOMEOSTATIC_EQUILIBRIUM"
        elif abs(z_score) < 2.0:
            spikes = 1
            state_label = "ALLOSTATIC_STRETCH"
        elif abs(z_score) < z_crit:
            spikes = 2
            state_label = "NOCICEPTIVE_WARNING"
        else:
            spikes = 3
            state_label = "CRITICAL_NOCICEPTIVE_SPIKE"

        return {
            "current_value": round(val, 4),
            "z_score": round(z_score, 4),
            "abs_extreme_ratio": round(abs_ratio * 100.0, 2),
            "habituated": is_habituated,
            "spikes": spikes,
            "state_label": state_label,
        }


class ThalamicSignalFilter:
    """Filters noise: silences peaceful nodes and prunes sub-materiality synapses."""

    def __init__(self, habituate_threshold: float = 0.8, min_synapse_weight: float = 0.15):
        self.habituate_threshold = habituate_threshold
        self.min_synapse_weight = min_synapse_weight

    def filter_active_spikes(self, nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        active = {}
        for nid, node in nodes.items():
            norm = HomeostaticBaselineNormalizer.normalize_node(node, self.habituate_threshold)
            node_copy = dict(node)
            node_copy.update(norm)
            if not norm["habituated"]:
                active[nid] = node_copy
        return active

    def prune_synapses(self, synapses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [s for s in synapses if abs(float(s.get("weight", 0.0))) >= self.min_synapse_weight]


class SpikingMacroGraph:
    """Direct multi-hop graph engine supporting axonal delays and convergent spatial summation."""

    def __init__(self, nodes: List[Dict[str, Any]], synapses: List[Dict[str, Any]], habituate_threshold: float = 0.8, min_weight: float = 0.15):
        self.raw_nodes = {n["id"]: n for n in nodes}
        self.filter = ThalamicSignalFilter(habituate_threshold, min_weight)
        self.synapses = self.filter.prune_synapses(synapses)

        # Adjacency
        self.adj_out: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
        self.adj_in: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
        for s in self.synapses:
            self.adj_out[s["source"]].append(s)
            self.adj_in[s["target"]].append(s)

        # Compute normalized state for all nodes
        self.nodes: Dict[str, Dict[str, Any]] = {}
        for nid, n in self.raw_nodes.items():
            norm = HomeostaticBaselineNormalizer.normalize_node(n, habituate_threshold)
            merged = dict(n)
            merged.update(norm)
            self.nodes[nid] = merged

        # Path cache: (u, v) -> {effective_weight, lag_days, min_hops}
        self.path_matrix: Dict[str, Dict[str, Dict[str, Any]]] = self._build_path_matrix(max_hops=3, gamma=0.75)

    def _build_path_matrix(self, max_hops: int = 3, gamma: float = 0.75) -> Dict[str, Dict[str, Dict[str, Any]]]:
        matrix: Dict[str, Dict[str, Dict[str, Any]]] = collections.defaultdict(dict)
        for start_id in self.nodes:
            queue = collections.deque([(start_id, 1.0, 0, 0, [start_id])])
            while queue:
                curr, cum_w, hop, cum_lag, path = queue.popleft()
                if hop >= max_hops:
                    continue
                for edge in self.adj_out.get(curr, []):
                    tgt = edge["target"]
                    if tgt in path:
                        continue
                    w = float(edge.get("weight", 0.0))
                    step_lag = int(edge.get("lag_days", 0))
                    eff_w = cum_w * w * (gamma ** (hop + 1))
                    tgt_lag = cum_lag + step_lag
                    curr_best = matrix[start_id].get(tgt)
                    if curr_best is None or abs(eff_w) > abs(curr_best["effective_weight"]):
                        matrix[start_id][tgt] = {
                            "effective_weight": eff_w,
                            "lag_days": tgt_lag,
                            "hops": hop + 1,
                        }
                    queue.append((tgt, eff_w, hop + 1, tgt_lag, path + [tgt]))
        return matrix

    def simulate_shock(self, source_id: str, magnitude: float = -0.40, max_hops: int = 3, gamma: float = 0.75, beta: float = 0.35) -> Dict[str, Any]:
        impacts: Dict[str, float] = collections.defaultdict(float)
        arrival_lags: Dict[str, int] = collections.defaultdict(int)
        in_parents: Dict[str, Set[str]] = collections.defaultdict(set)

        queue = collections.deque([(source_id, magnitude, 0, 0, [source_id])])
        while queue:
            curr, mag, hop, cum_lag, path = queue.popleft()
            if hop >= max_hops:
                continue
            for edge in self.adj_out.get(curr, []):
                tgt = edge["target"]
                if tgt in path:
                    continue
                w = float(edge.get("weight", 0.0))
                step_lag = int(edge.get("lag_days", 0))
                attenuated = mag * w * (gamma ** (hop + 1))
                impacts[tgt] += attenuated
                in_parents[tgt].add(curr)
                arrival_lags[tgt] = max(arrival_lags[tgt], cum_lag + step_lag)
                queue.append((tgt, attenuated, hop + 1, cum_lag + step_lag, path + [tgt]))

        results = []
        for tgt, parents in in_parents.items():
            base_impact = impacts[tgt]
            convergent_boost = 1.0 + beta * max(0, len(parents) - 1)
            final_impact = base_impact * convergent_boost
            results.append({
                "target": tgt,
                "label": self.nodes.get(tgt, {}).get("label", tgt),
                "impact_score": round(final_impact, 4),
                "arrival_lag_days": arrival_lags[tgt],
                "convergent_parents": len(parents),
                "parents": sorted(list(parents)),
            })
        results.sort(key=lambda x: abs(x["impact_score"]), reverse=True)
        return {
            "source_id": source_id,
            "source_label": self.nodes.get(source_id, {}).get("label", source_id),
            "magnitude": magnitude,
            "affected_targets": results,
        }

    def detect_systemic_chokepoints(self, top_k: int = 10) -> List[Dict[str, Any]]:
        node_ids = list(self.nodes.keys())
        n = len(node_ids)
        betweenness = {nid: 0.0 for nid in node_ids}

        for s in node_ids:
            stack = []
            pred = collections.defaultdict(list)
            sigma = collections.defaultdict(float)
            sigma[s] = 1.0
            dist = {nid: -1 for nid in node_ids}
            dist[s] = 0
            queue = collections.deque([s])

            while queue:
                v = queue.popleft()
                stack.append(v)
                for edge in self.adj_out.get(v, []):
                    w = edge["target"]
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        pred[w].append(v)

            delta = collections.defaultdict(float)
            while stack:
                w = stack.pop()
                for v in pred[w]:
                    if sigma[w] > 0:
                        delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
                if w != s:
                    betweenness[w] += delta[w]

        norm_factor = ((n - 1) * (n - 2)) if n > 2 else 1.0
        for nid in betweenness:
            betweenness[nid] = betweenness[nid] / norm_factor

        # HHI supplier concentration for downstream targets
        supplier_weights: Dict[str, Dict[str, float]] = collections.defaultdict(dict)
        for s in self.synapses:
            supplier_weights[s["target"]][s["source"]] = abs(float(s.get("weight", 0.0)))

        hhi_scores = {}
        for nid in node_ids:
            supps = supplier_weights.get(nid, {})
            tot = sum(supps.values())
            if tot > 0:
                hhi_scores[nid] = sum((w / tot) ** 2 for w in supps.values())
            else:
                hhi_scores[nid] = 0.0

        chokepoints = []
        for nid in node_ids:
            cb = betweenness.get(nid, 0.0)
            downstream_hhis = [hhi_scores.get(edge["target"], 0.0) for edge in self.adj_out.get(nid, [])]
            max_downstream_hhi = max(downstream_hhis) if downstream_hhis else 0.0
            alpha = round(0.5 * cb + 0.5 * max_downstream_hhi, 4)
            chokepoints.append({
                "node_id": nid,
                "label": self.nodes.get(nid, {}).get("label", nid),
                "betweenness": round(cb, 4),
                "max_downstream_hhi": round(max_downstream_hhi, 4),
                "chokepoint_alpha": alpha,
            })
        chokepoints.sort(key=lambda x: x["chokepoint_alpha"], reverse=True)
        return chokepoints[:top_k]


class PreContactAvoidanceGate:
    """Computes undiluted Top-k path-attenuated peripheral dissonance for gut avoidance."""

    @staticmethod
    def evaluate(target_id: str, graph: SpikingMacroGraph, theta_avoid: float = 1.15) -> Dict[str, Any]:
        # Collect 2-hop active upstream contributors
        contributors = []
        for u_id, u_node in graph.nodes.items():
            if u_id == target_id:
                continue
            path_info = graph.path_matrix.get(u_id, {}).get(target_id)
            if not path_info or path_info["hops"] > 2:
                continue
            w_eff = abs(float(path_info["effective_weight"]))
            z_u = float(u_node.get("z_score", 0.0))
            if w_eff >= 0.15 and abs(z_u) >= 0.8:
                contributors.append((u_id, z_u, w_eff))

        contributors.sort(key=lambda c: abs(c[1]) * c[2], reverse=True)
        top5 = contributors[:5]

        if len(top5) < 2:
            return {
                "target_id": target_id,
                "avoid": False,
                "gut_score": 0.0,
                "top_contributors": [],
                "reason": "Stable tranquil horizon (<2 peripheral turbulence inputs)",
                "action": "CLEAR: Stable tranquil horizon (<2 peripheral turbulence inputs)",
            }

        w_sum = sum(c[2] for c in top5) + 1e-6
        mean_turb = sum(abs(c[1]) * c[2] for c in top5) / w_sum

        # Sign dispersion (phase desync)
        signs = [1 if c[1] > 0 else -1 for c in top5]
        mean_sign = sum(signs) / len(signs)
        sign_var = sum((s - mean_sign) ** 2 for s in signs) / len(signs)

        d_gut = round(mean_turb * (1.0 + 0.5 * sign_var), 4)
        avoid = d_gut >= theta_avoid

        return {
            "target_id": target_id,
            "avoid": avoid,
            "gut_score": d_gut,
            "threshold": theta_avoid,
            "top_contributors": [{"id": c[0], "z_score": round(c[1], 2), "weight": round(c[2], 3)} for c in top5],
            "action": "PRE_CONTACT_AVOID: High peripheral turbulence/desync detected" if avoid else "CLEAR: Manageable allostatic baseline",
        }


class InhibitorySafetyCatch:
    """Evaluates forward trajectory and fires closed-form CBF braking (CATCH_AND_ARREST)."""

    @staticmethod
    def evaluate(target_id: str, delta_x: float, graph: SpikingMacroGraph, safety_margin: float = 0.85) -> Dict[str, Any]:
        alpha_brake = 1.0
        breach_details = []

        for edge in graph.adj_out.get(target_id, []):
            w_id = edge["target"]
            coupling = float(edge.get("weight", 0.0))
            w_node = graph.nodes.get(w_id, {})
            curr_val = float(w_node.get("current_value", 0.0))
            l3 = w_node.get("layer3_nociceptive", {})
            abs_min = float(l3.get("abs_min", -100.0))
            abs_max = float(l3.get("abs_max", 100.0))

            impulse = coupling * delta_x
            if abs(impulse) < 1e-6:
                continue

            limit_val = abs_min + safety_margin * (abs_max - abs_min) if impulse > 0 else abs_min + (1.0 - safety_margin) * (abs_max - abs_min)
            predicted_next = curr_val + impulse

            if impulse > 0 and predicted_next > limit_val:
                cand = max(0.0, (limit_val - curr_val) / impulse)
                if cand < alpha_brake:
                    alpha_brake = cand
                    breach_details.append(f"{w_id} ceiling breach ({predicted_next:.2f} > {limit_val:.2f})")
            elif impulse < 0 and predicted_next < limit_val:
                cand = max(0.0, (limit_val - curr_val) / impulse)
                if cand < alpha_brake:
                    alpha_brake = cand
                    breach_details.append(f"{w_id} floor breach ({predicted_next:.2f} < {limit_val:.2f})")

        engaged = alpha_brake < 0.999
        safe_delta = round(delta_x * alpha_brake, 4)

        return {
            "target_id": target_id,
            "engaged": engaged,
            "alpha_brake": round(alpha_brake, 4),
            "original_delta": delta_x,
            "safe_delta": safe_delta,
            "action": "CATCH_AND_ARREST: Reflex scaled down to preserve safety margins" if engaged else "PERMITTED: Clean forward trajectory",
            "breach_reasons": breach_details,
        }


class ForesightAlphaEngine:
    """Computes Signals 1 through 4 and renders actionable intelligence briefs."""

    def __init__(self, graph: SpikingMacroGraph, engrams: Optional[List[Dict[str, Any]]] = None):
        self.graph = graph
        self.engrams = engrams or []

    def compute_signal1_unpriced_ripples(self, min_coupling: float = 0.25, z_upstream: float = 1.8, z_downstream: float = 0.75) -> List[Dict[str, Any]]:
        ripples = []
        for u_id, u_node in self.graph.nodes.items():
            z_u = float(u_node.get("z_score", 0.0))
            if abs(z_u) < z_upstream:
                continue
            for v_id, v_node in self.graph.nodes.items():
                if u_id == v_id:
                    continue
                path = self.graph.path_matrix.get(u_id, {}).get(v_id)
                if not path:
                    continue
                w_eff = float(path["effective_weight"])
                lag = int(path["lag_days"])
                if abs(w_eff) < min_coupling or lag <= 0:
                    continue
                z_v = float(v_node.get("z_score", 0.0))
                if abs(z_v) < z_downstream:
                    expected_impact = round(z_u * w_eff, 4)
                    ripples.append({
                        "upstream": u_id,
                        "downstream": v_id,
                        "upstream_label": u_node.get("label", u_id),
                        "downstream_label": v_node.get("label", v_id),
                        "z_upstream": round(z_u, 2),
                        "z_downstream": round(z_v, 2),
                        "effective_coupling": round(w_eff, 3),
                        "arrival_lag_days": lag,
                        "expected_impact": expected_impact,
                        "action": f"Anticipate {expected_impact:+.2f}sigma ripple on {v_id} in ~{lag} days",
                    })
        ripples.sort(key=lambda r: abs(r["expected_impact"]), reverse=True)
        return ripples

    def compute_signal2_convergent_pinches(self, beta: float = 0.35) -> List[Dict[str, Any]]:
        pinches = []
        for v_id, v_node in self.graph.nodes.items():
            upstream_shocks = []
            for u_id, u_node in self.graph.nodes.items():
                if u_id == v_id:
                    continue
                path = self.graph.path_matrix.get(u_id, {}).get(v_id)
                if not path:
                    continue
                z_u = float(u_node.get("z_score", 0.0))
                w_eff = float(path["effective_weight"])
                if abs(z_u) >= 1.2 and abs(w_eff) >= 0.20:
                    upstream_shocks.append((u_id, z_u, w_eff, path["lag_days"]))

            if len(upstream_shocks) >= 2:
                total_pinch = sum(s[1] * s[2] for s in upstream_shocks) * (1.0 + beta * (len(upstream_shocks) - 1))
                pinches.append({
                    "target_id": v_id,
                    "target_label": v_node.get("label", v_id),
                    "convergent_upstream_count": len(upstream_shocks),
                    "total_pinch_potential": round(total_pinch, 4),
                    "convergent_sources": [{"id": s[0], "z": round(s[1], 2), "w": round(s[2], 3), "lag": s[3]} for s in upstream_shocks],
                    "action": f"Multi-hop convergence detected: {len(upstream_shocks)} inputs stretching simultaneously (Pinch: {total_pinch:+.2f})",
                })
        pinches.sort(key=lambda p: abs(p["total_pinch_potential"]), reverse=True)
        return pinches

    def compute_signal3_engram_matches(self, min_coverage: float = 0.70) -> List[Dict[str, Any]]:
        live_z = {nid: float(n.get("z_score", 0.0)) for nid, n in self.graph.nodes.items()}
        matches = []
        for engram in self.engrams:
            sig = engram.get("signature_z", {})
            if not sig:
                continue
            shared = [k for k in sig if k in live_z]
            coverage = len(shared) / len(sig)
            if coverage < min_coverage or not shared:
                continue
            dot = sum(live_z[k] * float(sig[k]) for k in shared)
            norm_live = math.sqrt(sum(live_z[k] ** 2 for k in shared)) + 1e-6
            norm_sig = math.sqrt(sum(float(sig[k]) ** 2 for k in shared)) + 1e-6
            cosine = dot / (norm_live * norm_sig)
            diag_dist = math.sqrt(sum((live_z[k] - float(sig[k])) ** 2 for k in shared) / len(shared))
            dist_factor = math.exp(-diag_dist)
            hybrid = round(0.6 * cosine + 0.4 * dist_factor, 4)
            matches.append({
                "engram_id": engram.get("engram_id"),
                "label": engram.get("label"),
                "hybrid_score": hybrid,
                "coverage_pct": round(coverage * 100.0, 1),
                "forward_30d": engram.get("forward_30d", ""),
                "forward_90d": engram.get("forward_90d", ""),
                "directive": engram.get("actionable_directive", ""),
            })
        matches.sort(key=lambda m: m["hybrid_score"], reverse=True)
        return matches

    def generate_brief(self) -> Dict[str, Any]:
        ripples = self.compute_signal1_unpriced_ripples()
        pinches = self.compute_signal2_convergent_pinches()
        engrams = self.compute_signal3_engram_matches()
        chokepoints = self.graph.detect_systemic_chokepoints(top_k=5)

        # Gut avoidance across top 5 active targets
        gut_checks = []
        for nid in list(self.graph.nodes.keys())[:10]:
            chk = PreContactAvoidanceGate.evaluate(nid, self.graph)
            if chk["avoid"] or chk["gut_score"] >= 0.9:
                gut_checks.append(chk)

        return {
            "ripples": ripples,
            "pinches": pinches,
            "engram_matches": engrams,
            "systemic_chokepoints": chokepoints,
            "gut_avoidance_advisories": gut_checks,
        }


class CorticalCartridgeLoader:
    """Loads, validates, and mounts CorticalCartridgeV1 files."""

    @staticmethod
    def load_cartridge(cartridge_path: Path | str) -> Dict[str, Any]:
        target = Path(cartridge_path)
        if not target.exists():
            # Check local data/universes
            alt_local = LOCAL_BUNDLED_CARTRIDGES / cartridge_path.name
            if alt_local.exists():
                target = alt_local
            else:
                alt_sibling = SIBLING_CP_CARTRIDGES / cartridge_path.name
                if alt_sibling.exists():
                    target = alt_sibling
                else:
                    raise FileNotFoundError(f"Cortical cartridge not found: {cartridge_path} (checked {LOCAL_BUNDLED_CARTRIDGES} and {SIBLING_CP_CARTRIDGES})")
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    @staticmethod
    def list_available_cartridges(cartridge_dir: Path = DEFAULT_CARTRIDGE_DIR) -> List[Dict[str, str]]:
        if not cartridge_dir.exists():
            return []
        cartridges = []
        for p in sorted(cartridge_dir.glob("*.json")):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    c = json.load(f)
                cartridges.append({
                    "id": c.get("universe_id", p.stem),
                    "name": c.get("cortical_lobe", p.stem),
                    "path": str(p),
                    "node_count": len(c.get("nodes", [])),
                    "synapse_count": len(c.get("synapses", [])),
                })
            except Exception:
                pass
        return cartridges


def render_markdown_brief(brief: Dict[str, Any], universe_id: str, lobe_name: str) -> str:
    lines = [
        f"# Azmuth Foresight Intelligence Radar",
        f"**Mounted Cortical Lobe:** `{universe_id}` ({lobe_name})  ",
        f"**Engine Mode:** 20W Neuromorphic Spiking Core (Thalamic Habituation Active)  ",
        "",
        "---",
        "",
        "## 1. Top Unpriced Axonal Ripples (Lead-Lag Asymmetric Edge)",
    ]
    ripples = brief.get("ripples", [])
    if not ripples:
        lines.append("_No unpriced lead-lag ripples detected. Equilibrium stable across axonal conduits._")
    else:
        for r in ripples[:5]:
            lines.append(f"- **{r['upstream']} -> {r['downstream']}** (Lead-Time: `~{r['arrival_lag_days']}d` | Coupling: `{r['effective_coupling']}`)")
            lines.append(f"  - Upstream State: `{r['z_upstream']:+.2f}sigma` | Downstream State: `{r['z_downstream']:+.2f}sigma`")
            lines.append(f"  - **Directive:** {r['action']}")

    lines.extend([
        "",
        "## 2. Convergent Spatial Pinches (Hidden Concentration)",
    ])
    pinches = brief.get("pinches", [])
    if not pinches:
        lines.append("_No convergent spatial pinches detected._")
    else:
        for p in pinches[:3]:
            lines.append(f"- **Target: {p['target_id']}** ({p['target_label']}) — `{p['convergent_upstream_count']}` Upstream Inputs Converging (Total Pinch: `{p['total_pinch_potential']:+.2f}`)")
            lines.append(f"  - **Directive:** {p['action']}")

    lines.extend([
        "",
        "## 3. Top Historical Regime Engram Matches",
    ])
    engrams = brief.get("engram_matches", [])
    if not engrams:
        lines.append("_No active historical engram matches._")
    else:
        for e in engrams[:2]:
            lines.append(f"- **{e['label']}** (Similarity: `{e['hybrid_score'] * 100:.1f}%` | Coverage: `{e['coverage_pct']}%`)")
            lines.append(f"  - Forward 30d Trajectory: {e['forward_30d']}")
            lines.append(f"  - Forward 90d Trajectory: {e['forward_90d']}")
            lines.append(f"  - **Directive:** {e['directive']}")

    lines.extend([
        "",
        "## 4. Pre-Contact Gut Avoidance Advisories",
    ])
    guts = brief.get("gut_avoidance_advisories", [])
    if not guts:
        lines.append("_All evaluated targets within peaceful allostatic baselines._")
    else:
        for g in guts:
            status = "[!] AVOID" if g["avoid"] else "[i] NOTICE"
            lines.append(f"- **{status} on {g['target_id']}** (Gut Dissonance Score: `{g['gut_score']:.2f}` / Threshold `{g['threshold']:.2f}`)")
            lines.append(f"  - **Directive:** {g['action']}")

    return "\n".join(lines)


def sweep_all_universes(cartridge_dir: Path = DEFAULT_CARTRIDGE_DIR, z_threshold: float = 0.8) -> dict[str, Any]:
    """Sweeps all 6 cortical cartridges (U0 through U5) in parallel/sequence.
    Evaluates SpikingMacroGraph and ForesightAlphaEngine across each lobe,
    returning a unified multi-universe telemetry matrix.
    """
    cartridges = CorticalCartridgeLoader.list_available_cartridges(cartridge_dir)
    results: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cartridges": len(cartridges),
        "universes": {},
        "systemic_spikes": [],
        "critical_chokepoints": [],
    }

    for c in cartridges:
        c_path = c["path"]
        try:
            c_data = CorticalCartridgeLoader.load_cartridge(c_path)
            u_id = c_data.get("universe_id", c["id"])
            lobe = c_data.get("cortical_lobe", c["name"])

            graph = SpikingMacroGraph(
                c_data.get("nodes", []),
                c_data.get("synapses", []),
                habituate_threshold=z_threshold,
            )
            engine = ForesightAlphaEngine(graph, c_data.get("engrams", []))
            brief = engine.generate_brief()

            spikes = [
                {"node_id": nid, "z_score": n["z_score"], "state": n["state_label"]}
                for nid, n in graph.nodes.items()
                if abs(n["z_score"]) >= z_threshold
            ]

            chokepoints = graph.detect_systemic_chokepoints(top_k=3)
            top_choke = chokepoints[0]["node_id"] if chokepoints else None

            results["universes"][u_id] = {
                "id": u_id,
                "name": lobe,
                "node_count": len(graph.nodes),
                "synapse_count": len(c_data.get("synapses", [])),
                "spikes_count": len(spikes),
                "top_chokepoint": top_choke,
                "engram_matches": len(brief.get("engram_matches", [])),
                "nodes": graph.nodes,
                "last_swept_at": datetime.now(timezone.utc).isoformat(),
            }

            for s in spikes:
                results["systemic_spikes"].append({"universe_id": u_id, **s})

            if top_choke:
                results["critical_chokepoints"].append({"universe_id": u_id, "node_id": top_choke})

        except Exception as exc:
            results["universes"][c["id"]] = {"error": str(exc)}

    # Attach Cross-Universe Bridge Synapses
    results["cross_universe_bridges"] = CROSS_UNIVERSE_BRIDGE_SYNAPSES

    # Phase 4: Ground foresight sweep in active memory context
    mem_ctx = extract_active_memory_context()
    results["memory_context"] = mem_ctx
    if mem_ctx.get("universe_affinity"):
        for u_id, affinity_boost in mem_ctx["universe_affinity"].items():
            if u_id in results["universes"] and isinstance(results["universes"][u_id], dict):
                results["universes"][u_id]["active_user_affinity"] = round(affinity_boost, 2)
                results["universes"][u_id]["grounded_in_user_memory"] = True

    # Persist multi-universe sweep summary
    DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)
    sweep_path = DEFAULT_STATE_DIR / "macro_foresight_sweep.json"
    try:
        with open(sweep_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    except Exception:
        pass

    return results


def main():
    parser = argparse.ArgumentParser(description="Azmuth Neuromorphic Multi-Universe Foresight Engine")
    parser.add_argument("--list-universes", action="store_true", help="List all available Cortical Cartridges")
    parser.add_argument("--mount", type=str, default="u4_macro_capital_markets", help="Universe cartridge ID or filename to mount")
    parser.add_argument("--view", choices=["3pv", "fpv"], default="3pv", help="View perspective (3pv: Allocentric Bird's-Eye, fpv: Egocentric Node Horizon)")
    parser.add_argument("--target", type=str, default=None, help="Target node ID for FPV or Ego-network queries")
    parser.add_argument("--foresight", action="store_true", help="Execute 4-signal foresight alpha engine")
    parser.add_argument("--extremes", action="store_true", help="Render allostatic stretch vs nociceptive extremes table")
    parser.add_argument("--chokepoints", action="store_true", help="Compute systemic chokepoint betweenness centrality")
    parser.add_argument("--sweep-all", action="store_true", help="Sweep and evaluate all 6 cortical cartridges (U0..U5)")
    parser.add_argument("--shock", type=str, default=None, help="Simulate shock propagation from a source node")
    parser.add_argument("--magnitude", type=float, default=-0.40, help="Shock magnitude (-1.0 to 1.0)")
    parser.add_argument("--inject", nargs="*", default=[], help="Inject telemetry overrides (e.g. --inject NVDA=8.5 TSM=2.1)")

    args = parser.parse_args()

    if args.sweep_all:
        sweep_data = sweep_all_universes()
        print(f"\n=== AZMUTH MULTI-UNIVERSE SWEEP (U0..U5) ===")
        print(f"Timestamp: {sweep_data['timestamp']} | Total Cartridges: {sweep_data['total_cartridges']}")
        for uid, uinfo in sweep_data.get("universes", {}).items():
            if "error" in uinfo:
                print(f"  * [{uid}] ERROR: {uinfo['error']}")
            else:
                print(f"  * [{uid}] {uinfo['name']}: {uinfo['node_count']} nodes, {uinfo['synapse_count']} synapses, {uinfo['spikes_count']} spikes (Top Choke: {uinfo['top_chokepoint']})")
        print(f"\n[OK] Summary updated in orchestrator-state/macro_foresight_sweep.json")
        return

    if args.list_universes:
        cartridges = CorticalCartridgeLoader.list_available_cartridges()
        print("\n=== AZMUTH CORTICAL CARTRIDGE VAULT (0 MB RAM Idle) ===")
        if not cartridges:
            print("No cartridges found in default vault path.")
        for c in cartridges:
            print(f"  * [{c['id']}] {c['name']} (Nodes: {c['node_count']} | Synapses: {c['synapse_count']})")
        return

    # Resolve cartridge
    mount_target = args.mount
    if not mount_target.endswith(".json"):
        mount_target = f"{mount_target}.json"

    cartridge_file = DEFAULT_CARTRIDGE_DIR / mount_target
    if not cartridge_file.exists():
        # Fallback to direct path
        cartridge_file = Path(args.mount)
        if not cartridge_file.exists():
            print(f"[ERROR] Universe cartridge not found: {args.mount} (checked {DEFAULT_CARTRIDGE_DIR})")
            sys.exit(1)

    cartridge_data = CorticalCartridgeLoader.load_cartridge(cartridge_file)
    universe_id = cartridge_data.get("universe_id", cartridge_file.stem)
    lobe_name = cartridge_data.get("cortical_lobe", "Universal Cortex")

    # Handle telemetry injection overrides
    if args.inject:
        for item in args.inject:
            if "=" in item:
                k, v = item.split("=", 1)
                try:
                    val_float = float(v)
                    for n in cartridge_data.get("nodes", []):
                        if n["id"] == k.strip():
                            n["current_value"] = val_float
                            print(f"[INJECT] Override {k.strip()} = {val_float}")
                except ValueError:
                    pass

    # Build Graph
    graph = SpikingMacroGraph(cartridge_data.get("nodes", []), cartridge_data.get("synapses", []))
    engine = ForesightAlphaEngine(graph, cartridge_data.get("engrams", []))

    if args.view == "fpv" and args.target:
        node = graph.nodes.get(args.target)
        if not node:
            print(f"[ERROR] Node '{args.target}' not found in universe '{universe_id}'")
            sys.exit(1)
        print(f"\n=== EGOCENTRIC FIRST-PERSON VIEW (FPV): {node['id']} ({node.get('label', '')}) ===")
        print(f"Current Value: {node['current_value']} {node.get('unit', '')}")
        print(f"State Horizon: {node['state_label']} (Z-score: {node['z_score']:+.2f}sigma | All-Time Extreme: {node['abs_extreme_ratio']}%)")
        print(f"Thalamic Spikes: {node['spikes']} (Habituated: {node['habituated']})")

        gut = PreContactAvoidanceGate.evaluate(node["id"], graph)
        print(f"Pre-Contact Avoidance: {gut['action']} (D_gut: {gut['gut_score']:.2f})")

        print("\nIncoming Axons:")
        for edge in graph.adj_in.get(node["id"], []):
            src = edge["source"]
            w = edge.get("weight", 0.0)
            lag = edge.get("lag_days", 0)
            src_node = graph.nodes.get(src, {})
            print(f"  <- {src} (weight: {w:+.2f}, lag: {lag}d | Z: {src_node.get('z_score', 0.0):+.2f}sigma)")

        print("\nOutgoing Axons:")
        for edge in graph.adj_out.get(node["id"], []):
            tgt = edge["target"]
            w = edge.get("weight", 0.0)
            lag = edge.get("lag_days", 0)
            tgt_node = graph.nodes.get(tgt, {})
            print(f"  -> {tgt} (weight: {w:+.2f}, lag: {lag}d | Z: {tgt_node.get('z_score', 0.0):+.2f}sigma)")
        return

    if args.extremes:
        print(f"\n=== {lobe_name.upper()} — 4-LAYER HOMEOSTATIC & EXTREMES TABLE ===")
        print(f"{'ID':<18} {'CURRENT':<10} {'Z-SCORE':<10} {'ABS EXTREME':<14} {'SPIKES':<8} {'HORIZON STATE'}")
        print("-" * 75)
        for nid, n in graph.nodes.items():
            print(f"{nid:<18} {n['current_value']:<10.2f} {n['z_score']:<+10.2f} {n['abs_extreme_ratio']:<13.1f}% {n['spikes']:<8} {n['state_label']}")
        return

    if args.chokepoints:
        chokes = graph.detect_systemic_chokepoints(top_k=10)
        print(f"\n=== SYSTEMIC CHOKEPOINT CENTRALITY ({universe_id}) ===")
        print(f"{'RANK':<5} {'NODE ID':<18} {'ALPHA':<10} {'BETWEENNESS':<14} {'MAX DOWNSTREAM HHI'}")
        print("-" * 65)
        for i, c in enumerate(chokes, 1):
            print(f"{i:<5} {c['node_id']:<18} {c['chokepoint_alpha']:<10.4f} {c['betweenness']:<14.4f} {c['max_downstream_hhi']:<10.4f}")
        return

    if args.shock:
        shock_res = graph.simulate_shock(args.shock, magnitude=args.magnitude)
        print(f"\n=== MULTI-HOP SHOCK PROPAGATION SIMULATION ===")
        print(f"Source Node: {shock_res['source_id']} ({shock_res['source_label']}) | Magnitude: {shock_res['magnitude']:+.2f}")
        print(f"{'TARGET':<18} {'IMPACT SCORE':<14} {'ARRIVAL LAG':<14} {'CONVERGENT PARENTS'}")
        print("-" * 65)
        for tgt in shock_res["affected_targets"]:
            print(f"{tgt['target']:<18} {tgt['impact_score']:<+14.4f} {tgt['arrival_lag_days']}d{'':<11} {tgt['convergent_parents']} ({', '.join(tgt['parents'])})")
        return

    # Default: Run full foresight brief
    brief = engine.generate_brief()
    md_report = render_markdown_brief(brief, universe_id, lobe_name)
    print(md_report)

    # Persist brief to orchestrator-state
    DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)
    brief_json_path = DEFAULT_STATE_DIR / "macro_foresight_brief.json"
    brief_md_path = DEFAULT_STATE_DIR / "macro_foresight_brief.md"

    with open(brief_json_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, indent=2)
    with open(brief_md_path, "w", encoding="utf-8") as f:
        f.write(md_report)

    print(f"\n[OK] Foresight brief written to {brief_json_path} and {brief_md_path}")


if __name__ == "__main__":
    main()
