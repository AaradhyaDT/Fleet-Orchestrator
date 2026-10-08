from __future__ import annotations

import os
from typing import Any

from client.adapters.gemini_api_adapter import GeminiAPIAdapter, DEPRECATED_MODEL_MAP

class GeminiFreeAdapter(GeminiAPIAdapter):
    """
    Backward-compatible adapter for Google Gemini Free Tier.
    Powered by official google-genai SDK (v2.25.0) and Gemini 3.8 Flash.
    Provides free tokens with rate limits handled gracefully.
    """
    def __init__(
        self,
        worker_id: str,
        nickname: str,
        api_key: str | None = None,
        model: str = "gemini-3.8-flash",
        system_instruction: str | None = None,
    ):
        super().__init__(
            worker_id=worker_id,
            nickname=nickname,
            api_key=api_key,
            model=model,
            system_instruction=system_instruction,
        )

__all__ = ["GeminiFreeAdapter", "GeminiAPIAdapter", "DEPRECATED_MODEL_MAP"]
