"""Fast Local Intent & Skill Router for Fleet-Orchestrator & Adaptive-Workflow.

Authoritative Single-Source-of-Truth Router with Full 9-Archetype Paradigm Support,
Regex Boundary Disambiguation, Hardware Telemetry, and Deterministic Fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client.local_llm import ROUTER_MODEL, chat_completion, extract_json, is_online

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
GGUF_PATH = MODELS_DIR / "qwen_intent_router_q4_k_m.gguf"

SYSTEM_PROMPT = (
    "You are the high-speed Intent, Skill, and Task Time Allocation Router for the Aaradhya development ecosystem. "
    "Classify the incoming user intent into the exact lifecycle archetype, tier, 2D matrix cell, "
    "primary skill, supporting skills, velocity profile, and task time allocation (tier, estimated_duration_s, "
    "timeout_ceiling_s, cpm_weight, execution_route) in strict JSON format."
)

ALL_ARCHETYPES = [
    "ENGINEERING_DEV",
    "DOMAIN_HARDWARE",
    "DOMAIN_AEC_CAD",
    "RESEARCH_ACADEMIC",
    "FRONTEND_PRODUCT",
    "SWARM_ORCHESTRATION",
    "SYSADMIN_SECURITY",
    "AI_ENGINEERING_ML",
    "ECOSYSTEM_META",
]

SKILL_ALIASES = {
    "academic-notebook-creator": "academic-notebook-architect",
    "notebook-creator": "academic-notebook-architect",
    "notebook-architect": "academic-notebook-architect",
    "academic-notebook": "academic-notebook-architect",
    "embedded-firmware-compiler": "embedded-firmware-scaffold",
    "firmware-driver": "embedded-firmware-scaffold",
    "firmware-scaffold": "embedded-firmware-scaffold",
    "academic-workflow": "adaptive-workflow",
    "adaptive-orchestrator": "adaptive-workflow",
    "colab": "colab-cloud-accelerator",
    "colab-accelerator": "colab-cloud-accelerator",
    "colab-cloud": "colab-cloud-accelerator",
    "colab-mcp": "colab-cloud-accelerator",
    "fusemachines": "ai-engineering-fellowship",
    "fusemachines-fellowship": "ai-engineering-fellowship",
    "fellowship": "ai-engineering-fellowship",
    "ai-fellowship": "ai-engineering-fellowship",
    "ai-engineering": "ai-engineering-fellowship",
    "fuseaif": "ai-engineering-fellowship",
}


def _matches_any_pattern(text: str, patterns: List[str]) -> bool:
    """Checks if any regex pattern matches text using word boundaries where applicable."""
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def _resolve_copilot_tier_and_model(cell: str, policy: str, prompt: str) -> Tuple[str, Optional[str]]:
    """Maps 2D Matrix Cell to 1st-Party Copilot CLI Auto-Tier and Model Escalation."""
    p = prompt.lower()
    if cell in ["(V2, R1)", "(V2, R2)"] or any(k in p for k in ["architectural refactor", "deadlock", "z3", "formal proof"]):
        return "intelligence", "gemini-3.8-flash"
    elif cell in ["(V0, R2)", "(V1, R2)"] or policy in ["SURGICAL_LOCK", "DECOUPLED_SLICES"]:
        return "intelligence", None
    elif cell in ["(V0, R1)", "(V1, R1)"] or policy in ["BRANCH_GUARD", "STAR_SUBAGENTS"]:
        return "balance", None
    else:
        return "efficiency", None


def _compute_time_allocation(prompt: str, archetype: str, tier: str, policy: str) -> Dict[str, Any]:
    """Computes deterministic duration and timeout allocation bounds from prompt semantics."""
    p = prompt.lower()
    word_count = len(prompt.split())

    if policy == "FLEET_SWARM" or any(k in p for k in ["batch", "swarm", "fleet", "worker pool"]):
        duration_s = 240
        time_tier = "T3_LONG"
        route = "FLEET_WORKER"
    elif archetype == "AI_ENGINEERING_ML" or any(k in p for k in ["mlops", "text-to-sql", "vision transformers", "rag assistant", "fellowship"]):
        duration_s = 90
        time_tier = "T2_MEDIUM"
        route = "SUBAGENT"
    elif policy == "STAR_SUBAGENTS" or any(k in p for k in ["scaffold", "pipeline", "syllabus"]):
        duration_s = 120
        time_tier = "T2_MEDIUM"
        route = "SUBAGENT"
    elif policy == "SURGICAL_LOCK" or any(k in p for k in ["refactor", "audit", "access.js"]):
        duration_s = 75
        time_tier = "T2_MEDIUM"
        route = "SUBAGENT"
    elif tier == "Tier 2" or word_count > 25:
        duration_s = 50
        time_tier = "T1_FAST"
        route = "SUBAGENT"
    elif word_count < 8 and policy == "DIRECT_FAST":
        duration_s = 12
        time_tier = "T0_MICRO"
        route = "LOCAL_SLM"
    else:
        duration_s = 35
        time_tier = "T1_FAST"
        route = "DIRECT_FAST"

    timeout_s = min(1200, max(30, int(duration_s * 2.2)))
    cpm_w = round(max(0.5, duration_s / 30.0), 2)

    return {
        "tier": time_tier,
        "estimated_duration_s": duration_s,
        "timeout_ceiling_s": timeout_s,
        "cpm_weight": cpm_w,
        "execution_route": route,
    }


def _heuristic_fallback(prompt: str) -> Dict[str, Any]:
    """Deterministic keyword & regex boundary fallback matching all 9 adaptive-workflow archetypes."""
    p = prompt.lower()

    # 1. AI_ENGINEERING_ML
    ml_patterns = [
        r"\b(fusemachines|fellowship|fuseaif)\b",
        r"\b(text-to-sql|text2sql|telco churn|tree ensembles|shap)\b",
        r"\b(neu steel|defect cnn|vision transformers|clip zero-shot|ner sequence)\b",
        r"\b(rag assistant|eval harness|mlops|biasaperture|fairness audit)\b",
    ]
    if _matches_any_pattern(p, ml_patterns):
        arch = "AI_ENGINEERING_ML"
        tier = "Tier 2"
        cell = "(V1, R1)"
        pol = "STAR_SUBAGENTS"
        pskill = "ai-engineering-fellowship"
        sup = ["colab-cloud-accelerator", "compliance-report-harmonizer"]
        velo = "BALANCED"

    # 2. SWARM_ORCHESTRATION & CLOUD ACCELERATION
    elif any(k in p for k in ["colab", "unsloth", "cuda"]) and any(k in p for k in ["gpu", "tpu", "fine-tune", "notebook"]):
        arch = "SWARM_ORCHESTRATION"
        tier = "Tier 1"
        cell = "(V1, R1)"
        pol = "STAR_SUBAGENTS"
        pskill = "colab-cloud-accelerator"
        sup = ["slm-router-forge"]
        velo = "TURBO"
    elif any(k in p for k in ["scout", "reviewer", "writer", "lead"]) and "swarm" in p or "agent-teams" in p or "teamwork" in p:
        arch = "SWARM_ORCHESTRATION"
        tier = "Tier 2"
        cell = "(V1, R1)"
        pol = "STAR_SUBAGENTS"
        pskill = "agent-teams-orchestration"
        sup = ["fleet-orchestrator"]
        velo = "TURBO"
    elif any(k in p for k in ["swarm", "fleet", "worker pool", "copilot-w", "copilot fleet"]):
        arch = "SWARM_ORCHESTRATION"
        tier = "Tier 2"
        cell = "(V2, R0)"
        pol = "FLEET_SWARM"
        pskill = "fleet-orchestrator"
        sup = ["adaptive-workflow"]
        velo = "TURBO"

    # 3. RESEARCH_ACADEMIC
    elif any(k in p for k in ["beamer", "thesis", "capstone report"]) or (any(k in p for k in ["latex", "tex"]) and "report" in p):
        arch = "RESEARCH_ACADEMIC"
        tier = "Tier 2"
        cell = "(V1, R1)"
        pol = "STAR_SUBAGENTS"
        pskill = "latex-thesis-architect"
        sup = ["writing-like-claude"]
        velo = "BALANCED"
    elif any(k in p for k in ["iv-ii", "iv-i", "syllabus", "semester", "super-nlm", "notebooklm", "studyhub", "notes"]):
        arch = "RESEARCH_ACADEMIC"
        tier = "Tier 2" if "scaffold" in p or "batch" in p else "Tier 1"
        cell = "(V1, R1)"
        pol = "STAR_SUBAGENTS"
        pskill = "academic-notebook-architect" if "scaffold" in p or "notes" in p else "super-nlm"
        sup = ["fleet-orchestrator"]
        velo = "TURBO" if "batch" in p or "scaffold" in p else "BALANCED"

    # 4. DOMAIN_AEC_CAD
    elif any(k in p for k in ["cad", "fusion360", "autodesk", "revit", "etabs", "bim", "makerspace", "3d model"]):
        arch = "DOMAIN_AEC_CAD"
        tier = "Tier 2"
        cell = "(V0, R1)"
        pol = "BRANCH_GUARD"
        pskill = "fusion360-mcp"
        sup = ["makerspace"]
        velo = "BALANCED"

    # 5. DOMAIN_HARDWARE
    elif any(k in p for k in ["antenna", "friis", "link budget", "vswr", "microwave", "telecom"]):
        arch = "DOMAIN_HARDWARE"
        tier = "Tier 2"
        cell = "(V0, R1)"
        pol = "BRANCH_GUARD"
        pskill = "rf-link-budget-calc"
        sup = ["avionic-telecom-analyzer"]
        velo = "BALANCED"
    elif any(k in p for k in ["filter", "bode", "nyquist", "transfer function", "pid", "control loop"]):
        arch = "DOMAIN_HARDWARE"
        tier = "Tier 2"
        cell = "(V0, R1)"
        pol = "BRANCH_GUARD"
        pskill = "control-systems-sim" if "pid" in p or "bode" in p else "dsp-signal-engine"
        sup = ["electronics-circuit-synth"]
        velo = "BALANCED"
    elif any(k in p for k in ["firmware", "dsp", "radar", "stm32", "freertos", "hal", "isr", "microcontroller"]):
        arch = "DOMAIN_HARDWARE"
        tier = "Tier 2"
        cell = "(V0, R1)"
        pol = "BRANCH_GUARD"
        pskill = "embedded-firmware-scaffold"
        sup = ["systems-concurrency-harness"]
        velo = "BALANCED"

    # 6. SYSADMIN_SECURITY
    elif any(k in p for k in ["alternate data stream", "pe header", "forensic", "triage artifact", "incident response"]) or ("ads" in p.split()):
        arch = "SYSADMIN_SECURITY"
        tier = "Tier 1"
        cell = "(V0, R1)"
        pol = "BRANCH_GUARD"
        pskill = "cyber-forensics"
        sup = ["win-vault"]
        velo = "BALANCED"
    elif any(k in p for k in ["win-vault", "vault.bat", "acl", "ntfs access control"]) or (r"\block\b" in p and any(k in p for k in ["folder", "directory", "secret", "confidential"])):
        arch = "SYSADMIN_SECURITY"
        tier = "Tier 1"
        cell = "(V0, R1)"
        pol = "BRANCH_GUARD"
        pskill = "win-vault"
        sup = ["cyber-forensics"]
        velo = "BALANCED"

    # 7. FRONTEND_PRODUCT
    elif any(k in p for k in ["portfolio", "aaradhyadt.github.io", "access.js", "projects.html"]) or ("project" in p and "onboard" in p):
        arch = "FRONTEND_PRODUCT"
        tier = "Tier 1"
        cell = "(V0, R2)" if "access.js" in p or "project" in p else "(V0, R1)"
        pol = "SURGICAL_LOCK" if "access.js" in p else "BRANCH_GUARD"
        pskill = "portfolio-project-manager" if "project" in p or "access.js" in p else "design-taste-frontend"
        sup = ["modern-web-guidance", "github-workflow"]
        velo = "BALANCED"
    elif any(k in p for k in ["navbar", "css", "html", "react", "widget", "frontend", "tailwind", "shadcn"]) or (r"\bui\b" in p and any(k in p for k in ["component", "layout", "design", "view", "theme", "style", "page", "button", "modal", "screen"])):
        arch = "FRONTEND_PRODUCT"
        tier = "Tier 1"
        cell = "(V0, R1)"
        pol = "BRANCH_GUARD"
        pskill = "design-taste-frontend"
        sup = ["modern-web-guidance"]
        velo = "BALANCED"

    # 8. ECOSYSTEM_META
    elif any(k in p for k in ["slm forge", "train local classifier", "tune intent router", "customization-state-sync", "graphify update"]):
        arch = "ECOSYSTEM_META"
        tier = "Tier 1"
        cell = "(V0, R1)"
        pol = "BRANCH_GUARD"
        pskill = "slm-router-forge"
        sup = ["graphify-optimizer"]
        velo = "BALANCED"

    # 9. Default ENGINEERING_DEV
    else:
        arch = "ENGINEERING_DEV"
        tier = "Tier 1" if len(p.split()) < 15 else "Tier 2"
        cell = "(V0, R0)"
        pol = "DIRECT_FAST"
        pskill = "writing-like-claude" if "calm authority" in p or "release dossier" in p else "github-workflow"
        sup = ["pr-review-toolkit"]
        velo = "BALANCED"

    time_alloc = _compute_time_allocation(prompt, arch, tier, pol)
    auto_tier, rec_model = _resolve_copilot_tier_and_model(cell, pol, prompt)

    return {
        "archetype": arch,
        "tier": tier,
        "matrix_cell": cell,
        "policy": pol,
        "primary_skill": pskill,
        "supporting_skills": sup,
        "velocity": velo,
        "time_allocation": time_alloc,
        "auto_tier": auto_tier,
        "recommended_copilot_model": rec_model,
        "source": "heuristic_fallback",
    }


def _call_lm_studio(prompt: str) -> Optional[Dict[str, Any]]:
    """Attempts inference via local LM Studio server if running."""
    if not is_online():
        if os.getenv("FLEET_ROUTER_DEBUG"):
            logger.info("LM Studio socket offline, falling back to heuristic")
        return None

    model_name = os.getenv("FLEET_ROUTER_MODEL", ROUTER_MODEL)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    raw_resp = chat_completion(
        model=model_name,
        messages=messages,
        temperature=0.0,
        max_tokens=250,
        timeout=5.0,
    )
    if not raw_resp:
        if os.getenv("FLEET_ROUTER_DEBUG"):
            logger.warning(f"LM Studio empty or failed response for model '{model_name}'")
        return None

    result = extract_json(raw_resp)
    if not result or not isinstance(result, dict):
        if os.getenv("FLEET_ROUTER_DEBUG"):
            logger.warning(f"Failed to parse valid JSON from model response: {raw_resp[:120]}")
        return None

    # Enforce essential invariant keys
    if "archetype" not in result:
        if os.getenv("FLEET_ROUTER_DEBUG"):
            logger.warning("Missing 'archetype' key in parsed JSON; falling back to heuristic")
        return None

    # Alias normalization for primary_skill
    ps = result.get("primary_skill")
    if ps in SKILL_ALIASES:
        result["primary_skill"] = SKILL_ALIASES[ps]

    result["source"] = f"lm_studio_{model_name}"
    if "time_allocation" not in result:
        result["time_allocation"] = _compute_time_allocation(
            prompt,
            result.get("archetype", "ENGINEERING_DEV"),
            result.get("tier", "Tier 1"),
            result.get("policy", "DIRECT_FAST"),
        )
    if "auto_tier" not in result:
        cell = result.get("matrix_cell", "(V0, R0)")
        pol = result.get("policy", "DIRECT_FAST")
        auto_tier, rec_model = _resolve_copilot_tier_and_model(cell, pol, prompt)
        result["auto_tier"] = auto_tier
        result["recommended_copilot_model"] = rec_model
    return result


def route_intent(prompt: str) -> Dict[str, Any]:
    """Primary routing entrypoint. Returns routing metadata and latency_ms."""
    start_time = time.perf_counter()

    # 1. Try local LM Studio / llama.cpp if active
    res = _call_lm_studio(prompt)

    # 2. If not running, use zero-latency deterministic fallback
    if not res:
        res = _heuristic_fallback(prompt)

    # 3. Resolve active hardware target
    try:
        from tools.npu_engine import TriHardwareEngine
        hw = TriHardwareEngine.get_hardware_status()
        res["hardware_target"] = hw.get("runtimes", {}).get("active_priority_target", "CPU")
    except Exception:
        res["hardware_target"] = "CPU"

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    res["latency_ms"] = round(elapsed_ms, 2)
    return res


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Scaffold IOE semester IV-II notes for CE 752 and share via super-nlm"
    output = route_intent(query)
    print(json.dumps(output, indent=2))
