"""Unit tests for probe_environment tool."""

import json
from pathlib import Path

from tools.probe_environment import capture_environment_snapshot, probe_host_telemetry

ROOT = Path(__file__).resolve().parent.parent


def test_probe_host_telemetry():
    """Asserts that host telemetry captures CPU and RAM numbers within plausible hardware limits."""
    telem = probe_host_telemetry()
    assert "cpu_count" in telem
    assert telem["cpu_count"] >= 1
    assert "total_ram_mb" in telem
    assert telem["total_ram_mb"] > 0
    assert "free_ram_mb" in telem
    assert telem["free_ram_mb"] > 0
    assert "safe_worker_slots" in telem
    assert 0 <= telem["safe_worker_slots"] <= 27


def test_capture_environment_snapshot():
    """Asserts that environment snapshot structure adheres to expected contract."""
    snap = capture_environment_snapshot()
    assert "timestamp_epoch" in snap
    assert "timestamp_iso" in snap
    assert "host_telemetry" in snap
    assert "lm_studio" in snap
    assert "fleet_pools" in snap
    assert "cli_binaries" in snap
    assert "skills_registry" in snap
    assert snap["skills_registry"]["present"] is True
    assert snap["skills_registry"]["distinct_skills"] >= 90
