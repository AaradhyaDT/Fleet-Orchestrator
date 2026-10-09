from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from client.adapters.base_adapter import BaseWorkerAdapter


class ColabCloudAdapter(BaseWorkerAdapter):
    """
    Adapter for Google Colab Cloud GPU/TPU execution.
    Executes tasks remotely on Google Colab runtimes via the Colab CLI wrapper.
    Guarantees automated resource teardown to prevent compute unit leakage.
    """

    def __init__(
        self,
        worker_id: str = "colab-w1",
        nickname: str = "colab-cloud",
        default_gpu: str = "T4",
        cli_command: str = "colab"
    ):
        super().__init__(
            worker_id=worker_id,
            nickname=nickname,
            capabilities=["cloud_gpu", "colab", "cuda", "tpu", "fine_tuning", "python"]
        )
        self.default_gpu = default_gpu
        self.cli_command = cli_command

    def _resolve_cli(self) -> list[str]:
        """Resolves the Colab CLI executable or python shim."""
        # Check if colab or colab.cmd is available in PATH
        colab_path = shutil.which(self.cli_command)
        if colab_path:
            return [colab_path]
        
        # Fallback to local repo wrapper tools/colab_cli_win.py
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        win_shim = os.path.join(repo_root, "tools", "colab_cli_win.py")
        if os.path.exists(win_shim):
            return [sys.executable, win_shim]
            
        return [self.cli_command]

    async def check_health(self) -> bool:
        """
        Verifies if the Colab CLI is installed, runnable, and authenticated.
        Returns True if `colab whoami` or token inspection succeeds.
        """
        # Fast path: check if OAuth2 token file exists
        token_path = os.path.expanduser("~/.config/colab-cli/token.json")
        if os.path.exists(token_path):
            try:
                with open(token_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("access_token") or data.get("refresh_token"):
                        return True
            except Exception:
                pass

        # Verification via whoami command
        cli_prefix = self._resolve_cli()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cli_prefix, "whoami",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=8.0)
            return proc.returncode == 0 and b"Email:" in stdout
        except Exception:
            return False

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Executes code on a remote Google Colab VM.
        Supports direct code execution or local script files.
        Enforces automated VM lifecycle teardown.
        """
        cli_prefix = self._resolve_cli()
        gpu_tier = context.get("gpu", self.default_gpu)
        tpu_tier = context.get("tpu")
        script_path = context.get("script_path")
        code = context.get("code")
        install_pkgs = context.get("install_pkgs", [])
        timeout_s = context.get("timeout_s", 300.0)

        # Build execution arguments
        session_name = f"fleet-{task_id[:8]}"
        created_session = False

        # If a standalone script is provided without dependencies, prefer `colab run`
        if script_path and os.path.exists(script_path) and not install_pkgs:
            cmd = list(cli_prefix) + ["run"]
            if gpu_tier:
                cmd.extend(["--gpu", gpu_tier])
            elif tpu_tier:
                cmd.extend(["--tpu", tpu_tier])
            cmd.extend([script_path])

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
                success = (proc.returncode == 0)
                return {
                    "summary": f"Executed {script_path} via Colab run (GPU: {gpu_tier or 'CPU'})",
                    "result_text": stdout.decode("utf-8", errors="replace"),
                    "success": success,
                    "error": None if success else stderr.decode("utf-8", errors="replace")
                }
            except Exception as e:
                return {
                    "summary": f"Failed running script {script_path}",
                    "result_text": "",
                    "success": False,
                    "error": str(e)
                }

        # Multi-step session flow with guaranteed cleanup
        try:
            # 1. Provision VM
            new_cmd = list(cli_prefix) + ["new", "-s", session_name]
            if gpu_tier:
                new_cmd.extend(["--gpu", gpu_tier])
            elif tpu_tier:
                new_cmd.extend(["--tpu", tpu_tier])

            new_proc = await asyncio.create_subprocess_exec(
                *new_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(new_proc.communicate(), timeout=45.0)
            if new_proc.returncode != 0:
                return {
                    "summary": "Failed to provision Colab VM session",
                    "result_text": "",
                    "success": False,
                    "error": f"colab new exited with code {new_proc.returncode}"
                }
            created_session = True

            # 2. Optional Package Installation
            if install_pkgs:
                inst_cmd = list(cli_prefix) + ["install", "-s", session_name] + install_pkgs
                inst_proc = await asyncio.create_subprocess_exec(
                    *inst_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(inst_proc.communicate(), timeout=120.0)

            # 3. Execution
            if script_path and os.path.exists(script_path):
                exec_cmd = list(cli_prefix) + ["exec", "-s", session_name, "-f", script_path]
                exec_proc = await asyncio.create_subprocess_exec(
                    *exec_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(exec_proc.communicate(), timeout=timeout_s)
            elif code:
                exec_cmd = list(cli_prefix) + ["exec", "-s", session_name]
                exec_proc = await asyncio.create_subprocess_exec(
                    *exec_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    exec_proc.communicate(input=code.encode("utf-8")),
                    timeout=timeout_s
                )
            else:
                stdout = b"[colab] VM provisioned successfully (no code payload)."
                stderr = b""

            success = (exec_proc.returncode == 0) if (script_path or code) else True
            return {
                "summary": f"Executed task on Colab VM {session_name} (GPU: {gpu_tier or 'CPU'})",
                "result_text": stdout.decode("utf-8", errors="replace"),
                "success": success,
                "error": None if success else stderr.decode("utf-8", errors="replace")
            }

        except Exception as e:
            return {
                "summary": f"Error executing task {task_id} on Colab",
                "result_text": "",
                "success": False,
                "error": str(e)
            }
        finally:
            # Enforce resource safety: always stop session
            if created_session:
                stop_cmd = list(cli_prefix) + ["stop", "-s", session_name]
                try:
                    stop_proc = await asyncio.create_subprocess_exec(
                        *stop_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await asyncio.wait_for(stop_proc.communicate(), timeout=20.0)
                except Exception:
                    pass
