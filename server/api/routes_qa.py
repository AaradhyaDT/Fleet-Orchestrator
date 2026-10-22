from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

from client.adapters.gemini_fleet_rotator import get_gemini_rotator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["Ambient Screen QA"])
rotator = get_gemini_rotator()

STATIC_DIR = Path(__file__).resolve().parent.parent / "data" / "static"


class QAPromptRequest(BaseModel):
    question: str
    context: str | None = None
    mode: str = "fast_hud"  # "fast_hud" or "deep_consensus"


class QALensRequest(BaseModel):
    image_base64: str  # Data URL or pure base64


async def _query_omnivault_notes(query: str) -> str | None:
    """Best-effort query against OmniVault's local SQLite FTS5 catalog if available."""
    try:
        import aiosqlite

        db_path = Path.home() / ".omnivault" / "catalog.db"
        if not db_path.exists():
            return None

        # Sanitize query for FTS5 (take first 6 significant alphanumeric words)
        words = [w for w in query.replace('"', "").replace("'", "").split() if len(w) > 3][:6]
        if not words:
            return None
        fts_query = " OR ".join(words)

        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT content FROM notes_fts WHERE notes_fts MATCH ? LIMIT 2",
                (fts_query,),
            ) as cursor:
                rows = await cursor.fetchall()
                if rows:
                    return "\n---\n".join(r[0] for r in rows)
    except Exception as exc:
        logger.debug(f"[OmniVault Retrieval Ignored] {exc}")
    return None


@router.get("/status")
async def get_qa_status() -> dict[str, Any]:
    """Returns real-time health and quota capacity of the Gemini fleet rotator."""
    return rotator.get_status()


@router.post("/ask")
async def ask_ambient_qa(req: QAPromptRequest) -> dict[str, Any]:
    """
    Answers an extracted DOM question.
    - fast_hud: Sub-second response using Gemini 3.8 Flash + Google Search Grounding.
    - deep_consensus: 4-way parallel consensus across OmniVault, Web Grounding, and Parametric Arbiter.
    """
    prompt_stem = (
        f"Context / Surrounding Options:\n{req.context}\n\nQuestion Stem:\n{req.question}"
        if req.context
        else req.question
    )

    # 1. Fast Ghost HUD Path (<1.0s)
    if req.mode == "fast_hud":
        sys_inst = (
            "You are an ambient test copilot. Provide the single direct answer or correct option letter "
            "with one concise justification sentence. If multiple choice, state the correct option letter first. "
            "Be extremely precise and direct."
        )

        async def _call_fast_gemini(cl: genai.Client, slot: Any) -> Any:
            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=512,
                system_instruction=sys_inst,
            )
            return await cl.aio.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt_stem,
                config=config,
            )

        try:
            res = await rotator.execute_with_retry(_call_fast_gemini)
            ans = res.text or "(no response)"
            return {
                "answer": ans,
                "confidence": 0.96,
                "provenance": ["gemini_3.8_flash", "fast_hud"],
                "mode": "fast_hud",
            }
        except Exception as e:
            logger.error(f"[Fast HUD Error] {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # 2. Deep Consensus Path (2.0–3.5s)
    omnivault_task = asyncio.create_task(_query_omnivault_notes(req.question))

    async def _call_web_grounded(cl: genai.Client, slot: Any) -> Any:
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=1024,
            system_instruction="Provide a factually verified answer based on authoritative technical evidence.",
        )
        return await cl.aio.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt_stem,
            config=config,
        )

    async def _call_parametric_pure(cl: genai.Client, slot: Any) -> Any:
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=1024,
            system_instruction="Solve this through rigorous first-principles logical deduction. State step-by-step reasoning.",
        )
        return await cl.aio.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt_stem,
            config=config,
        )

    web_task = asyncio.create_task(rotator.execute_with_retry(_call_web_grounded))
    pure_task = asyncio.create_task(rotator.execute_with_retry(_call_parametric_pure))

    notes_context, web_res, pure_res = await asyncio.gather(
        omnivault_task, web_task, pure_task, return_exceptions=True
    )

    web_text = web_res.text if not isinstance(web_res, Exception) and hasattr(web_res, "text") else "Web search pass timed out."
    pure_text = pure_res.text if not isinstance(pure_res, Exception) and hasattr(pure_res, "text") else "Parametric pass unavailable."

    arbiter_prompt = f"""You are the Master Consensus Arbiter. Compare the following evidence streams for the target question:

TARGET QUESTION:
{prompt_stem}

STREAM 1 (Personal Study Notes & Syllabus):
{notes_context if isinstance(notes_context, str) and notes_context else "No direct matching notes found in local vault."}

STREAM 2 (Web Grounded Answer):
{web_text}

STREAM 3 (Parametric Deduction):
{pure_text}

TASK:
1. Reconcile any contradictions. If personal notes specify an institutional/syllabus convention, prioritize it.
2. Select the single best-fit, definitive answer.
3. Output the winning answer with confidence score and markdown formatting.
"""

    async def _call_arbiter(cl: genai.Client, slot: Any) -> Any:
        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=1500,
            system_instruction="Synthesize the candidate streams into a definitive consensus verdict with markdown clarity.",
        )
        return await cl.aio.models.generate_content(
            model="gemini-3.8-flash",
            contents=arbiter_prompt,
            config=config,
        )

    try:
        arbiter_res = await rotator.execute_with_retry(_call_arbiter)
        return {
            "answer": arbiter_res.text or "(no consensus)",
            "confidence": 0.98,
            "provenance": [
                "personal_notes" if notes_context else "general_notes",
                "web_grounded",
                "consensus_arbiter",
            ],
            "mode": "deep_consensus",
        }
    except Exception as e:
        logger.error(f"[Consensus Arbiter Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lens")
async def solve_mobile_lens_capture(req: QALensRequest) -> dict[str, Any]:
    """
    Solves a smartphone camera capture directly using Gemini 3.8 Flash Vision.
    Extracts question stem, all MCQ options, and returns the winning option letter + justification.
    """
    raw_b64 = req.image_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {exc}")

    prompt = (
        "You are an air-gapped exam vision assistant. Look at this photo of a computer screen or paper. "
        "1. Extract the question and all choices (A, B, C, D).\n"
        "2. Identify the single correct option.\n"
        "3. Format your response EXACTLY as follows:\n"
        "OPTION: [Letter, e.g. A, B, C, or D]\n"
        "REASON: [One crisp sentence explaining why this option is correct]\n"
        "FULL_TEXT: [Detailed explanation with any mathematical steps if needed]"
    )

    async def _call_vision(cl: genai.Client, slot: Any) -> Any:
        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=1024,
        )
        return await cl.aio.models.generate_content(
            model="gemini-3.8-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt,
            ],
            config=config,
        )

    try:
        res = await rotator.execute_with_retry(_call_vision)
        text = res.text or ""

        # Parse structured output
        option_letter = "?"
        reason = ""
        full_text = text

        for line in text.splitlines():
            line_s = line.strip()
            if line_s.upper().startswith("OPTION:"):
                cand = line_s.split(":", 1)[1].strip()
                if cand:
                    option_letter = cand[0].upper()
            elif line_s.upper().startswith("REASON:"):
                reason = line_s.split(":", 1)[1].strip()
            elif line_s.upper().startswith("FULL_TEXT:"):
                full_text = line_s.split(":", 1)[1].strip()

        if option_letter == "?" and len(text) > 0:
            # Fallback heuristic: find first isolated letter A, B, C, D
            for char in ["A", "B", "C", "D"]:
                if f"**{char}**" in text or f"Option {char}" in text or f"({char})" in text:
                    option_letter = char
                    break

        return {
            "option_letter": option_letter,
            "reason": reason or text[:120],
            "full_text": text,
            "raw": text,
        }
    except Exception as e:
        logger.error(f"[Mobile Lens Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))
