"""Headless subprocess adapter for the OpenCode CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from client.adapters.base_adapter import BaseWorkerAdapter
from client.process_runtime import spawn_background, communicate_background
from client.cli_accounts import reported_retry_after

logger = logging.getLogger(__name__)


class OpenCodeCLIAdapter(BaseWorkerAdapter):
    """Run one task through ``opencode run --format json`` in its worktree."""

    DEFAULT_CAPABILITIES = [
        "code",
        "refactor",
        "unit_test",
        "qa_review",
        "research",
        "writing",
        "formatting",
    ]

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        opencode_path: str | Path | None = None,
        workspace_dir: str | Path | None = None,
        model: str | None = None,
        variant: str | None = None,
        timeout: float = 600.0,
        auto_approve: bool = True,
        capabilities: list[str] | None = None,
        process_env: dict[str, str] | None = None,
    ):
        super().__init__(worker_id, nickname, capabilities or self.DEFAULT_CAPABILITIES)
        self.opencode_path = str(opencode_path or self._resolve_opencode_binary())
        self.workspace_dir = Path(workspace_dir).expanduser().resolve() if workspace_dir else None
        self.model = model
        self.variant = variant
        self.timeout = timeout
        self.auto_approve = auto_approve
        self.process_env = process_env

    @staticmethod
    def _resolve_opencode_binary() -> str:
        """Resolve an explicit override or the OpenCode executable on PATH."""
        if os.getenv("OPENCODE_CLI_BINARY"):
            return os.environ["OPENCODE_CLI_BINARY"]
        if sys.platform == "win32":
            native = Path(os.getenv("APPDATA", "")) / "npm" / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
            if native.is_file():
                return str(native)
        return (
            os.getenv("OPENCODE_CLI_BINARY") or shutil.which("opencode.exe") or shutil.which("opencode") or "opencode"
        )

    async def check_health(self) -> bool:
        """Return whether the OpenCode executable responds to its version probe."""
        try:
            proc = await spawn_background(
                self.opencode_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.process_env,
                stdin=asyncio.subprocess.DEVNULL,
            )
            await communicate_background(proc, timeout=10.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("[%s] OpenCode CLI health check failed: %s", self.worker_id, exc)
            return False

    def build_cli_command(self, prompt: str) -> list[str]:
        """Build the non-interactive OpenCode command for a configured worktree."""
        if self.workspace_dir is None:
            raise ValueError("OpenCode worker requires Workspace or Worktree configuration")

        cmd = [
            self.opencode_path,
            "run",
            "--format",
            "json",
            "--dir",
            str(self.workspace_dir),
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.variant:
            cmd.extend(["--variant", self.variant])
        if self.auto_approve:
            cmd.append("--auto")
        cmd.append(prompt)
        return cmd

    @staticmethod
    def _parse_jsonl_output(stdout_text: str) -> tuple[str, str | None]:
        """Extract OpenCode text events and identify malformed or failed streams."""
        messages: list[str] = []
        valid_events = 0
        malformed_lines = 0
        failure: str | None = None

        for line in stdout_text.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                malformed_lines += 1
                continue
            if not isinstance(event, dict):
                malformed_lines += 1
                continue
            valid_events += 1
            event_type = event.get("type")
            part = event.get("part")
            if event_type == "text" and isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text:
                    messages.append(text)
            if event_type == "error":
                failure = str(event.get("message") or event.get("error") or event)

        if messages:
            return "".join(messages), failure
        if valid_events == 0 and malformed_lines:
            return "", "OpenCode CLI returned malformed JSON event output"
        if failure:
            return "", failure
        if valid_events:
            return "", "OpenCode CLI returned no assistant text in its JSON events"
        return "", None

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        proc: asyncio.subprocess.Process | None = None
        if self.workspace_dir is None:
            return {
                "success": False,
                "error": "OpenCode worker requires Workspace or Worktree configuration",
                "summary": "",
                "result_text": "",
                "task_id": task_id,
                "execution_started": proc is not None,
            }
        if not self.workspace_dir.is_dir():
            return {
                "success": False,
                "error": f"OpenCode worktree does not exist or is not a directory: {self.workspace_dir}",
                "summary": "",
                "result_text": "",
                "task_id": task_id,
                "execution_started": proc is not None,
            }

        prompt = (
            f"You are executing as autonomous agent [{self.nickname}] in stage: {stage}.\n"
            f"TASK ID: {task_id}\nTASK SPECIFICATION:\n{spec}"
        )
        if context:
            prompt += f"\n\nCONTEXT:\n{json.dumps(context, indent=2, default=str)}"

        cmd = self.build_cli_command(prompt)
        try:
            proc = await spawn_background(
                *cmd,
                cwd=str(self.workspace_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.process_env,
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout_bytes, stderr_bytes = await communicate_background(proc, timeout=self.timeout)
            stdout_text = stdout_bytes.decode("utf-8", errors="replace")
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")
            result_text, structured_error = self._parse_jsonl_output(stdout_text)
            retry_after = reported_retry_after(stdout_text)

            if proc.returncode != 0 or structured_error:
                detail = stderr_text.strip() or structured_error or f"exit code {proc.returncode}"
                return {
                    "success": False,
                    "retry_after_seconds": retry_after,
                    "error": f"OpenCode CLI execution failed: {detail[:500]}",
                    "summary": "",
                    "result_text": result_text,
                    "task_id": task_id,
                    "execution_started": proc is not None,
                }
            if not result_text:
                detail = stderr_text.strip() or "OpenCode CLI returned no JSON events"
                return {
                    "success": False,
                    "retry_after_seconds": retry_after,
                    "error": f"OpenCode CLI execution failed: {detail[:500]}",
                    "summary": "",
                    "result_text": "",
                    "task_id": task_id,
                    "execution_started": proc is not None,
                }
            return {
                "success": True,
                "summary": f"Completed {stage} via OpenCode CLI ({self.nickname})",
                "result_text": result_text,
                "error": None,
                "task_id": task_id,
                "execution_started": proc is not None,
            }
        except asyncio.TimeoutError:
            if proc and proc.returncode is None:
                proc.kill()
                await proc.wait()
            return {
                "success": False,
                "error": f"OpenCode CLI worker timed out after {self.timeout}s",
                "summary": "",
                "result_text": "",
                "task_id": task_id,
                "execution_started": proc is not None,
            }
        except Exception as exc:
            if proc and proc.returncode is None:
                proc.kill()
                await proc.wait()
            return {
                "success": False,
                "error": f"OpenCode CLI execution error: {exc}",
                "summary": "",
                "result_text": "",
                "task_id": task_id,
                "execution_started": proc is not None,
            }
