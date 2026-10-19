"""Local SLM Intent Router Runtime Adapter.

Provides low-latency (<50ms) task classification and skill routing using
fine-tuned Small Language Models (e.g. Qwen2.5-Coder-0.5B-Instruct / LoRA).

Execution Ladder:
1. Local HTTP inference (LM Studio / Ollama / Local Server on localhost:1234/11434)
2. Fast regex/heuristic token classifier (fallback guaranteed <5ms)

Maps tasks into standard Fleet-Orchestrator intent codons:
- CODE_REFACTOR
- SYSTEM_AUDIT
- HARDWARE_SYNTH
- RESEARCH_SYNTHESIS
- FORESIGHT_SIMULATION
- VCS_SYNC
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List
import urllib.request
import urllib.error


@dataclass
class IntentRoutingResult:
    intent_codon: str
    target_skill: str
    confidence: float
    latency_ms: float
    router_source: str  # "LOCAL_SLM_HTTP" | "HEURISTIC_CODON_FALLBACK"
    metadata: Dict[str, Any]


class SLMIntentRouter:
    """Local intent discovery and task allocation router."""

    INTENT_MAP = {
        "CODE_REFACTOR": "github-workflow",
        "SYSTEM_AUDIT": "cyber-forensics",
        "HARDWARE_SYNTH": "edge-ai-model-forge",
        "RESEARCH_SYNTHESIS": "writing-like-claude",
        "FORESIGHT_SIMULATION": "adaptive-workflow",
        "VCS_SYNC": "github-workflow",
    }

    HEURISTIC_RULES = [
        (r"\b(audit|cbf|barrier|security|dfir|forensic|leak)\b", "SYSTEM_AUDIT", 0.92),
        (r"\b(azmuth|sde|simulation|hyperburst|horizon|foresight|universe)\b", "FORESIGHT_SIMULATION", 0.95),
        (r"\b(sync|commit|push|pull|pr|branch|issue)\b", "VCS_SYNC", 0.90),
        (r"\b(imu|spark|freertos|tinyml|esp32|sensor|hardware)\b", "HARDWARE_SYNTH", 0.93),
        (r"\b(paper|report|latex|thesis|research|scholar)\b", "RESEARCH_SYNTHESIS", 0.88),
        (r"\b(refactor|fix|bug|test|pytest|code|feature)\b", "CODE_REFACTOR", 0.89),
    ]

    def __init__(self, http_endpoint: str | None = None):
        # Default to None so tests and local runs without a live server don't waste connection handshake timeouts
        self.http_endpoint = http_endpoint

    def classify_intent(self, prompt: str) -> IntentRoutingResult:
        """Classify task prompt into an intent codon within <50ms."""
        start_time = time.perf_counter()

        # Try fast HTTP local SLM server first if explicitly configured
        if self.http_endpoint:
            result = self._try_http_slm(prompt)
            if result:
                latency = (time.perf_counter() - start_time) * 1000.0
                return IntentRoutingResult(
                    intent_codon=result["codon"],
                    target_skill=self.INTENT_MAP.get(result["codon"], "adaptive-workflow"),
                    confidence=result["confidence"],
                    latency_ms=round(latency, 2),
                    router_source="LOCAL_SLM_HTTP",
                    metadata=result.get("meta", {}),
                )

        # Fallback to high-speed deterministic heuristic (<2ms)
        codon, conf = self._classify_heuristically(prompt)
        latency = (time.perf_counter() - start_time) * 1000.0
        return IntentRoutingResult(
            intent_codon=codon,
            target_skill=self.INTENT_MAP.get(codon, "adaptive-workflow"),
            confidence=conf,
            latency_ms=round(latency, 2),
            router_source="HEURISTIC_CODON_FALLBACK",
            metadata={"prompt_length": len(prompt)},
        )

    def _try_http_slm(self, prompt: str) -> Dict[str, Any] | None:
        """Query local SLM server with an aggressive 15ms timeout."""
        if not self.http_endpoint:
            return None
        try:
            payload = json.dumps({
                "model": "qwen2.5-coder-0.5b-instruct",
                "messages": [
                    {"role": "system", "content": "You are a task classifier. Respond strictly with one of: CODE_REFACTOR, SYSTEM_AUDIT, HARDWARE_SYNTH, RESEARCH_SYNTHESIS, FORESIGHT_SIMULATION, VCS_SYNC."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 10
            }).encode("utf-8")

            req = urllib.request.Request(
                self.http_endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=0.015) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"].strip().upper()
                for key in self.INTENT_MAP:
                    if key in content:
                        return {"codon": key, "confidence": 0.98, "meta": {"raw": content}}
        except Exception:
            return None
        return None

    def _classify_heuristically(self, prompt: str) -> tuple[str, float]:
        """Match against pre-compiled regex codon patterns."""
        p_lower = prompt.lower()
        for pattern, codon, conf in self.HEURISTIC_RULES:
            if re.search(pattern, p_lower):
                return codon, conf
        return "CODE_REFACTOR", 0.70


def run_router_cli() -> None:
    """CLI to test router speed and accuracy."""
    router = SLMIntentRouter()
    test_prompts = [
        "Audit the system for memory leaks and check control barrier function safety",
        "Run 30-day SDE stochastic simulation on A100 hyperburst",
        "Calibrate ESP32 FreeRTOS queue and compute TinyML INT8 fall latency",
        "Sync repository commits and open PR under issue #192",
    ]

    print("=" * 80)
    print("  🧠 LOCAL SLM INTENT ROUTER BENCHMARK")
    print("=" * 80)
    for p in test_prompts:
        res = router.classify_intent(p)
        print(f"Prompt:   '{p}'")
        print(f"  ↳ Codon:      {res.intent_codon}")
        print(f"  ↳ Skill:      {res.target_skill}")
        print(f"  ↳ Source:     {res.router_source}")
        print(f"  ↳ Latency:    {res.latency_ms} ms (Confidence: {res.confidence * 100:.1f}%)")
        print("-" * 80)


if __name__ == "__main__":
    run_router_cli()
