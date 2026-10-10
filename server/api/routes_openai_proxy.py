"""
OpenAI-Compatible REST Proxy for VS Code and External AI Extensions.
Exposes standard /v1/chat/completions and /v1/models endpoints backed by
the pooled Gemini API Fleet Rotator with automatic 2-tier cooldown and failover.
Seamlessly injects Antigravity system directives, rules (AGENTS.md), and skills.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from google import genai
from google.genai import types, errors

from client.adapters.gemini_api_adapter import DEPRECATED_MODEL_MAP
from client.adapters.gemini_fleet_rotator import GeminiKeyRotator, GeminiKeySlot, get_gemini_rotator
from client.antigravity_bridge import harvest_antigravity_customizations, harvest_chat_context
from tools.copilot_fleet import get_fleet_quota_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["OpenAI Compatible Proxy"])


class ChatMessage(BaseModel):
    role: str
    content: str
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str = "gemini-3.8-flash"
    messages: list[ChatMessage]
    temperature: float | None = 0.2
    max_tokens: int | None = 4096
    stream: bool = False


def _resolve_model(model_name: str) -> str:
    """Translates generic/OpenAI model names to supported Gemini equivalents."""
    cleaned = (model_name or "").lower().strip()
    if cleaned in ("gpt-4o", "gpt-4", "claude-3-5-sonnet", "claude-3.5-sonnet", "auto"):
        return "gemini-3.8-flash"
    if cleaned in ("gpt-4o-mini", "claude-3-haiku"):
        return "gemini-3.5-flash-lite"
    return DEPRECATED_MODEL_MAP.get(cleaned, cleaned or "gemini-3.8-flash")


def _build_system_instruction(custom_system: str | None = None) -> str:
    """
    Harvests Antigravity rules, active skills, and behavioral invariants,
    weaving them into the base system prompt.
    """
    customizations = harvest_antigravity_customizations()
    chat_ctx = harvest_chat_context()

    sections = [
        "You are an expert autonomous software engineer and pair programmer powered by the Antigravity Intelligence Fleet.",
        "Operating Philosophy: Calm authority, high agency, zero conversational fluff, deterministic verification.",
    ]

    rules = customizations.get("rules", [])
    if rules:
        sections.append("\n### Governing Antigravity Invariants:")
        for r in rules:
            sections.append(f"- {r}")

    active_skills = customizations.get("active_skills", [])
    if active_skills:
        sections.append(f"\n### Active Knowledge & Skills Scope: {', '.join(active_skills[:12])}")

    cid = chat_ctx.get("conversation_id")
    if cid:
        sections.append(f"\nConnected Workspace Scope: Conversation ID {cid}")

    if custom_system:
        sections.append(f"\n### Client Specific Directives:\n{custom_system}")

    return "\n".join(sections)


@router.get("/v1/models")
async def list_models():
    """Returns available models in OpenAI-compatible format."""
    now = int(time.time())
    models = [
        {"id": "gemini-3.8-flash", "object": "model", "created": now, "owned_by": "google"},
        {"id": "gemini-3.5-flash-lite", "object": "model", "created": now, "owned_by": "google"},
        {"id": "gemini-3.1-pro-preview", "object": "model", "created": now, "owned_by": "google"},
        {"id": "gpt-4o", "object": "model", "created": now, "owned_by": "fleet-proxy-alias"},
        {"id": "claude-3-5-sonnet", "object": "model", "created": now, "owned_by": "fleet-proxy-alias"},
    ]
    return {"object": "list", "data": models}


@router.get("/v1/fleet/status")
async def get_fleet_telemetry():
    """
    Returns real-time status of both the Gemini API Fleet and Copilot Fleet.
    Used by VS Code Status Bar and Sidebar TreeView without opening external GUIs.
    """
    rotator = get_gemini_rotator()
    gemini_status = rotator.get_status()

    # Copilot metrics
    copilot_status = {}
    try:
        copilot_status = get_fleet_quota_metrics()
    except Exception as e:
        copilot_status = {"error": str(e)}

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gemini_fleet": gemini_status,
        "copilot_fleet": copilot_status,
    }


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.
    Routes to the pooled Gemini API keys in round-robin fashion,
    recovering gracefully from 429 burst rate limits.
    """
    rotator = get_gemini_rotator()
    if rotator.total_keys == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No Gemini API keys registered in fleet. Add GEMINI_API_KEY_1..N into .env.fleet.",
        )

    target_model = _resolve_model(req.model)

    # Separate system messages from user/assistant conversation history
    system_parts: list[str] = []
    contents: list[Any] = []

    for msg in req.messages:
        role = msg.role.lower().strip()
        if role == "system":
            system_parts.append(msg.content)
        elif role == "user":
            contents.append(msg.content)
        elif role == "assistant":
            contents.append(f"Assistant: {msg.content}")

    if not contents:
        contents.append("Hello")

    merged_prompt = "\n\n".join(contents)
    client_system = "\n".join(system_parts) if system_parts else None
    system_instruction = _build_system_instruction(client_system)

    config = types.GenerateContentConfig(
        temperature=req.temperature if req.temperature is not None else 0.2,
        max_output_tokens=req.max_tokens if req.max_tokens is not None else 4096,
        system_instruction=system_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    req_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    # 1. STREAMING MODE
    if req.stream:
        async def event_generator() -> AsyncGenerator[str, None]:
            async def _stream_call(client: genai.Client, slot: GeminiKeySlot):
                stream_resp = await client.aio.models.generate_content_stream(
                    model=target_model,
                    contents=merged_prompt,
                    config=config,
                )
                async for chunk in stream_resp:
                    text_chunk = getattr(chunk, "text", "") or ""
                    if text_chunk:
                        slot.total_tokens += len(text_chunk) // 4
                        data = {
                            "id": req_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": target_model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": text_chunk},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(data)}\n\n"

            # Execute streaming generator with rotator resilience
            slot = await rotator.get_next_slot()
            try:
                slot.total_calls += 1
                stream_resp = await slot.client.aio.models.generate_content_stream(
                    model=target_model,
                    contents=merged_prompt,
                    config=config,
                )
                async for chunk in stream_resp:
                    text_chunk = getattr(chunk, "text", "") or ""
                    if text_chunk:
                        slot.total_tokens += max(1, len(text_chunk) // 4)
                        data = {
                            "id": req_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": target_model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": text_chunk},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(data)}\n\n"
            except errors.APIError as api_err:
                code = getattr(api_err, "code", None)
                msg = str(api_err)
                if code == 429 or "RESOURCE_EXHAUSTED" in msg:
                    rotator.mark_burst_cooldown(slot.key_id, error_msg=msg)
                error_data = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": target_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": f"\n\n[Fleet Warning: Key {slot.key_id} rate limited. Rotating...]"},
                            "finish_reason": "error",
                        }
                    ],
                }
                yield f"data: {json.dumps(error_data)}\n\n"

            # Finalize stream
            end_chunk = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": target_model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
            }
            yield f"data: {json.dumps(end_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # 2. NON-STREAMING MODE
    async def _execute_single(client: genai.Client, slot: GeminiKeySlot):
        resp = await client.aio.models.generate_content(
            model=target_model,
            contents=merged_prompt,
            config=config,
        )
        tokens_used = 0
        if getattr(resp, "usage_metadata", None):
            meta = resp.usage_metadata
            tokens_used = getattr(meta, "total_token_count", 0) or 0
        slot.total_tokens += tokens_used
        return resp, tokens_used

    try:
        response, total_tokens = await rotator.execute_with_retry(_execute_single)
        text_out = getattr(response, "text", "") or ""

        return {
            "id": req_id,
            "object": "chat.completion",
            "created": created_ts,
            "model": target_model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text_out,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": max(1, len(merged_prompt) // 4),
                "completion_tokens": max(1, len(text_out) // 4),
                "total_tokens": total_tokens or (len(merged_prompt) + len(text_out)) // 4,
            },
        }
    except Exception as e:
        logger.error(f"Error in chat_completions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gemini fleet execution error: {str(e)}",
        )
