"""Unit tests for Azmuth Daemon in Fleet-Orchestrator."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.azmuth_daemon import (
    execute_cycle,
    sense_capability_gaps,
    reconcile_mirrors_and_registry,
    run_verification_suite,
    synthesize_gap_solution_with_gemini,
    self_heal_code,
    is_paused,
    set_paused,
    get_windows_idle_seconds,
    is_system_idle,
    execute_idle_burst,
    is_working_tree_pure_state,
    execute_guarded_state_sync,
)


def test_sense_capability_gaps_clean():
    with patch("tools.azmuth_daemon.run_command") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"total_gaps": 0, "gaps": []}),
        )
        data = sense_capability_gaps()
        assert data["total_gaps"] == 0
        assert data["gaps"] == []


def test_reconcile_mirrors_and_registry():
    with patch("tools.azmuth_daemon.run_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        success = reconcile_mirrors_and_registry()
        assert success is True


def test_run_verification_suite_smoke():
    with patch("tools.azmuth_daemon.run_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="test pass", stderr="")
        passed, out = run_verification_suite()
        assert passed is True


def test_synthesize_gap_solution_with_gemini_mocked():
    gap = {
        "category": "untested_adapter",
        "summary": "Adapter 'dummy_adapter.py' lacks test coverage",
        "details": {},
    }
    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key_for_test"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.text = json.dumps({
                "target_file": "tests/test_dummy_adapter.py",
                "code_content": "def test_dummy(): pass",
                "description": "Dummy test",
            })
            mock_client.models.generate_content.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            res = synthesize_gap_solution_with_gemini(gap)
            assert res is not None
            assert res["target_file"] == "tests/test_dummy_adapter.py"
            assert "def test_dummy" in res["code_content"]


def test_self_healing_patch_mocked():
    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key_for_test"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.text = json.dumps({
                "target_file": "tests/test_dummy_adapter.py",
                "code_content": "def test_dummy_healed(): assert True",
                "fix_explanation": "Added assertion",
            })
            mock_client.models.generate_content.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            healed = self_heal_code("tests/test_dummy_adapter.py", "def test_dummy(): fail", "AssertionError")
            assert healed is not None
            assert "test_dummy_healed" in healed


def test_pause_resume_lifecycle(tmp_path: Path):
    with patch("tools.azmuth_daemon.STATE_DIR", tmp_path), \
         patch("tools.azmuth_daemon.PAUSE_FILE", tmp_path / "azmuth.pause"):
        set_paused(True, "testing pause")
        assert is_paused() is True

        # When paused, execute_cycle skips work
        report = execute_cycle()
        assert report["status"] == "PAUSED"

        set_paused(False)
        assert is_paused() is False


def test_idle_burst_stealing():
    with patch("tools.azmuth_daemon.has_sufficient_ram", return_value=True), \
         patch("tools.azmuth_daemon.check_and_update_skills_dirty", return_value=True), \
         patch("tools.azmuth_daemon.reconcile_mirrors_and_registry", return_value=True), \
         patch("tools.azmuth_daemon.is_system_idle", return_value=True), \
         patch("tools.azmuth_daemon.sense_capability_gaps", return_value={"total_gaps": 0}), \
         patch("tools.azmuth_corpus_harvester.harvest_single_task", return_value={"status": "ALL_SYNCHRONIZED"}):
        res = execute_idle_burst()
        assert res["aborted_due_to_activity"] is False
        assert "skills_registry_refresh" in res["tasks_executed"]


def test_idle_burst_clean_skips_refresh():
    with patch("tools.azmuth_daemon.has_sufficient_ram", return_value=True), \
         patch("tools.azmuth_daemon.check_and_update_skills_dirty", return_value=False), \
         patch("tools.azmuth_daemon.is_system_idle", return_value=True), \
         patch("tools.azmuth_corpus_harvester.harvest_single_task", return_value={"status": "ALL_SYNCHRONIZED"}):
        res = execute_idle_burst()
        assert res["aborted_due_to_activity"] is False
        assert "skills_registry_refresh" not in res["tasks_executed"]



def test_execute_cycle_all_healthy():
    with patch("tools.azmuth_daemon.is_paused", return_value=False), \
         patch("tools.azmuth_daemon.has_sufficient_ram", return_value=True), \
         patch("tools.azmuth_daemon.reconcile_mirrors_and_registry", return_value=True), \
         patch("tools.azmuth_daemon.sense_capability_gaps", return_value={"total_gaps": 0, "gaps": []}), \
         patch("tools.azmuth_daemon.run_verification_suite", return_value=(True, "")):

        report = execute_cycle(dry_run=True, use_ai=False)
        assert report["status"] == "ALL_HEALTHY_ZERO_TOKENS"
        assert report["gaps_detected"] == 0
        assert report["smoke_suite_passed"] is True


def test_is_working_tree_pure_state_true():
    mock_porcelain = (
        " M orchestrator-state/azmuth_run.json\n"
        " M orchestrator-state/github_sensor_cache.json\n"
        " M tools/skills_registry.json\n"
    )
    with patch("tools.azmuth_daemon.run_command") as mock_cmd:
        mock_cmd.return_value = MagicMock(returncode=0, stdout=mock_porcelain)
        is_pure, dirty_files = is_working_tree_pure_state()
        assert is_pure is True
        assert len(dirty_files) == 3


def test_is_working_tree_pure_state_false_on_code_edit():
    mock_porcelain = (
        " M orchestrator-state/azmuth_run.json\n"
        " M tools/azmuth_daemon.py\n"
    )
    with patch("tools.azmuth_daemon.run_command") as mock_cmd:
        mock_cmd.return_value = MagicMock(returncode=0, stdout=mock_porcelain)
        is_pure, dirty_files = is_working_tree_pure_state()
        assert is_pure is False
        assert "tools/azmuth_daemon.py" in dirty_files


def test_execute_guarded_state_sync_locked():
    with patch("pathlib.Path.exists", return_value=True):
        res = execute_guarded_state_sync(force=True)
        assert res["status"] == "SKIPPED_GIT_LOCKED"


def test_execute_guarded_state_sync_dirty_tree():
    with patch("tools.azmuth_daemon.is_working_tree_pure_state", return_value=(False, ["tools/azmuth_daemon.py"])), \
         patch("pathlib.Path.exists", return_value=False):
        res = execute_guarded_state_sync(force=True)
        assert res["status"] == "SKIPPED_DIRTY_TREE"


def test_execute_guarded_state_sync_success():
    with patch("tools.azmuth_daemon.is_working_tree_pure_state", return_value=(True, ["orchestrator-state/azmuth_run.json"])), \
         patch("pathlib.Path.exists", return_value=False), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("tools.azmuth_daemon.run_command") as mock_cmd, \
         patch("tools.azmuth_daemon.record_ingestion_event"):
        mock_cmd.return_value = MagicMock(returncode=0, stdout="Workspace synced successfully.")
        res = execute_guarded_state_sync(force=True)
        assert res["status"] == "SUCCESS"
        assert res["files_synced"] == 1

