"""Unit tests for adaptive_engine CLI controller."""

import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.adaptive_engine import format_cli_output
from tools.adaptive_decision_harness import AdaptiveDecisionEngine


def test_format_cli_output_fast_path():
    decision = AdaptiveDecisionEngine.decide("run pytest")
    output = format_cli_output(decision)
    assert "[TIER 0 FAST PATH DETECTED]" in output
    assert "Shell Cmd" in output


def test_format_cli_output_regular():
    decision = AdaptiveDecisionEngine.decide("Design FIR filter for STM32 DSP", files=["dsp.c"])
    output = format_cli_output(decision)
    assert "ADAPTIVE WORKFLOW ORCHESTRATION DECISION" in output
    assert "HARDWARE & RESOURCE ENVELOPE" in output
    assert "Available RAM" in output
    assert "Safe Concurrency" in output


def test_cli_execution_via_subprocess():
    res = subprocess.run([
        sys.executable,
        str(ROOT / "tools" / "adaptive_engine.py"),
        "lint codebase with ruff",
        "--json",
    ], capture_output=True, text=True, cwd=str(ROOT))
    assert res.returncode == 0
    assert '"is_fast_path": true' in res.stdout
