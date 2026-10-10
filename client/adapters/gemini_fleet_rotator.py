"""
Gemini API Fleet Key Rotator: Multi-account round-robin rotation with 2-tier cooldown.
Applies the Super-NLM multi-account pool pattern to Google AI Studio Gemini API keys.
Features:
- Thread-safe and async-safe round-robin cursor across N registered API keys.
- Two-tiered rate limiting:
  * Tier 1 (Burst Cooldown): 60-120s cooldown on HTTP 429 / RESOURCE_EXHAUSTED.
  * Tier 2 (Daily Exhaustion): Cooldown until 00:00 UTC midnight.
- Transparent zero-drop failover: automatically retries request on the next available key.
- Live telemetry for status bar, VS Code tree view, and health checks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Coroutine, TypeVar

from google import genai
from google.genai import types, errors

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class GeminiKeySlot:
    """Represents a single registered Gemini API key slot in the fleet."""
    index: int
    key_id: str
    api_key: str
    status: str = "HEALTHY"  # HEALTHY, BURST_COOLDOWN, DAILY_EXHAUSTED
    cooldown_until: float = 0.0
    total_calls: int = 0
    total_tokens: int = 0
    last_used: float = 0.0
    last_error: str | None = None
    _client: genai.Client | None = field(default=None, repr=False)

    @property
    def is_available(self) -> bool:
        now = time.time()
        if self.status != "HEALTHY" and now >= self.cooldown_until:
            # Auto-recover expired cooldown
            self.status = "HEALTHY"
            self.cooldown_until = 0.0
            self.last_error = None
        return self.status == "HEALTHY"

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @property
    def masked_key(self) -> str:
        if not self.api_key:
            return "EMPTY"
        if len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"


class GeminiKeyRotator:
    """
    Manages round-robin rotation and resilience across an array of Gemini API keys.
    """

    DEFAULT_BURST_COOLDOWN = 60.0  # 60s cooldown on 429
    
    def __init__(
        self,
        api_keys: list[str] | None = None,
        env_file_path: Path | str | None = None,
    ):
        self._slots: list[GeminiKeySlot] = []
        self._cursor: int = 0
        self._lock = asyncio.Lock()
        
        # Load keys from argument or environment files
        keys = api_keys or self.discover_keys(env_file_path)
        self.register_keys(keys)

    @classmethod
    def discover_keys(cls, env_file_path: Path | str | None = None) -> list[str]:
        """
        Discovers keys from:
        1. Explicit .env.fleet or .env file
        2. Environment variables: GEMINI_API_KEY_1..N, GEMINI_API_KEYS, GEMINI_API_KEY
        """
        discovered: list[str] = []
        file_env: dict[str, str] = {}

        candidate_paths = []
        if env_file_path:
            candidate_paths.append(Path(env_file_path))
        else:
            repo_root = Path(__file__).resolve().parent.parent.parent
            candidate_paths.extend([
                repo_root / ".env.fleet.gemini",
                repo_root / ".env.fleet",
                repo_root / ".env",
                Path.cwd() / ".env.fleet.gemini",
                Path.cwd() / ".env.fleet",
                Path.cwd() / ".env",
            ])

        for p in candidate_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or "=" not in line:
                                continue
                            k, v = line.split("=", 1)
                            file_env[k.strip()] = v.strip().strip('"').strip("'")
                except Exception as e:
                    logger.debug(f"Error parsing {p}: {e}")

        combined_env = {**file_env, **os.environ}

        # 1. Numbered keys GEMINI_API_KEY_1 .. GEMINI_API_KEY_50
        i = 1
        while True:
            k = f"GEMINI_API_KEY_{i}"
            val = combined_env.get(k, "").strip()
            if not val:
                # Allow a small gap up to 2 missing before terminating
                if i > 2:
                    break
            else:
                if val not in discovered and not val.startswith("REPLACE_"):
                    discovered.append(val)
            i += 1

        # 2. Comma / newline separated GEMINI_API_KEYS
        bulk_keys = combined_env.get("GEMINI_API_KEYS", "").strip()
        if bulk_keys:
            for item in re.split(r"[,\n\r\t]+", bulk_keys):
                item = item.strip()
                if item and item not in discovered and not item.startswith("REPLACE_"):
                    discovered.append(item)

        # 3. Fallback single GEMINI_API_KEY
        single = combined_env.get("GEMINI_API_KEY", "").strip()
        if single and single not in discovered and not single.startswith("REPLACE_"):
            discovered.append(single)

        return discovered

    def register_keys(self, keys: list[str]) -> None:
        """Initializes or resets key slots."""
        self._slots = []
        for idx, k in enumerate(keys, start=1):
            if k and not k.startswith("REPLACE_"):
                self._slots.append(
                    GeminiKeySlot(
                        index=idx,
                        key_id=f"gemini-key-{idx}",
                        api_key=k,
                    )
                )
        self._cursor = 0

    @property
    def total_keys(self) -> int:
        return len(self._slots)

    @property
    def healthy_keys(self) -> int:
        return sum(1 for s in self._slots if s.is_available)

    def mark_burst_cooldown(self, key_id: str, cooldown_seconds: float = DEFAULT_BURST_COOLDOWN, error_msg: str = "") -> None:
        """Marks a key in short-term cooldown following a 429 burst rate limit."""
        for slot in self._slots:
            if slot.key_id == key_id:
                slot.status = "BURST_COOLDOWN"
                slot.cooldown_until = time.time() + cooldown_seconds
                slot.last_error = error_msg or "429 Rate Limit (RPM/TPM)"
                logger.warning(f"[{slot.key_id}] Hit burst 429 cooldown for {cooldown_seconds}s: {slot.last_error}")
                break

    def mark_daily_exhausted(self, key_id: str, error_msg: str = "") -> None:
        """Marks a key exhausted until 00:00 UTC."""
        now = datetime.now(timezone.utc)
        tomorrow_utc = (now + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
        cooldown_secs = max(60.0, (tomorrow_utc - now).total_seconds())
        
        for slot in self._slots:
            if slot.key_id == key_id:
                slot.status = "DAILY_EXHAUSTED"
                slot.cooldown_until = time.time() + cooldown_secs
                slot.last_error = error_msg or "Daily quota exhausted (RPD)"
                logger.warning(f"[{slot.key_id}] Marked daily exhausted until 00:00 UTC ({int(cooldown_secs)}s)")
                break

    async def get_next_slot(self) -> GeminiKeySlot:
        """
        Retrieves the next available healthy key slot using round-robin cursor.
        Raises RuntimeError if no keys are registered.
        If all keys are in cooldown, waits for the slot that recovers earliest.
        """
        if not self._slots:
            raise RuntimeError("No Gemini API keys registered in fleet.")

        async with self._lock:
            n = len(self._slots)
            # 1. Try round-robin search for a healthy slot
            for _ in range(n):
                slot = self._slots[self._cursor]
                self._cursor = (self._cursor + 1) % n
                if slot.is_available:
                    slot.last_used = time.time()
                    return slot

            # 2. All slots currently cooling down; pick earliest recovering
            earliest_slot = min(self._slots, key=lambda s: s.cooldown_until)
            wait_time = max(0.1, earliest_slot.cooldown_until - time.time())
            
        logger.warning(f"[GeminiKeyRotator] All {n} keys in cooldown. Waiting {wait_time:.1f}s for {earliest_slot.key_id}...")
        await asyncio.sleep(min(wait_time, 15.0))
        earliest_slot.is_available  # Trigger status refresh
        earliest_slot.last_used = time.time()
        return earliest_slot

    async def execute_with_retry(
        self,
        call_fn: Callable[[genai.Client, GeminiKeySlot], Coroutine[Any, Any, T]],
        max_attempts: int | None = None,
    ) -> T:
        """
        Executes call_fn using an active key slot.
        If HTTP 429 / RESOURCE_EXHAUSTED occurs, puts the key into burst cooldown
        and immediately retries on the next available key.
        """
        attempts = 0
        total_limit = max_attempts or max(len(self._slots), 3)
        last_exception: Exception | None = None

        while attempts < total_limit:
            attempts += 1
            slot = await self.get_next_slot()

            try:
                result = await call_fn(slot.client, slot)
                slot.total_calls += 1
                return result
            except errors.APIError as api_err:
                last_exception = api_err
                code = getattr(api_err, "code", None)
                msg = str(api_err)
                
                # Check for rate limit or quota exhaustion
                if code == 429 or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                    if "daily" in msg.lower() or "per day" in msg.lower():
                        self.mark_daily_exhausted(slot.key_id, msg)
                    else:
                        self.mark_burst_cooldown(slot.key_id, self.DEFAULT_BURST_COOLDOWN, msg)
                    logger.info(f"Failing over to next Gemini key (attempt {attempts}/{total_limit})...")
                    continue
                else:
                    slot.last_error = f"APIError_{code}: {msg[:100]}"
                    raise
            except Exception as exc:
                last_exception = exc
                slot.last_error = f"{type(exc).__name__}: {str(exc)[:100]}"
                raise

        raise RuntimeError(f"Gemini fleet execution failed after {attempts} attempts. Last error: {last_exception}")

    def get_status(self) -> dict[str, Any]:
        """Provides snapshot telemetry for VS Code status bar and dashboard."""
        healthy_count = sum(1 for s in self._slots if s.is_available)
        total_count = len(self._slots)
        total_calls = sum(s.total_calls for s in self._slots)
        total_tokens = sum(s.total_tokens for s in self._slots)

        slots_detail = []
        for s in self._slots:
            is_avail = s.is_available
            slots_detail.append({
                "key_id": s.key_id,
                "masked": s.masked_key,
                "status": s.status,
                "is_available": is_avail,
                "cooldown_remaining_sec": max(0.0, s.cooldown_until - time.time()) if not is_avail else 0.0,
                "total_calls": s.total_calls,
                "total_tokens": s.total_tokens,
                "last_error": s.last_error,
            })

        return {
            "provider": "google_gemini_fleet",
            "total_keys": total_count,
            "healthy_keys": healthy_count,
            "pooled_rpm_capacity": healthy_count * 15,
            "pooled_rpd_capacity": healthy_count * 1500,
            "total_calls_served": total_calls,
            "total_tokens_served": total_tokens,
            "keys": slots_detail,
        }


# Global shared instance
_global_rotator: GeminiKeyRotator | None = None

def get_gemini_rotator(env_file_path: Path | str | None = None) -> GeminiKeyRotator:
    """Returns the process-wide shared GeminiKeyRotator instance."""
    global _global_rotator
    if _global_rotator is None:
        _global_rotator = GeminiKeyRotator(env_file_path=env_file_path)
    return _global_rotator
