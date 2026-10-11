"""Unit tests for Sentinel #7: audit_routing_accuracy."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tools.fleet_watchdog import audit_routing_accuracy
from tools.retrain_pipeline import AccuracyReport


def test_sentinel_routing_accuracy_passes():
    root = Path(__file__).resolve().parent.parent
    # Standard repository golden scenarios should evaluate cleanly above 80%
    ok = audit_routing_accuracy(root, min_accuracy=80.0)
    assert ok is True


def test_sentinel_routing_accuracy_fails_below_threshold(tmp_path: Path):
    root = Path(__file__).resolve().parent.parent
    mock_report = AccuracyReport(
        total=25,
        composite_accuracy=72.0,
    )
    with patch("tools.retrain_pipeline.evaluate_routing_accuracy", return_value=mock_report):
        ok = audit_routing_accuracy(root, min_accuracy=85.0)
        assert ok is False


def test_sentinel_routing_accuracy_missing_fixture(tmp_path: Path):
    # tmp_path has no tests/fixtures/adaptive_golden_scenarios.yaml
    ok = audit_routing_accuracy(tmp_path, min_accuracy=85.0)
    assert ok is False


def test_sentinel_routing_accuracy_handles_exception():
    root = Path(__file__).resolve().parent.parent
    with patch("tools.retrain_pipeline.evaluate_routing_accuracy", side_effect=RuntimeError("Parsing crash")):
        ok = audit_routing_accuracy(root, min_accuracy=85.0)
        assert ok is False
