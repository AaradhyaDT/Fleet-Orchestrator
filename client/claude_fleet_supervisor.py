"""
claude_fleet_supervisor.py
--------------------------
Supervisor and Multi-Profile CDP Handoff Coordinator for Claude Desktop instances.
Discovers local Claude profiles from profiles.json (CDP ports 9222..9226),
monitors health and rolling cooldowns, integrates with ScratchpadManager,
and executes seamless profile-to-profile handoffs on prompt limits.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from client.adapters.claude_desktop_proxy import ClaudeDesktopProxyAdapter
from client.scratchpad_manager import scratchpad_mgr
from client.qa_verdict import parse_qa_verdict, VERDICT_PASS

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DESKTOP_ROOT = REPO_ROOT.parent / "Claude-Desktop"
PROFILES_FILE = CLAUDE_DESKTOP_ROOT / "profiles.json"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def discover_claude_profiles(profiles_path: Path | None = None) -> List[Dict[str, Any]]:
    """Loads configured Claude Desktop profiles with CDP ports."""
    target = profiles_path or PROFILES_FILE
    if not target.exists():
        # Fallback to local copy if running isolated
        local_target = REPO_ROOT / "orchestrator-state" / "profiles.json"
        if local_target.exists():
            target = local_target
        else:
            return []

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        profiles = []
        for user_key, data in raw.items():
            cdp_port = int(data.get("cdp_port", 0))
            if cdp_port <= 0:
                continue
            profiles.append({
                "profile_id": user_key,
                "worker_id": f"claude-{user_key}",
                "nickname": data.get("nickname", user_key),
                "role": data.get("role", "worker"),
                "preferred_model": data.get("preferred_model", "Sonnet 5"),
                "cdp_port": cdp_port,
                "profile_path": data.get("path", ""),
            })
        return profiles
    except Exception:
        return []


class ClaudeFleetSupervisor:
    """Coordinates active Claude Desktop CDP sessions and handles serial cooldown handoffs."""

    def __init__(self, profiles: List[Dict[str, Any]] | None = None):
        self.profiles = profiles if profiles is not None else discover_claude_profiles()
        self.adapters: Dict[str, ClaudeDesktopProxyAdapter] = {}
        self.cooldowns: Dict[str, datetime] = {}
        self._init_adapters()

    def _init_adapters(self) -> None:
        for p in self.profiles:
            wid = p["worker_id"]
            self.adapters[wid] = ClaudeDesktopProxyAdapter(
                worker_id=wid,
                nickname=p["nickname"],
                profile_path=p["profile_path"],
                model=p["preferred_model"],
                cdp_port=p["cdp_port"],
            )

    async def check_health(self, wid: str) -> bool:
        """Verifies if a specific profile's CDP port is open and responding."""
        adapter = self.adapters.get(wid)
        if not adapter:
            return False
        return await adapter.check_health()

    async def check_all_health(self) -> Dict[str, bool]:
        """Pings all profile CDP endpoints concurrently."""
        results = {}
        for wid, adapter in self.adapters.items():
            results[wid] = await adapter.check_health()
        return results

    def is_in_cooldown(self, wid: str) -> bool:
        """Returns True if worker is in temporary rate-limit cooldown."""
        exp = self.cooldowns.get(wid)
        if not exp:
            return False
        if _now_utc() >= exp:
            del self.cooldowns[wid]
            return False
        return True

    def mark_cooldown(self, wid: str, minutes: int = 60) -> None:
        """Places a profile in cooldown upon limit detection."""
        self.cooldowns[wid] = _now_utc() + timedelta(minutes=minutes)

    def select_best_profile(self, stage: str) -> Optional[ClaudeDesktopProxyAdapter]:
        """
        Selects the best healthy, non-cooldown Claude profile for the given stage:
        - 'plan' / 'architecture' prefers role 'orchestrator' (e.g. user1 / user2).
        - 'qa_review' / 'qa' prefers role 'worker_reviewer' (e.g. user4).
        """
        candidates = []
        for p in self.profiles:
            wid = p["worker_id"]
            if self.is_in_cooldown(wid):
                continue
            adapter = self.adapters.get(wid)
            if not adapter:
                continue
            candidates.append((p, adapter))

        if not candidates:
            return None

        # Filter by stage affinity
        if stage in ("plan", "architecture", "research"):
            for p, adapter in candidates:
                if p["role"] in ("orchestrator", "lead", "architect"):
                    return adapter
        elif stage in ("qa", "qa_review", "audit"):
            for p, adapter in candidates:
                if "review" in p["role"] or "qa" in p["role"]:
                    return adapter

        # Fallback to first available
        return candidates[0][1]

    async def execute_stage_with_handoff(
        self,
        job_id: str,
        stage: str,
        spec: str,
        max_attempts: int = 3,
    ) -> Dict[str, Any]:
        """
        Executes a task stage through Claude Desktop, automatically handling
        cooldown handoffs to secondary profiles using the shared scratchpad.
        """
        attempts = 0
        tried_workers: set[str] = set()

        # Ensure scratchpad has stage context
        scratchpad_text = await scratchpad_mgr.get_stage_context(job_id, stage)
        augmented_spec = (
            f"=== STAGE: {stage.upper()} ===\n"
            f"JOB SPECIFICATION:\n{spec}\n\n"
            f"=== CURRENT SHARED SCRATCHPAD CONTEXT ===\n"
            f"{scratchpad_text}\n\n"
            f"Please execute this stage and adhere strictly to quality contracts.\n"
        )
        if stage in ("qa", "qa_review", "audit"):
            augmented_spec += "\nYou MUST emit an explicit verdict: 'QA_VERDICT: PASS' or 'QA_VERDICT: REVISE <reasons>'."

        while attempts < max_attempts:
            adapter = None
            for p in self.profiles:
                wid = p["worker_id"]
                if wid not in tried_workers and not self.is_in_cooldown(wid):
                    adapter = self.adapters[wid]
                    break

            if not adapter:
                return {
                    "success": False,
                    "error": "All Claude Desktop profiles are exhausted or in cooldown.",
                    "summary": "",
                    "result_text": "",
                }

            wid = adapter.worker_id
            tried_workers.add(wid)
            attempts += 1

            # Check health
            healthy = await adapter.check_health()
            if not healthy:
                continue

            res = await adapter.execute_task(
                task_id=f"{job_id}_{stage}_{attempts}",
                spec=augmented_spec,
                stage=stage,
                context={"job_id": job_id},
            )

            if res.get("success"):
                # Append result to scratchpad under appropriate section
                sec_num = 2 if stage in ("plan", "architecture") else 4
                await scratchpad_mgr.append_section(
                    job_id=job_id,
                    section_number=sec_num,
                    content=res.get("result_text", ""),
                    actor=f"{wid} ({adapter.nickname})",
                )
                return res

            err_text = str(res.get("error", "")).lower()
            if "limit" in err_text or "cooldown" in err_text or "rate" in err_text:
                self.mark_cooldown(wid, minutes=60)

        return {
            "success": False,
            "error": f"Failed after {attempts} profile handoff attempts.",
            "summary": "",
            "result_text": "",
        }
