"""
Copilot CLI Adapter: Autonomous Subprocess Adapter for GitHub Copilot CLI (copilot.exe).
Executes non-interactive agent workflows in autopilot mode with local sandbox tools,
workspace isolation, and JSON usage metrics telemetry.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from client.adapters.base_adapter import BaseWorkerAdapter
from client.process_runtime import spawn_background


class CopilotCLIAdapter(BaseWorkerAdapter):
    """
    Drives local GitHub Copilot CLI (v1.0+) via headless non-interactive execution:
    `copilot -p "<prompt>" --autopilot --allow-all --no-ask-user --usage-output-file <json>`
    """

    DEFAULT_CAPABILITIES = ["code", "refactor", "unit_test", "research", "draft", "writing"]

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        copilot_path: str | None = None,
        worktree: str | None = None,
        capabilities: list[str] | None = None,
        timeout: float = 180.0,
        max_autopilot_continues: int = 5,
        model: str | None = None,
        auto_tier: str | None = None,
        github_token: str | None = None,
        copilot_home: str | Path | None = None,
        max_ai_credits: int | None = None,
        allow_custom_instructions: bool = False,
        disallow_temp_dir: bool = True,
        headless: bool = False,
        no_auto_update: bool = True,
    ):
        caps = capabilities or self.DEFAULT_CAPABILITIES
        super().__init__(worker_id, nickname, caps)
        self.copilot_path = copilot_path or self._resolve_copilot_binary()
        self.worktree = Path(worktree).resolve() if worktree else None
        self.timeout = timeout
        self.max_autopilot_continues = max_autopilot_continues
        self.model = model
        self.auto_tier = auto_tier
        self.github_token = github_token
        self.copilot_home = Path(copilot_home).resolve() if copilot_home else None
        self.max_ai_credits = max_ai_credits
        self.allow_custom_instructions = allow_custom_instructions
        self.disallow_temp_dir = disallow_temp_dir
        self.headless = headless
        self.no_auto_update = no_auto_update

    @staticmethod
    def _resolve_copilot_binary() -> str:
        """Finds copilot CLI binary on system PATH or standard WinGet installation path."""
        found = shutil.which("copilot")
        if found:
            return found

        # Fallback to standard Windows WinGet install location
        local_app_data = os.getenv("LOCALAPPDATA", "")
        if local_app_data:
            winget_pattern = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if winget_pattern.exists():
                for p in winget_pattern.glob("*GitHub.Copilot*"):
                    candidate = p / "copilot.exe"
                    if candidate.is_file():
                        return str(candidate)

        return "copilot"

    async def check_health(self) -> bool:
        """Health check returns True if copilot executable is present and returns version code 0."""
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            proc = await spawn_background(
                self.copilot_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=flags,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            return proc.returncode == 0 and b"Copilot CLI" in stdout
        except Exception:
            return False

    def build_cli_command(self, prompt: str, usage_file: str | None = None) -> list[str]:
        """Constructs non-interactive CLI argument vector."""
        cmd = [
            self.copilot_path,
            "-p",
            prompt,
            "--autopilot",
            "--allow-all",
            "--no-ask-user",
            "--no-color",
        ]

        if self.no_auto_update:
            cmd.append("--no-auto-update")

        if self.disallow_temp_dir:
            cmd.append("--disallow-temp-dir")

        if self.headless:
            cmd.append("--headless")

        if not self.allow_custom_instructions:
            cmd.append("--no-custom-instructions")

        cmd.extend([
            "--max-autopilot-continues",
            str(self.max_autopilot_continues),
        ])

        if self.max_ai_credits is not None:
            cmd.extend(["--max-ai-credits", str(self.max_ai_credits)])

        if self.auto_tier:
            cmd.extend(["--model", "auto", "--auto-tier", self.auto_tier])
        elif self.model:
            cmd.extend(["--model", self.model])

        if self.worktree:
            cmd.extend(["-C", str(self.worktree)])

        if usage_file:
            cmd.extend(["--usage-output-file", usage_file])

        return cmd

    @staticmethod
    def extract_sqlite_session_telemetry(copilot_home: Path | str | None) -> dict[str, Any]:
        """
        Extracts high-fidelity telemetry directly from SQLite session-store.db
        persisted by copilot.EXE in COPILOT_HOME (assistant_usage_events table).
        """
        if not copilot_home:
            return {}
        home = Path(copilot_home)
        db_path = home / "session-store.db"
        if not db_path.exists():
            return {}

        try:
            import sqlite3
            conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=2.0)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Aggregate across turns for the most recent session
            row = cur.execute(
                """
                SELECT 
                    session_id,
                    model,
                    SUM(input_tokens) AS total_input_tokens,
                    SUM(output_tokens) AS total_output_tokens,
                    SUM(cache_read_tokens) AS total_cache_read_tokens,
                    SUM(cache_write_tokens) AS total_cache_write_tokens,
                    SUM(reasoning_tokens) AS total_reasoning_tokens,
                    SUM(total_nano_aiu) AS total_nano_aiu,
                    SUM(duration_ms) AS total_duration_ms,
                    api_endpoint,
                    reasoning_effort,
                    finish_reason
                FROM assistant_usage_events
                WHERE session_id = (SELECT session_id FROM assistant_usage_events ORDER BY id DESC LIMIT 1)
                GROUP BY session_id
                """
            ).fetchone()
            conn.close()
            if row:
                return dict(row)
        except Exception:
            pass
        return {}

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Executes a task specification non-interactively using copilot CLI autopilot mode.
        Captures exit codes, stdout/stderr, and parses usage JSON statistics.
        """
        directives_header = ""
        if context:
            antigravity_scope = context.get("antigravity_scope")
            if not antigravity_scope and ("chat_context" in context or "antigravity_customizations" in context):
                antigravity_scope = {
                    "chat_context": context.get("chat_context", {}),
                    "antigravity_customizations": context.get("antigravity_customizations", {}),
                }
            if antigravity_scope:
                try:
                    from client.antigravity_bridge import format_prompt_directives
                    directives_header = format_prompt_directives(antigravity_scope) + "\n"
                except Exception as e:
                    directives_header = ""

        prompt = (
            f"{directives_header}"
            f"TASK ID: {task_id}\n"
            f"STAGE: {stage}\n\n"
            f"SPECIFICATION:\n{spec}"
        )
        if context:
            prompt += f"\n\nCONTEXT:\n{json.dumps(context, indent=2)}"

        usage_tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        usage_tmp_path = Path(usage_tmp.name)
        usage_tmp.close()

        cmd = self.build_cli_command(prompt, usage_file=str(usage_tmp_path))

        cwd = str(self.worktree) if self.worktree and self.worktree.exists() else None

        # Build isolated environment for child process
        child_env = os.environ.copy()
        if self.github_token:
            child_env["COPILOT_GITHUB_TOKEN"] = self.github_token
        if self.copilot_home:
            try:
                self.copilot_home.mkdir(parents=True, exist_ok=True)
                (self.copilot_home / "cache").mkdir(parents=True, exist_ok=True)
                (self.copilot_home / "pkg_cache").mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            child_env["COPILOT_HOME"] = str(self.copilot_home)
            child_env["COPILOT_CACHE_HOME"] = str(self.copilot_home / "cache")
            child_env["COPILOT_PKG_CACHE_HOME"] = str(self.copilot_home / "pkg_cache")

        # REA-discovered runtime hardening variables (EXP-REA-001)
        child_env["COPILOT_AUTO_UPDATE"] = "0"
        child_env["COPILOT_ALLOW_ALL"] = "true"
        child_env["COPILOT_FORCE_WINDOWS_HIDE"] = "1"
        child_env["COPILOT_DEBUG_SKIP_LAUNCH_CHECKS"] = "1"

        proc = None
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            proc = await spawn_background(
                *cmd,
                cwd=cwd,
                env=child_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=flags,
                startupinfo=startupinfo,
            )

            start_exec_t = time.perf_counter()

            async def _ticker():
                interval = 15.0
                while True:
                    await asyncio.sleep(interval)
                    elapsed = int(time.perf_counter() - start_exec_t)
                    print(f"[PROGRESS {elapsed}s] Copilot worker active in worktree... (Phase: executing autopilot)", flush=True)

            ticker_task = asyncio.create_task(_ticker())
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout,
                )
            finally:
                ticker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await ticker_task

            stdout_str = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_bytes.decode("utf-8", errors="replace").strip()

            # Parse usage statistics if file generated
            usage_data: dict[str, Any] = {}
            if usage_tmp_path.exists() and usage_tmp_path.stat().st_size > 0:
                try:
                    usage_data = json.loads(usage_tmp_path.read_text(encoding="utf-8"))
                except Exception:
                    usage_data = {}

            # 1. Parse Token Details
            tokens_used = usage_data.get("total_tokens", usage_data.get("tokens", 0))
            if not tokens_used and "tokenDetails" in usage_data:
                td = usage_data.get("tokenDetails", {})
                inp = td.get("input", {}).get("tokenCount", 0)
                outp = td.get("output", {}).get("tokenCount", 0)
                cache = td.get("cache_read", {}).get("tokenCount", 0)
                tokens_used = inp + outp + cache

            # 2. Parse Model
            model_used = (
                usage_data.get("currentModel")
                or usage_data.get("model")
                or self.model
                or "copilot-cli-autopilot"
            )

            # 3. Parse AI Credits (Authentic Nano-AIU or Request Cost or stdout fallback)
            credits_used = 0.0
            if "totalNanoAiu" in usage_data and usage_data["totalNanoAiu"] is not None:
                # Nano AI Units: 1 credit = 1,000,000,000 nanoAiu
                credits_used = round(float(usage_data["totalNanoAiu"]) / 1_000_000_000.0, 2)
            elif "totalPremiumRequestCost" in usage_data and usage_data["totalPremiumRequestCost"] is not None:
                credits_used = float(usage_data["totalPremiumRequestCost"])
            elif any(k in usage_data for k in ["credits_used", "ai_credits_used", "credits", "ai_credits"]):
                raw_credits = (
                    usage_data.get("credits_used")
                    or usage_data.get("ai_credits_used")
                    or usage_data.get("credits")
                    or usage_data.get("ai_credits")
                )
                try:
                    credits_used = round(float(raw_credits), 2)
                except (TypeError, ValueError):
                    credits_used = 0.0
            else:
                # Attempt regex on stdout / stderr (e.g. "AI Credits 0.55 (12s)")
                credit_match = re.search(r"(?:AI Credits|ai-credits|credits)[:\s]+([0-9.]+)", f"{stdout_str} {stderr_str}", re.IGNORECASE)
                if credit_match:
                    try:
                        credits_used = round(float(credit_match.group(1)), 2)
                    except ValueError:
                        credits_used = 1.0 if proc.returncode == 0 else 0.0
                else:
                    credits_used = 1.0 if proc.returncode == 0 else 0.0

            # Ingest authentic SQLite session telemetry if COPILOT_HOME exists (EXP-REA-001)
            session_telemetry = self.extract_sqlite_session_telemetry(self.copilot_home)
            if session_telemetry:
                if not tokens_used:
                    tokens_used = (
                        (session_telemetry.get("total_input_tokens") or 0)
                        + (session_telemetry.get("total_output_tokens") or 0)
                    )
                if ("totalNanoAiu" not in usage_data and "totalPremiumRequestCost" not in usage_data) and session_telemetry.get("total_nano_aiu"):
                    credits_used = round(float(session_telemetry["total_nano_aiu"]) / 1_000_000_000.0, 2)
                if model_used in (None, "copilot-cli-autopilot") and session_telemetry.get("model"):
                    model_used = session_telemetry["model"]

            # Calibrated classification order: check exhaustion first, then anchored 429, strictly on non-zero exit
            quota_exhausted = False
            rate_limited_429 = False
            rate_limit_kind = None

            if proc.returncode != 0:
                combined_tail = f"{stderr_str}\n{stdout_str[-1024:]}".lower()
                # 1. Weekly / monthly quota or credit exhaustion takes precedence
                if "user_weekly_rate_limited" in combined_tail:
                    quota_exhausted = True
                    rate_limit_kind = "user_weekly_rate_limited"
                elif "user_model_rate_limited" in combined_tail:
                    rate_limited_429 = True
                    rate_limit_kind = "user_model_rate_limited"
                elif "user_global_rate_limited" in combined_tail:
                    rate_limited_429 = True
                    rate_limit_kind = "user_global_rate_limited"
                elif "integration_rate_limited" in combined_tail:
                    rate_limited_429 = True
                    rate_limit_kind = "integration_rate_limited"
                elif any(
                    p in combined_tail
                    for p in [
                        "credit limit",
                        "credits exhausted",
                        "quota exceeded",
                        "usage limit",
                        "out of credits",
                        "insufficient credits",
                    ]
                ):
                    quota_exhausted = True
                    rate_limit_kind = "quota_exhausted"
                # 2. Transient HTTP 429 rate-limiting checked second
                elif re.search(r"http[ /]*429|status[: =]*429|too many requests|rate.?limit", combined_tail):
                    rate_limited_429 = True
                    rate_limit_kind = "rate_limited_429"

            if proc.returncode == 0:
                return {
                    "success": True,
                    "summary": f"Completed {stage} via Copilot CLI (autopilot)",
                    "result_text": stdout_str if stdout_str else f"Task {task_id} completed successfully.",
                    "model_used": model_used,
                    "tokens_used": tokens_used,
                    "credits_used": credits_used,
                    "usage_data": usage_data,
                    "quota_exhausted": False,
                    "rate_limited_429": False,
                    "rate_limit_kind": None,
                    "session_telemetry": session_telemetry,
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "summary": f"Copilot CLI exited with code {proc.returncode}",
                    "result_text": stdout_str,
                    "model_used": model_used,
                    "tokens_used": tokens_used,
                    "credits_used": credits_used,
                    "usage_data": usage_data,
                    "quota_exhausted": quota_exhausted,
                    "rate_limited_429": rate_limited_429,
                    "rate_limit_kind": rate_limit_kind,
                    "session_telemetry": session_telemetry,
                    "error": f"CLI_EXIT_{proc.returncode}: {stderr_str[:300] if stderr_str else 'Command failed'}",
                }

        except asyncio.TimeoutError:
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return {
                "success": False,
                "summary": f"Copilot CLI timed out after {self.timeout}s",
                "result_text": "",
                "model_used": self.model or "copilot-cli",
                "tokens_used": 0,
                "credits_used": 0,
                "usage_data": {},
                "quota_exhausted": False,
                "rate_limited_429": False,
                "rate_limit_kind": None,
                "session_telemetry": {},
                "error": f"TIMEOUT: Exceeded {self.timeout}s execution window",
            }
        except Exception as e:
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return {
                "success": False,
                "summary": "Copilot CLI execution encountered an exception",
                "result_text": "",
                "model_used": self.model or "copilot-cli",
                "tokens_used": 0,
                "credits_used": 0,
                "usage_data": {},
                "quota_exhausted": False,
                "rate_limited_429": False,
                "rate_limit_kind": None,
                "session_telemetry": {},
                "error": f"SUBPROCESS_ERROR: {e}",
            }
        finally:
            if usage_tmp_path.exists():
                try:
                    usage_tmp_path.unlink()
                except Exception:
                    pass
