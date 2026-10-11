"""client/local_llm.py
-------------------
Lightweight client and helper library for communicating with LM Studio / llama.cpp
local server instances (OpenAI-compatible HTTP endpoint).

Stdlib only (urllib) to guarantee zero overhead and zero external dependencies
for lightweight CLI tools, dispatchers, and routers.
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

logger = logging.getLogger("local_llm")

DEFAULT_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
ROUTER_MODEL = os.getenv("FLEET_ROUTER_MODEL", "qwen-intent-router")
WORKER_MODEL = os.getenv("FLEET_LOCAL_WORKER_MODEL", "fleet-master-3b")
HEAVY_MODEL = os.getenv("FLEET_LOCAL_HEAVY_MODEL", "fleet-master-7b")


def is_online(host: str = "127.0.0.1", port: int = 1234, timeout: float = 0.05) -> bool:
    """Fast socket check (<1ms) to verify if LM Studio is listening before issuing HTTP requests."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def get_loaded_models(base_url: str = DEFAULT_BASE_URL, timeout: float = 2.0) -> List[str]:
    """Retrieves list of active model identifiers from LM Studio."""
    if not is_online():
        return []
    url = f"{base_url}/models"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("id") for m in data.get("data", []) if "id" in m]
    except Exception as e:
        logger.debug(f"Failed to query loaded models from {url}: {e}")
        return []


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Tolerantly extracts JSON objects from raw LLM output, stripping markdown fences or prose."""
    if not text:
        return None
    cleaned = text.strip()
    # Match markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    
    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Extract first outer pair of curly braces
    brace_match = re.search(r"(\{[\s\S]*\})", cleaned)
    if brace_match:
        try:
            return json.loads(brace_match.group(1).strip())
        except Exception:
            pass

    return None


def chat_completion(
    model: str,
    messages: List[Dict[str, str]],
    *,
    base_url: str = DEFAULT_BASE_URL,
    temperature: float = 0.0,
    max_tokens: int = 256,
    timeout: float = 5.0,
) -> Optional[str]:
    """Issues a chat completion request to the OpenAI-compatible endpoint."""
    if not is_online():
        return None

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
    except Exception as e:
        if os.getenv("FLEET_ROUTER_DEBUG"):
            logger.warning(f"LM Studio chat completion error on {url} (model {model}): {e}")
        return None
