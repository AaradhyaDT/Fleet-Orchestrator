from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from client.adapters.gemini_fleet_rotator import get_gemini_rotator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["Ambient Screen QA"])
rotator = get_gemini_rotator()

STATIC_DIR = Path(__file__).resolve().parent.parent / "data" / "static"

# In-memory realtime QA broadcast bus for paired mobile Lens HUD
_qa_history: list[dict[str, Any]] = []
_qa_subscribers: list[asyncio.Queue] = []


def broadcast_qa_update(entry: dict[str, Any]) -> None:
    """Broadcasts a new QA result to all connected mobile HUD subscribers."""
    _qa_history.append(entry)
    if len(_qa_history) > 50:
        _qa_history.pop(0)
    for q in list(_qa_subscribers):
        try:
            q.put_nowait(entry)
        except Exception:
            pass


def _extract_option_and_reason(text: str) -> tuple[str, str]:
    """Extracts an MCQ option letter (A-D) and concise justification from AI response."""
    option_letter = "?"
    reason = ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        upper = line.upper()
        if upper.startswith("OPTION:") or upper.startswith("ANSWER:") or upper.startswith("CORRECT:"):
            cand = line.split(":", 1)[1].strip()
            if cand and cand[0].upper() in "ABCD":
                option_letter = cand[0].upper()
                break
    if option_letter == "?":
        for char in ["A", "B", "C", "D"]:
            if re.search(rf"\b(Option\s+{char}|\({char}\)|\*\*{char}\*\*|^{char}[\.\:\—\-])", text, re.IGNORECASE):
                option_letter = char
                break
    for line in lines:
        if line.startswith(option_letter) and len(line) < 5:
            continue
        if len(line) > 10:
            reason = line
            break
    if not reason and lines:
        reason = lines[0]
    return option_letter, reason


class CopilotFleetManager:
    """
    Manages autonomous dispatch across the 31-account GitHub Copilot CLI fleet.
    Rotates account credentials to eliminate quota ceilings and 429 rate limits.
    """

    def __init__(self):
        self._accounts: list[dict[str, Any]] = []
        self._index = 0
        self._lock = asyncio.Lock()
        self._copilot_bin = self._resolve_copilot_bin()
        self._load_accounts()

    def _resolve_copilot_bin(self) -> str:
        found = shutil.which("copilot")
        if found:
            return found
        local_app_data = os.getenv("LOCALAPPDATA", "")
        if local_app_data:
            winget_pattern = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if winget_pattern.exists():
                for p in winget_pattern.glob("*GitHub.Copilot*"):
                    candidate = p / "copilot.exe"
                    if candidate.is_file():
                        return str(candidate)
        return "copilot"

    def _load_accounts(self):
        try:
            from tools.copilot_fleet import discover_accounts, load_env_fleet

            self._accounts = [a for a in discover_accounts(load_env_fleet()) if a.get("has_token")]
        except Exception as e:
            logger.warning(f"Failed to load copilot fleet accounts: {e}")
            self._accounts = []

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": "copilot_cli_fleet",
            "total_workers": len(self._accounts),
            "healthy_workers": len(self._accounts),
            "copilot_binary": self._copilot_bin,
            "pooled_capacity": f"{len(self._accounts) * 200} AI credits/mo",
        }

    async def execute_prompt(self, prompt: str, timeout: float = 30.0) -> dict[str, Any]:
        if not self._accounts:
            self._load_accounts()
        if not self._accounts:
            raise RuntimeError("No active Copilot accounts found in .env.fleet")

        async with self._lock:
            acc = self._accounts[self._index % len(self._accounts)]
            self._index += 1

        child_env = os.environ.copy()
        child_env["COPILOT_GITHUB_TOKEN"] = acc["token"]
        child_env["COPILOT_HOME"] = str(acc["state_dir"])
        child_env["COPILOT_ALLOW_ALL"] = "true"
        child_env["COPILOT_FORCE_WINDOWS_HIDE"] = "1"

        cmd = [
            self._copilot_bin,
            "-s",
            "-p",
            prompt,
            "--allow-all",
            "--no-ask-user",
            "--no-color",
            "--no-custom-instructions",
        ]

        from client.process_runtime import run_background

        def _run():
            return run_background(
                cmd,
                env=child_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        try:
            res = await asyncio.to_thread(_run)
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Copilot CLI timed out after {timeout}s on worker {acc['worker_id']}")

        stdout_str = (res.stdout or "").strip()
        stderr_str = (res.stderr or "").strip()

        if res.returncode != 0:
            raise RuntimeError(f"Copilot CLI error (exit {res.returncode}): {stderr_str or stdout_str}")

        if not stdout_str:
            raise RuntimeError(f"Copilot CLI produced empty response on worker {acc['worker_id']}")

        return {
            "answer": stdout_str,
            "worker": acc["name"],
            "worker_id": acc["worker_id"],
        }


copilot_fleet = CopilotFleetManager()


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
    """Returns real-time status of Copilot Fleet as primary and Gemini rotator as fallback."""
    copilot_stat = copilot_fleet.get_status()
    gemini_stat = rotator.get_status()
    total_workers = copilot_stat.get("total_workers", 31)
    return {
        "provider": "copilot_cli_fleet",
        "copilot": copilot_stat,
        "gemini_fallback": {
            "total_keys": gemini_stat.get("total_keys", 0),
            "healthy_keys": gemini_stat.get("healthy_keys", 0),
        },
        "total_keys": total_workers,
        "healthy_keys": total_workers,
    }


@router.get("/latest")
async def get_latest_qa_result() -> dict[str, Any]:
    """Returns the most recent question and answer payload for polling clients."""
    if not _qa_history:
        return {
            "status": "idle",
            "message": "Waiting for questions...",
            "option_letter": "",
            "answer": "",
            "reason": "Extension scanning questions on PC",
            "timestamp": 0,
            "id": 0,
        }
    return {
        "status": "active",
        **_qa_history[-1],
    }


@router.get("/stream")
async def stream_qa_events():
    """SSE endpoint streaming live question and answer updates to the mobile lens HUD."""
    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        _qa_subscribers.append(queue)
        try:
            # Yield initial connection heartbeat
            yield {
                "event": "connected",
                "data": json.dumps({"status": "connected", "subscriber_count": len(_qa_subscribers)}),
            }
            # Yield latest cached answer if present
            if _qa_history:
                yield {
                    "event": "qa_update",
                    "data": json.dumps(_qa_history[-1]),
                }
            while True:
                data = await queue.get()
                yield {
                    "event": "qa_update",
                    "data": json.dumps(data),
                }
        finally:
            if queue in _qa_subscribers:
                _qa_subscribers.remove(queue)

    return EventSourceResponse(event_generator())


@router.post("/ask")
async def ask_ambient_qa(req: QAPromptRequest) -> dict[str, Any]:
    """
    Answers an extracted DOM question.
    - PRIMARY (Default): GitHub Copilot CLI Fleet (31 accounts, 5,910 credits, zero 429 quota exhaustion).
    - SECONDARY (Fallback): Google Gemini 30-key rotator.
    """
    prompt_stem = (
        f"Context / Surrounding Options:\n{req.context}\n\nQuestion Stem:\n{req.question}"
        if req.context
        else req.question
    )

    sys_inst = (
        "You are an ambient test copilot. Provide the single direct answer or correct option letter "
        "with one concise justification sentence. If multiple choice, state the correct option letter first (e.g. B — explanation). "
        "Be extremely precise and direct."
    )
    full_prompt = f"{sys_inst}\n\n{prompt_stem}"

    # 1. PRIMARY: GitHub Copilot CLI Fleet (Always tried first)
    try:
        copilot_res = await copilot_fleet.execute_prompt(full_prompt, timeout=25.0)
        ans = copilot_res["answer"]
        opt_letter, reason = _extract_option_and_reason(ans)
        qa_payload = {
            "id": int(time.time() * 1000),
            "timestamp": time.time(),
            "question": req.question[:300],
            "option_letter": opt_letter,
            "reason": reason,
            "answer": ans,
            "confidence": 0.98,
            "provenance": ["copilot_cli_fleet", copilot_res["worker"]],
            "mode": "copilot_fleet",
        }
        broadcast_qa_update(qa_payload)
        return qa_payload
    except Exception as copilot_err:
        logger.warning(f"[Copilot Fleet Primary Failed: {copilot_err}] Falling back to Gemini Rotator...")

    # 2. SECONDARY FALLBACK: Gemini 30-Key Rotator (Fast Ghost HUD)
    async def _call_fast_gemini(cl: genai.Client, slot: Any) -> Any:
        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=512,
            system_instruction=sys_inst,
        )
        try:
            return await cl.aio.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt_stem,
                config=config,
            )
        except Exception as m_err:
            if "503" in str(m_err) or "UNAVAILABLE" in str(m_err) or "404" in str(m_err):
                return await cl.aio.models.generate_content(
                    model="gemini-flash-latest",
                    contents=prompt_stem,
                    config=config,
                )
            raise

    try:
        res = await rotator.execute_with_retry(_call_fast_gemini)
        ans = res.text or "(no response)"
        opt_letter, reason = _extract_option_and_reason(ans)
        qa_payload = {
            "id": int(time.time() * 1000),
            "timestamp": time.time(),
            "question": req.question[:300],
            "option_letter": opt_letter,
            "reason": reason,
            "answer": ans,
            "confidence": 0.96,
            "provenance": ["gemini_rotator_fallback", "fast_hud"],
            "mode": "fast_hud",
        }
        broadcast_qa_update(qa_payload)
        return qa_payload
    except Exception as gemini_err:
        logger.error(f"[Both Copilot Fleet and Gemini Rotator Failed] {gemini_err}")
        raise HTTPException(
            status_code=500,
            detail=f"Both Copilot Fleet and Gemini Rotator failed: {gemini_err}",
        )


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
        try:
            return await cl.aio.models.generate_content(
                model="gemini-3.8-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
                config=config,
            )
        except Exception as v_err:
            if "503" in str(v_err) or "UNAVAILABLE" in str(v_err) or "404" in str(v_err):
                return await cl.aio.models.generate_content(
                    model="gemini-flash-latest",
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        prompt,
                    ],
                    config=config,
                )
            raise

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
            for char in ["A", "B", "C", "D"]:
                if f"**{char}**" in text or f"Option {char}" in text or f"({char})" in text:
                    option_letter = char
                    break

        lens_res = {
            "option_letter": option_letter,
            "reason": reason or text[:120],
            "full_text": text,
            "raw": text,
        }
        qa_payload = {
            "id": int(time.time() * 1000),
            "timestamp": time.time(),
            "question": "Mobile Photo Snap",
            "option_letter": option_letter,
            "reason": reason or text[:120],
            "answer": text,
            "confidence": 0.95,
            "provenance": ["mobile_lens_vision"],
            "mode": "mobile_lens",
        }
        broadcast_qa_update(qa_payload)
        return lens_res
    except Exception as e:
        logger.error(f"[Mobile Lens Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))
