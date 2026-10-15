"""
Worker Adapter for Tiered Deterministic Symbolic Mathematics.

Allows Fleet-Orchestrator worker queues and Sentinel DAG planners to route
calculus, EKF Jacobians, Laplace transforms, and C-code generation tasks to
the local SymPy/Wolfram tiered engine rather than burning LLM reasoning tokens.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from client.adapters.base_adapter import BaseWorkerAdapter
from tools.symbolic_math_adapter import (
    SymbolicRequest,
    SymbolicResult,
    TieredSymbolicDispatcher,
)

logger = logging.getLogger("fleet.symbolic_adapter")


class SymbolicWorkerAdapter(BaseWorkerAdapter):
    """Headless worker adapter providing exact symbolic mathematics compute."""

    def __init__(
        self,
        worker_id: str = "worker_symbolic_math",
        nickname: str = "Deterministic Math Engine",
        capabilities: Optional[List[str]] = None,
        dispatcher: Optional[TieredSymbolicDispatcher] = None,
    ) -> None:
        caps = capabilities or [
            "math",
            "calculus",
            "jacobian",
            "c_code",
            "symbolic_solve",
            "laplace_transform",
        ]
        super().__init__(worker_id, nickname, caps)
        self.dispatcher = dispatcher or TieredSymbolicDispatcher()

    async def check_health(self) -> bool:
        """Check if at least Tier 1 (SymPy) or Tier 2 (Wolfram) is operational."""
        return self.dispatcher.tier1.is_available() or self.dispatcher.tier2.is_available()

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute symbolic math request.
        Spec can be:
        1. A JSON string matching SymbolicRequest schema
        2. A structured dictionary passed via context['symbolic_request']
        3. A simple text instruction
        """
        req: Optional[SymbolicRequest] = None

        # Check context first
        if "symbolic_request" in context and isinstance(context["symbolic_request"], dict):
            try:
                req = SymbolicRequest(**context["symbolic_request"])
            except Exception as e:
                logger.warning(f"Failed to parse context['symbolic_request']: {e}")

        # Try parsing spec as JSON
        if not req and spec.strip().startswith("{") and spec.strip().endswith("}"):
            try:
                data = json.loads(spec.strip())
                req = SymbolicRequest(**data)
            except Exception as e:
                logger.warning(f"Failed to parse spec as JSON: {e}")

        # Fallback heuristic parser from raw spec string
        if not req:
            req = self._parse_text_spec(spec)

        if not req:
            return {
                "success": False,
                "error": "Could not parse symbolic math request from spec or context.",
                "summary": "Invalid symbolic request format",
                "result_text": "",
            }

        result: SymbolicResult = self.dispatcher.execute(req)

        summary_parts = [
            f"Executed '{req.operation}' via {result.tier_name}",
            f"in {result.execution_time_ms:.2f}ms",
        ]
        if result.fallback_triggered:
            summary_parts.append("(Tier 2 fallback escalated)")

        return {
            "success": result.success,
            "tier_used": result.tier_used,
            "tier_name": result.tier_name,
            "summary": " ".join(summary_parts),
            "result_text": result.result,
            "c_code": result.c_code,
            "latex": result.latex,
            "fallback_triggered": result.fallback_triggered,
            "error": result.error,
        }

    def _parse_text_spec(self, text: str) -> Optional[SymbolicRequest]:
        """Heuristic extractor for natural language math instructions."""
        lower = text.lower()
        if "jacobian" in lower:
            # Extract expression after jacobian
            return SymbolicRequest(operation="jacobian", expression=text, variables=["x", "y"])
        elif "diff" in lower or "derivative" in lower:
            return SymbolicRequest(operation="diff", expression=text, variables=["x"])
        elif "integrate" in lower or "integral" in lower:
            return SymbolicRequest(operation="integrate", expression=text, variables=["x"])
        elif "laplace" in lower:
            return SymbolicRequest(operation="laplace", expression=text, variables=["t", "s"])
        elif "c code" in lower or "c_code" in lower or "export c" in lower:
            return SymbolicRequest(operation="c_code", expression=text)
        elif "solve" in lower:
            return SymbolicRequest(operation="solve", expression=text, variables=["x"])
        return None
