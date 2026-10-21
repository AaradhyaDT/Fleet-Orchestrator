"""tests/test_azmuth_startup_preflight.py
---------------------------------------
Unit and integration tests for Azmuth startup preflight, power awareness,
cold boot grace period, stale lock hygiene, and air-gapped network detection.
"""

from __future__ import annotations

import ctypes
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.azmuth_daemon import (
    GEARS,
    check_and_enforce_gear_safety,
    get_current_gear,
    get_system_power_status,
    get_system_uptime_seconds,
    is_network_available,
    purge_stale_git_locks,
    run_boot_preflight_hygiene,
    set_current_gear,
)


def test_get_system_power_status_structure():
    """Verify system power status returns standard telemetry structure."""
    status = get_system_power_status()
    assert isinstance(status, dict)
    assert "ac_line_status" in status
    assert "on_battery" in status
    assert "battery_pct" in status
    assert "battery_saver" in status
    assert isinstance(status["on_battery"], bool)


def test_get_system_uptime_seconds():
    """Verify system uptime returns a positive float."""
    uptime = get_system_uptime_seconds()
    assert isinstance(uptime, float)
    assert uptime >= 0.0


def test_network_availability_probe():
    """Verify network probe returns a boolean without hanging."""
    res = is_network_available(timeout=0.2)
    assert isinstance(res, bool)


def test_battery_power_gate_auto_downshift(tmp_path: Path):
    """Verify that being on battery power triggers auto-downshift to whisper gear."""
    # Mock power status to simulate running on battery at 42%
    mock_power = {
        "ac_line_status": 0,
        "on_battery": True,
        "battery_pct": 42,
        "battery_saver": False,
    }

    set_current_gear("turbo", reason="test initial setting")
    assert get_current_gear() == "turbo"

    with patch("tools.azmuth_daemon.get_system_power_status", return_value=mock_power):
        gear_name, gear_cfg = check_and_enforce_gear_safety()
        assert gear_name == "whisper"
        assert gear_cfg == GEARS["whisper"]
        assert get_current_gear() == "whisper"


def test_purge_stale_git_locks_when_none_exists(tmp_path: Path):
    """Verify purge_stale_git_locks returns False when no lock exists."""
    with patch("tools.azmuth_daemon.ROOT", tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        assert purge_stale_git_locks() is False


def test_purge_stale_git_locks_when_stale(tmp_path: Path):
    """Verify purge_stale_git_locks safely unlinks .git/index.lock if no git.exe process is active."""
    with patch("tools.azmuth_daemon.ROOT", tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        lock_file = git_dir / "index.lock"
        lock_file.write_text("dummy lock content", encoding="utf-8")
        assert lock_file.exists()

        # Mock subprocess to simulate NO git.exe running
        fake_tasklist = MagicMock(return_value=MagicMock(stdout="INFO: No tasks running with specified criteria."))
        with patch("subprocess.run", fake_tasklist):
            cleared = purge_stale_git_locks()
            assert cleared is True
            assert not lock_file.exists()


def test_run_boot_preflight_hygiene():
    """Verify the comprehensive Phase 0 preflight execution returns valid payload."""
    report = run_boot_preflight_hygiene()
    assert isinstance(report, dict)
    assert "timestamp" in report
    assert "uptime_sec" in report
    assert "is_cold_boot_warmup" in report
    assert "stale_git_lock_cleared" in report
    assert "power_status" in report
    assert "network_online" in report
