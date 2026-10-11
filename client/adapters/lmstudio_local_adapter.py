from __future__ import annotations
 
import os
from typing import Any
import httpx

from client.adapters.base_adapter import BaseWorkerAdapter
from client.local_llm import DEFAULT_BASE_URL, WORKER_MODEL


class LMStudioLocalAdapter(BaseWorkerAdapter):
    """
    Adapter for local LLM models served via LM Studio / llama.cpp OpenAI-compatible API.
    Zero-cost local inference for preprocessing, formatting, extraction, and code generation.
    """

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        base_url: str | None = None,
        model: str | None = None,
    ):
        resolved_model = model or os.getenv("LMSTUDIO_MODEL") or os.getenv("FLEET_LOCAL_WORKER_MODEL", WORKER_MODEL)
        caps = ["research", "qa", "formatting", "writing"]
        if "7b" in resolved_model.lower():
            caps.append("code")

        super().__init__(worker_id, nickname, caps)
        self.base_url = (base_url or os.getenv("LMSTUDIO_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model = resolved_model

    async def check_health(self) -> bool:
        """Verifies LM Studio server endpoint is healthy and responding."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{self.base_url}/models")
                return r.status_code == 200
        except Exception:
            return False

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            f"SYSTEM: You are a specialized local AI engine executing stage: {stage}.\n"
            f"TASK SPECIFICATION:\n{spec}\n\n"
            f"OUTPUT DELIVERABLE:"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        }

        timeout_sec = 300.0 if "7b" in self.model.lower() else 120.0
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                r = await client.post(f"{self.base_url}/chat/completions", json=payload)
                if r.status_code != 200:
                    return {
                        "success": False,
                        "error": f"LM Studio HTTP {r.status_code} ({self.model}): {r.text}",
                        "summary": "",
                        "result_text": "",
                    }

                data = r.json()
                try:
                    result_text = data["choices"][0]["message"]["content"]
                    return {
                        "success": True,
                        "summary": f"Completed {stage} locally via {self.model}",
                        "result_text": result_text,
                        "error": None,
                    }
                except (KeyError, IndexError, TypeError) as e:
                    return {
                        "success": False,
                        "error": f"Invalid LM Studio response payload for {self.model}: {e}",
                        "summary": "",
                        "result_text": "",
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"LM Studio connection error ({self.model}): {e}",
                "summary": "",
                "result_text": "",
            }
