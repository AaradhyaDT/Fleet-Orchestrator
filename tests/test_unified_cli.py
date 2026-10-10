from __future__ import annotations

import argparse
from unittest.mock import patch
import pytest

from tools.unified_fleet_cli import get_full_status_dict, cmd_submit


def test_unified_cli_get_full_status_dict():
    data = get_full_status_dict()
    assert "timestamp" in data
    assert "gemini_fleet" in data
    assert "copilot_fleet" in data
    assert "tasks" in data
    assert "counts" in data["tasks"]
    assert "recent" in data["tasks"]


def test_unified_cli_cmd_submit(tmp_path):
    args = argparse.Namespace(
        state_dir=str(tmp_path),
        spec="Test specification for unit test",
        kind="code",
        no_antigravity=True,
        conversation_id=None,
    )
    cmd_submit(args)
    
    tasks_dir = tmp_path / "tasks"
    assert tasks_dir.exists()
    task_files = list(tasks_dir.glob("*.json"))
    assert len(task_files) == 1
    assert "task_" in task_files[0].name
