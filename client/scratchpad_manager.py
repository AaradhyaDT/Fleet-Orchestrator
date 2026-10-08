"""
scratchpad_manager.py
---------------------
Thread-safe, durable Markdown Scratchpad Engine for Fleet-Orchestrator jobs.
Coordinates shared persistent state and handoff context across:
  - Stage 1: Claude Desktop Lead (Architectural Decomposition & WBS)
  - Stage 2: Copilot CLI Fleet (High-Volume Worktree Code Execution)
  - Stage 3: Claude Desktop Reviewer (Adversarial QA & Invariant Audit)
  - Stage 4: Orchestrator Host (Verification Gate & Sealing)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCRATCHPADS_DIR = REPO_ROOT / "orchestrator-state" / "scratchpads"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ScratchpadManager:
    """Manages persistent job scratchpads with atomic asynchronous read/write locks."""

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir).resolve() if base_dir else DEFAULT_SCRATCHPADS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_lock(self, job_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if job_id not in self._locks:
                self._locks[job_id] = asyncio.Lock()
            return self._locks[job_id]

    def get_path(self, job_id: str) -> Path:
        """Returns the canonical file path for a job's scratchpad."""
        clean_id = job_id.replace("/", "_").replace("\\", "_").strip()
        return self.base_dir / f"{clean_id}_scratchpad.md"

    async def init_scratchpad(self, job_id: str, title: str, initial_spec: str) -> Path:
        """Initializes a new job scratchpad with standard multi-stage template."""
        path = self.get_path(job_id)
        lock = await self._get_lock(job_id)
        
        content = (
            f"# 📋 Dynamic Execution Scratchpad: {job_id}\n\n"
            f"> **Job ID:** `{job_id}`  \n"
            f"> **Title:** {title}  \n"
            f"> **Created At:** {_now_iso()}  \n"
            f"> **Lifecycle State:** `INITIALIZED`  \n"
            f"> **Architecture Mesh:** Claude Desktop CDP $\\longleftrightarrow$ Copilot CLI 27-Worker Swarm\n\n"
            f"---\n\n"
            f"## 1. Primary Specification & Acceptance Criteria\n\n"
            f"{initial_spec.strip()}\n\n"
            f"---\n\n"
            f"## 2. Architectural Plan & WBS Specs (Claude Desktop Lead)\n"
            f"*(Pending Stage 1 Planning & Decomposition)*\n\n"
            f"---\n\n"
            f"## 3. Worktree Implementations & Test Results (Copilot CLI Swarm)\n"
            f"*(Pending Stage 2 Worktree Code Implementations)*\n\n"
            f"---\n\n"
            f"## 4. Adversarial QA Reviews & Invariant Audits (Claude Desktop Reviewer)\n"
            f"*(Pending Stage 3 Senior QA Review)*\n\n"
            f"---\n\n"
            f"## 5. Gate Certification & Master Conclusion (Orchestrator Host)\n"
            f"*(Pending Stage 4 Final Gate Verification)*\n"
        )

        async with lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        return path

    async def read_scratchpad(self, job_id: str) -> str:
        """Reads current scratchpad markdown text."""
        path = self.get_path(job_id)
        lock = await self._get_lock(job_id)
        async with lock:
            if not path.exists():
                return ""
            return path.read_text(encoding="utf-8")

    async def append_section(
        self,
        job_id: str,
        section_number: int,
        content: str,
        actor: str = "",
    ) -> None:
        """
        Appends or replaces content under a specific numeric section (2, 3, 4, 5).
        Section 2: Plan & WBS Specs
        Section 3: Worktree Implementations
        Section 4: Adversarial QA
        Section 5: Gate Certification
        """
        path = self.get_path(job_id)
        lock = await self._get_lock(job_id)
        
        async with lock:
            if not path.exists():
                await self.init_scratchpad(job_id, f"Job {job_id}", "Implicit specification.")

            current = path.read_text(encoding="utf-8")
            timestamp = _now_iso()
            header_prefix = f"## {section_number}."
            
            entry = f"\n\n### Update by [{actor or 'System'}] at {timestamp}\n\n{content.strip()}\n"

            # Check if section header exists in file
            if header_prefix in current:
                parts = current.split(header_prefix)
                pre = parts[0]
                post = header_prefix + parts[1]
                
                # If section has placeholder "(Pending ...)", remove it
                placeholder = f"*(Pending Stage {section_number - 1}"
                if placeholder in post:
                    first_line, _, rest = post.partition("\n")
                    # Replace until the next '---' or end of block
                    after_placeholder = rest
                    if "---" in rest:
                        pending_part, sep, remainder = rest.partition("---")
                        post = f"{first_line}\n{entry}\n\n---{remainder}"
                    else:
                        post = f"{first_line}\n{entry}\n"
                else:
                    # Append right before next section delimiter '---' or at end
                    if "\n---\n" in post:
                        sec_body, sep, rest = post.partition("\n---\n")
                        post = f"{sec_body}\n{entry}\n---\n{rest}"
                    else:
                        post = f"{post}\n{entry}"
                new_text = pre + post
            else:
                new_text = current + f"\n\n## {section_number}. Appended Stage\n{entry}\n"

            path.write_text(new_text, encoding="utf-8")

    async def get_stage_context(self, job_id: str, stage: str, max_chars: int = 12000) -> str:
        """
        Generates calibrated prompt context from the scratchpad for a specific stage:
        - 'code' stage gets Section 1 (Spec) + Section 2 (WBS Plan).
        - 'qa_review' stage gets Section 1 (Spec) + Section 2 (WBS Plan) + Section 3 (Diffs).
        """
        text = await self.read_scratchpad(job_id)
        if not text:
            return ""

        if len(text) <= max_chars:
            return text

        # Truncate keeping header and tail
        half = max_chars // 2
        return text[:half] + "\n\n... [Scratchpad intermediate context truncated for prompt budget] ...\n\n" + text[-half:]

    async def seal_scratchpad(self, job_id: str, final_status: str = "COMPLETED", summary: str = "") -> Path:
        """Marks scratchpad as concluded and records final verification."""
        path = self.get_path(job_id)
        timestamp = _now_iso()
        lock = await self._get_lock(job_id)
        
        async with lock:
            if not path.exists():
                return path
            text = path.read_text(encoding="utf-8")
            text = text.replace("`INITIALIZED`", f"`{final_status}`").replace("`ACTIVE`", f"`{final_status}`")
            conclusion_block = (
                f"\n\n### Sealed by [Orchestrator Host] at {timestamp}\n"
                f"- **Final Verdict:** `{final_status}`\n"
                f"- **Summary:** {summary or 'Task successfully certified and merged.'}\n"
            )
            if "## 5." in text:
                text = text.replace("*(Pending Stage 4 Final Gate Verification)*", conclusion_block.strip())
            else:
                text += f"\n\n## 5. Gate Certification & Master Conclusion\n{conclusion_block}"
            path.write_text(text, encoding="utf-8")
            return path


# Global singleton instance
scratchpad_mgr = ScratchpadManager()
