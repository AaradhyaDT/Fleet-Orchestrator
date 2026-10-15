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
        mock_run.return_value = MagicMock(returncode=0)
        assert run_verification_suite() is True


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


def test_execute_cycle_all_healthy():
    with patch("tools.azmuth_daemon.reconcile_mirrors_and_registry", return_value=True), \
         patch("tools.azmuth_daemon.sense_capability_gaps", return_value={"total_gaps": 0, "gaps": []}), \
         patch("tools.azmuth_daemon.run_verification_suite", return_value=True):

        report = execute_cycle(dry_run=True, use_ai=False)
        assert report["status"] == "ALL_HEALTHY_ZERO_TOKENS"
        assert report["gaps_detected"] == 0
        assert report["smoke_suite_passed"] is True
