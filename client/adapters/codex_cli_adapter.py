"""Headless subprocess adapter for the OpenAI Codex CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from client.adapters.base_adapter import BaseWorkerAdapter
from client.process_runtime import spawn_background, communicate_background
from client.cli_accounts import reported_retry_after

logger = logging.getLogger(__name__)


class CodexCLIAdapter(BaseWorkerAdapter):
    """Run one task through ``codex exec --json`` in a workspace-write sandbox."""

    DEFAULT_CAPABILITIES = [
        "orchestrator",
        "code",
        "refactor",
        "unit_test",
        "qa_review",
        "writing",
        "formatting",
    ]

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        codex_path: str | Path | None = None,
        codex_home: str | Path | None = None,
        workspace_dir: str | Path | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        timeout: float = 600.0,
        sandbox: str = "workspace-write",
        approval_policy: str = "never",
        capabilities: list[str] | None = None,
        process_env: dict[str, str] | None = None,
    ):
        super().__init__(worker_id, nickname, capabilities or self.DEFAULT_CAPABILITIES)
        self.codex_path = str(codex_path or self._resolve_codex_binary())
        self.codex_home = Path(codex_home).expanduser().resolve() if codex_home else None
        self.workspace_dir = Path(workspace_dir).expanduser().resolve() if workspace_dir else None
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.timeout = timeout
        self.sandbox = sandbox
        self.approval_policy = approval_policy
        self.process_env = process_env

    @staticmethod
    def _resolve_codex_binary() -> str:
        """Resolve Codex from an explicit environment override or PATH."""
        env_binary = os.getenv("CODEX_CLI_BINARY")
        if env_binary:
            return env_binary
        return shutil.which("codex.exe") or shutil.which("codex") or "codex"

    async def check_health(self) -> bool:
        """Return whether the CLI is installed and responds to its version probe."""
        try:
            proc = await spawn_background(
                self.codex_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._prepare_environment(),
                stdin=asyncio.subprocess.DEVNULL,
            )
            await communicate_background(proc, timeout=10.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("[%s] Codex CLI health check failed: %s", self.worker_id, exc)
            return False

    def _prepare_environment(self) -> dict[str, str]:
        env = self.process_env.copy() if self.process_env is not None else os.environ.copy()
        if self.codex_home:
            self.codex_home.mkdir(parents=True, exist_ok=True)
            env["CODEX_HOME"] = str(self.codex_home)
        return env

    def build_cli_command(self, prompt: str) -> list[str]:
        """Build an unattended Codex command with bounded workspace permissions."""
        cmd = [
            self.codex_path,
            "--ask-for-approval",
            self.approval_policy,
            "exec",
            "--json",
            "--sandbox",
            self.sandbox,
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.process_env is not None:
            cmd.extend(["--config", 'cli_auth_credentials_store="file"'])
            cmd.extend(["--config", 'forced_login_method="chatgpt"'])
        if self.reasoning_effort:
            cmd.extend(["--config", f'model_reasoning_effort="{self.reasoning_effort}"'])
        cmd.append(prompt)
        return cmd

    @staticmethod
    def _parse_jsonl_output(stdout_text: str) -> tuple[str, str | None]:
        """Extract the final assistant message and a structured failure, if any."""
        messages: list[str] = []
        failure: str | None = None
        for line in stdout_text.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_type = event.get("type")
            if event_type in {"turn.failed", "error"}:
                failure = str(event.get("message") or event.get("error") or event)
            item = event.get("item") or {}
            if not isinstance(item, dict):
                continue
            if event_type == "item.completed" and item.get("type") in {"agent_message", "assistant_message"}:
                message = item.get("text") or item.get("content")
                if isinstance(message, str) and message:
                    messages.append(message)
        return "\n".join(messages) if messages else stdout_text.strip(), failure

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = (
            f"You are executing as autonomous agent [{self.nickname}] in stage: {stage}.\n"
            f"TASK SPECIFICATION:\n{spec}\n\n"
            "Complete the task in the current workspace and report the changes and any verification performed."
        )
        cwd = self.workspace_dir or Path.cwd()
        cmd = self.build_cli_command(prompt)
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await spawn_background(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=self._prepare_environment(),
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout_bytes, stderr_bytes = await communicate_background(proc, timeout=self.timeout)
            stdout_text = stdout_bytes.decode("utf-8", errors="replace")
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")
            result_text, structured_error = self._parse_jsonl_output(stdout_text)
            retry_after = reported_retry_after(stdout_text)

            if proc.returncode != 0 or structured_error:
                error = structured_error or stderr_text.strip() or f"Codex CLI exited with code {proc.returncode}"
                return {
                    "success": False,
                    "retry_after_seconds": retry_after,
                    "error": f"Codex CLI execution failed: {error[:500]}",
                    "summary": "",
                    "result_text": result_text,
                    "task_id": task_id,
                    "execution_started": proc is not None,
                }
            return {
                "success": True,
                "summary": f"Completed {stage} via Codex CLI ({self.nickname})",
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
                "error": f"Codex CLI worker timed out after {self.timeout}s",
                "summary": "",
                "result_text": "",
                "task_id": task_id,
                "execution_started": proc is not None,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Codex CLI execution error: {exc}",
                "summary": "",
                "result_text": "",
                "task_id": task_id,
                "execution_started": proc is not None,
            }
