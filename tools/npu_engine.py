#!/usr/bin/env python3
"""
tools/npu_engine.py
-------------------
Intel 1st-Party Tri-Hardware Inference Engine for Meteor Lake (Intel Core Ultra 7 155H).
Supports:
  1. Intel AI Boost NPU (11 TOPS) via OpenVINO GenAI (device='NPU' or 'AUTO:NPU,GPU,CPU') - ~2W, 0% CPU.
  2. Intel Arc Graphics iGPU (8 Xe-Cores) via OpenVINO GPU plugin.
  3. Intel CPU (16 Cores, AVX-VNNI) via OpenVINO CPU plugin or LM Studio GGUF.
  4. Automatic 4-level fallback ladder:
     NPU -> Arc iGPU -> CPU (LM Studio port 1234) -> Deterministic Heuristic (<1ms).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_NPU_PYTHON = REPO_ROOT / ".venv-npu" / "Scripts" / "python.exe"
MODELS_DIR = REPO_ROOT / "models"
DEFAULT_OV_MODEL_DIR = MODELS_DIR / "openvino_qwen_3b"
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"


class TriHardwareEngine:
    def __init__(
        self,
        model_dir: Path | str | None = None,
        preferred_device: str = "AUTO:NPU,GPU,CPU",
    ):
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_OV_MODEL_DIR
        self.preferred_device = preferred_device
        self._pipe = None
        self._device_used: Optional[str] = None

    @staticmethod
    def get_available_devices() -> List[str]:
        """Queries OpenVINO for physical hardware accelerator tiles."""
        # 1. Try directly in current python process
        try:
            import openvino as ov
            core = ov.Core()
            return list(core.available_devices)
        except Exception:
            pass

        # 2. Try via .venv-npu python if present
        if VENV_NPU_PYTHON.exists():
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                res = subprocess.run(
                    [
                        str(VENV_NPU_PYTHON),
                        "-c",
                        "import openvino as ov; core = ov.Core(); import json; print(json.dumps(list(core.available_devices)))",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5.0,
                    creationflags=flags,
                )
                if res.returncode == 0:
                    return json.loads(res.stdout.strip())
            except Exception:
                pass

        return []

    @staticmethod
    def is_lm_studio_online(host: str = "127.0.0.1", port: int = 1234, timeout: float = 0.05) -> bool:
        """Fast socket ping to check LM Studio port 1234."""
        import socket
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (OSError, ConnectionRefusedError):
            return False

    def load(self) -> bool:
        """Attempts to initialize OpenVINO GenAI pipeline."""
        if not self.model_dir.exists():
            return False

        try:
            import openvino_genai as ov_genai
            self._pipe = ov_genai.LLMPipeline(str(self.model_dir), self.preferred_device)
            self._device_used = self.preferred_device
            return True
        except Exception as e:
            logger.debug(f"Could not load OpenVINO GenAI pipeline directly: {e}")
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 220,
    ) -> Dict[str, Any]:
        """
        Executes generation across the tri-hardware hierarchy with graceful recovery:
          Level 1: Native OpenVINO GenAI (NPU / GPU / CPU)
          Level 2: Subprocess .venv-npu OpenVINO
          Level 3: LM Studio (CPU AVX-VNNI port 1234)
          Level 4: Heuristic fallback
        """
        t0 = time.perf_counter()

        # Level 1: In-process OpenVINO
        if self._pipe is not None:
            try:
                formatted = f"<|im_start|>system\n{system_prompt or ''}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
                out = self._pipe.generate(formatted, max_new_tokens=max_tokens)
                elapsed = round((time.perf_counter() - t0) * 1000, 2)
                return {
                    "text": out,
                    "device": self._device_used or "NPU",
                    "latency_ms": elapsed,
                    "tier": "Level 1 (OpenVINO In-Process)",
                }
            except Exception as e:
                logger.warning(f"In-process OpenVINO generation failed: {e}")

        # Level 2: Via .venv-npu if model directory exists
        if VENV_NPU_PYTHON.exists() and self.model_dir.exists():
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                code = (
                    "import openvino_genai as ov, sys, json\n"
                    f"pipe = ov.LLMPipeline(r'{self.model_dir}', '{self.preferred_device}')\n"
                    f"out = pipe.generate('''{prompt}''', max_new_tokens={max_tokens})\n"
                    "print(json.dumps({'text': out}))\n"
                )
                res = subprocess.run(
                    [str(VENV_NPU_PYTHON), "-c", code],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10.0,
                    creationflags=flags,
                )
                if res.returncode == 0:
                    data = json.loads(res.stdout.strip())
                    elapsed = round((time.perf_counter() - t0) * 1000, 2)
                    return {
                        "text": data.get("text", ""),
                        "device": self.preferred_device,
                        "latency_ms": elapsed,
                        "tier": "Level 2 (OpenVINO .venv-npu)",
                    }
            except Exception:
                pass

        # Level 3: LM Studio port 1234 (CPU AVX-VNNI)
        if self.is_lm_studio_online():
            try:
                payload = {
                    "model": "qwen-intent-router",
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": max_tokens,
                }
                req = urllib.request.Request(
                    LM_STUDIO_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body["choices"][0]["message"]["content"]
                    elapsed = round((time.perf_counter() - t0) * 1000, 2)
                    return {
                        "text": text,
                        "device": "CPU_AVX_VNNI",
                        "latency_ms": elapsed,
                        "tier": "Level 3 (LM Studio CPU)",
                    }
            except Exception:
                pass

        # Level 4: Deterministic fallback
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "text": json.dumps({"status": "nominal", "fallback": True}),
            "device": "DETERMINISTIC_HEURISTIC",
            "latency_ms": elapsed,
            "tier": "Level 4 (Deterministic Heuristic)",
        }

    @classmethod
    def get_hardware_status(cls) -> Dict[str, Any]:
        """Reports complete silicon and runtime readiness across CPU, GPU, and NPU."""
        devices = cls.get_available_devices()
        lm_online = cls.is_lm_studio_online()
        venv_ready = VENV_NPU_PYTHON.exists()

        npu_ready = "NPU" in devices
        gpu_ready = "GPU" in devices
        cpu_ready = True

        primary_target = "NPU" if npu_ready else ("GPU" if gpu_ready else "CPU")

        return {
            "platform": "Intel Core Ultra 7 155H (Meteor Lake)",
            "devices_detected": devices,
            "intel_ai_boost_npu": {
                "available": npu_ready,
                "power_profile": "~2W / 0% CPU",
                "capacity": "11 TOPS",
            },
            "intel_arc_gpu": {
                "available": gpu_ready,
                "architecture": "8 Xe-Cores (Xe-LPG)",
            },
            "intel_cpu_avx_vnni": {
                "available": cpu_ready,
                "cores": 16,
                "threads": 22,
            },
            "runtimes": {
                "venv_npu_installed": venv_ready,
                "lm_studio_port_1234": lm_online,
                "active_priority_target": primary_target,
            },
        }


def main():
    status = TriHardwareEngine.get_hardware_status()
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
