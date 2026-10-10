"""
Antigravity (AGY) CLI Adapter: Headless Subprocess Adapter for agy.exe.
Drives the Google Antigravity CLI in non-interactive print mode with
isolated worker sandboxes, permission auto-approval, and JSON telemetry parsing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from client.adapters.base_adapter import BaseWorkerAdapter

logger = logging.getLogger(__name__)


class AGYCLIAdapter(BaseWorkerAdapter):
    """
    Drives local Antigravity CLI (agy.exe) via non-interactive headless execution:
    `agy -p "<prompt>" --dangerously-skip-permissions --output-format json --model <model> --effort <effort>`
    """

    DEFAULT_CAPABILITIES = [
        "orchestrator",
        "code",
        "refactor",
        "unit_test",
        "research",
        "qa_review",
        "writing",
        "formatting",
    ]

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        agy_path: str | Path | None = None,
        worker_home: str | Path | None = None,
        model: str = "gemini-3.8-flash",
        effort: str = "high",
        timeout: float = 300.0,
        dangerously_skip_permissions: bool = True,
        capabilities: list[str] | None = None,
        workspace_dir: str | Path | None = None,
    ):
        caps = capabilities or self.DEFAULT_CAPABILITIES
        super().__init__(worker_id, nickname, caps)
        self.agy_path = str(agy_path or self._resolve_agy_binary())
        self.worker_home = Path(worker_home).resolve() if worker_home else None
        self.model = model
        self.effort = effort
        self.timeout = timeout
        self.dangerously_skip_permissions = dangerously_skip_permissions
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else None

    @staticmethod
    def _resolve_agy_binary() -> str:
        """Finds agy executable in standard install paths or PATH."""
        env_binary = os.getenv("AGY_CLI_BINARY")
        if env_binary and Path(env_binary).exists():
            return env_binary

        # Common Windows local app data path
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            candidate = Path(local_app_data) / "agy" / "bin" / "agy.exe"
            if candidate.exists():
                return str(candidate)

        which_agy = shutil.which("agy.exe") or shutil.which("agy")
        if which_agy:
            return which_agy

        return "agy.exe"

    async def check_health(self) -> bool:
        """Checks if agy binary exists and runs --help or version check."""
        try:
            cmd = [self.agy_path, "--help"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            return proc.returncode == 0 or b"Usage of agy" in stdout
        except Exception as e:
            logger.debug(f"[{self.worker_id}] AGY health check failed: {e}")
            return False

    def _prepare_environment(self) -> dict[str, str]:
        """Prepares isolated environment variables for this worker process."""
        env = os.environ.copy()
        if self.worker_home:
            self.worker_home.mkdir(parents=True, exist_ok=True)
            # Isolate home and app data directories
            env["ANTIGRAVITY_APP_DATA"] = str(self.worker_home)
            env["USERPROFILE"] = str(self.worker_home)
            env["HOME"] = str(self.worker_home)
        return env

    def _build_command(self, prompt: str) -> list[str]:
        """Constructs the agy CLI execution command."""
        cmd = [self.agy_path, "-p", prompt]

        if self.dangerously_skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        if self.model:
            cmd.extend(["--model", self.model])

        if self.effort:
            cmd.extend(["--effort", self.effort])

        cmd.extend(["--output-format", "json"])

        if self.workspace_dir and self.workspace_dir.exists():
            cmd.extend(["--add-dir", str(self.workspace_dir)])

        return cmd

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Executes work specified in `spec` via agy CLI non-interactively.
        Returns standard deliverable dictionary.
        """
        prompt = (
            f"You are executing as autonomous agent [{self.nickname}] in stage: {stage}.\n"
            f"TASK SPECIFICATION:\n{spec}\n\n"
            f"Fulfill the task completely, validating correctness before returning."
        )

        cmd = self._build_command(prompt)
        env = self._prepare_environment()
        cwd = str(self.workspace_dir) if self.workspace_dir else str(Path.cwd())

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout,
            )

            stdout_text = stdout_bytes.decode("utf-8", errors="replace")
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": f"agy.exe exited with code {proc.returncode}: {stderr_text[:500]}",
                    "summary": "",
                    "result_text": stdout_text,
                    "task_id": task_id,
                }

            # Attempt JSON parsing of output
            parsed_result = stdout_text
            try:
                data = json.loads(stdout_text)
                if isinstance(data, dict):
                    parsed_result = data.get("content") or data.get("response") or stdout_text
            except Exception:
                pass

            return {
                "success": True,
                "summary": f"Completed {stage} via AGY ({self.nickname})",
                "result_text": parsed_result,
                "error": None,
                "task_id": task_id,
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"AGY worker timed out after {self.timeout}s",
                "summary": "",
                "result_text": "",
                "task_id": task_id,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"AGY execution error: {str(e)}",
                "summary": "",
                "result_text": "",
                "task_id": task_id,
            }
