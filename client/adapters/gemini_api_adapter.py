from __future__ import annotations

import os
from typing import Any
from google import genai
from google.genai import types, errors

from client.adapters.base_adapter import BaseWorkerAdapter

# Model migration mapping: strictly eliminate deprecated models
DEPRECATED_MODEL_MAP: dict[str, str] = {
    "gemini-2.5-flash": "gemini-3.8-flash",
    "gemini-2.5-pro": "gemini-3.1-pro-preview",
    "gemini-2.0-flash": "gemini-3.8-flash",
    "gemini-2.0-flash-exp": "gemini-3.8-flash",
    "gemini-1.5-flash": "gemini-3.8-flash",
    "gemini-1.5-pro": "gemini-3.1-pro-preview",
}

class GeminiAPIAdapter(BaseWorkerAdapter):
    """
    Modern Gemini API Adapter powered by official google-genai SDK (v2.25.0).
    Supports Gemini 3.8 Flash (default) and Gemini 3.5 Flash-Lite.
    Extracts usage token telemetry and maps API rate limits gracefully.
    """

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        api_key: str | None = None,
        model: str = "gemini-3.8-flash",
        system_instruction: str | None = None,
        rotator: Any | None = None,
    ):
        super().__init__(
            worker_id,
            nickname,
            ["research", "writing", "qa", "seo", "formatting", "code_review"]
        )
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
        # Automatic deprecated model translation
        self.model = DEPRECATED_MODEL_MAP.get(model, model)
        self.system_instruction = system_instruction
        self._client: genai.Client | None = None
        self.rotator = rotator

    def get_client(self) -> genai.Client:
        """Lazily initialize the google-genai SDK Client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("Missing GEMINI_API_KEY")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def check_health(self) -> bool:
        """Returns True if api_key or rotator with healthy keys is configured."""
        if self.rotator and self.rotator.healthy_keys > 0:
            return True
        return bool(self.api_key)

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Executes work specified in `spec` via Gemini API asynchronously.
        Returns dictionary with success, summary, result_text, tokens, and error.
        """
        if not self.api_key and not (self.rotator and self.rotator.healthy_keys > 0):
            return {
                "success": False,
                "error": "Missing GEMINI_API_KEY",
                "summary": "",
                "result_text": "",
                "tokens": {}
            }

        prompt = (
            f"You are a specialized AI worker operating in stage: {stage}.\n"
            f"TASK SPECIFICATION:\n{spec}\n\n"
            f"Produce your final deliverable adhering strictly to the quality criteria."
        )

        sys_inst = self.system_instruction or context.get("system_instruction")
        temperature = float(context.get("temperature", 0.2))
        max_output_tokens = int(context.get("max_output_tokens", 4096))

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=sys_inst,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        try:
            if self.rotator:
                async def _call_gemini(cl: genai.Client, slot: Any):
                    res = await cl.aio.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=config,
                    )
                    if getattr(res, "usage_metadata", None):
                        meta = res.usage_metadata
                        slot.total_tokens += getattr(meta, "total_token_count", 0) or 0
                    return res
                response = await self.rotator.execute_with_retry(_call_gemini)
            else:
                client = self.get_client()
                response = await client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )

            tokens: dict[str, int] = {}
            if getattr(response, "usage_metadata", None):
                meta = response.usage_metadata
                tokens = {
                    "prompt": getattr(meta, "prompt_token_count", 0) or 0,
                    "candidates": getattr(meta, "candidates_token_count", 0) or 0,
                    "total": getattr(meta, "total_token_count", 0) or 0,
                }

            result_text = getattr(response, "text", "") or ""
            return {
                "success": True,
                "summary": f"Completed {stage} via {self.model}",
                "result_text": result_text,
                "tokens": tokens,
                "error": None,
            }
        except errors.APIError as e:
            err_msg = getattr(e, "message", None) or str(e)
            if getattr(e, "code", None) == 429:
                return {
                    "success": False,
                    "error": "RATE_LIMIT_429",
                    "summary": "",
                    "result_text": "",
                    "tokens": {},
                    "details": err_msg,
                }
            return {
                "success": False,
                "error": f"APIError {getattr(e, 'code', 'unknown')}: {err_msg}",
                "summary": "",
                "result_text": "",
                "tokens": {}
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Gemini execution error: {str(e)}",
                "summary": "",
                "result_text": "",
                "tokens": {}
            }
