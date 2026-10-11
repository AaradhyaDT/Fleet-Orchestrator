"""Unit tests for tools/retrain_pipeline.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from tools.retrain_pipeline import (
    AccuracyReport,
    RetrainDecision,
    PipelineResult,
    evaluate_routing_accuracy,
    check_dataset_staleness,
    make_retrain_decision,
    harvest_fresh_trajectories,
    rebuild_unified_dataset,
    sync_dataset_to_drive,
    trigger_colab_training,
    post_training_verify,
    run_pipeline,
)


def test_accuracy_report_dataclass():
    report = AccuracyReport(
        total=25,
        archetype_correct=20,
        cell_correct=22,
        skill_correct=19,
        fast_path_correct=24,
        composite_accuracy=86.5,
        decider="deterministic",
    )
    assert report.total == 25
    assert report.composite_accuracy == 86.5
    assert report.decider == "deterministic"


def test_evaluate_routing_accuracy_golden():
    fixture = Path(__file__).resolve().parent / "fixtures" / "adaptive_golden_scenarios.yaml"
    assert fixture.exists(), "adaptive_golden_scenarios.yaml fixture must exist"

    report = evaluate_routing_accuracy(fixture, decider="deterministic")
    assert report.total >= 20
    assert report.composite_accuracy >= 80.0
    assert report.latency_ms > 0
    assert len(report.per_scenario) == report.total


def test_evaluate_routing_accuracy_missing_fixture(tmp_path: Path):
    missing_fixture = tmp_path / "nonexistent.yaml"
    report = evaluate_routing_accuracy(missing_fixture)
    assert report.total == 0
    assert report.composite_accuracy == 0.0


def test_check_dataset_staleness_summary(tmp_path: Path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    summary_file = dataset_dir / "dataset_summary.json"

    # 5 days ago
    five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
    summary_file.write_text(
        json.dumps({"generated_at": five_days_ago.isoformat()}),
        encoding="utf-8",
    )

    age = check_dataset_staleness(dataset_dir)
    assert 4.9 <= age <= 5.1


def test_check_dataset_staleness_mtime_fallback(tmp_path: Path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    train_file = dataset_dir / "unified_fleet_train.jsonl"
    train_file.write_text('{"sample": 1}\n', encoding="utf-8")

    age = check_dataset_staleness(dataset_dir)
    # Created just now -> age < 0.1 days
    assert 0.0 <= age <= 0.1


def test_check_dataset_staleness_missing(tmp_path: Path):
    empty_dir = tmp_path / "empty_dataset"
    empty_dir.mkdir()
    age = check_dataset_staleness(empty_dir)
    assert age == float("inf")


def test_make_retrain_decision_healthy():
    decision = make_retrain_decision(
        accuracy=92.0,
        staleness_days=10.0,
        min_accuracy=85.0,
        max_staleness_days=21,
    )
    assert decision.should_retrain is False
    assert "healthy" in decision.reason
    assert decision.accuracy == 92.0


def test_make_retrain_decision_accuracy_drift():
    decision = make_retrain_decision(
        accuracy=81.0,
        staleness_days=10.0,
        min_accuracy=85.0,
        max_staleness_days=21,
    )
    assert decision.should_retrain is True
    assert "accuracy" in decision.reason.lower()
    assert decision.phase_a_details["trigger"] == "accuracy_drift"


def test_make_retrain_decision_dataset_stale():
    decision = make_retrain_decision(
        accuracy=90.0,
        staleness_days=25.0,
        min_accuracy=85.0,
        max_staleness_days=21,
    )
    assert decision.should_retrain is True
    assert "staleness" in decision.reason.lower()
    assert decision.phase_a_details["trigger"] == "staleness"


def test_make_retrain_decision_force():
    decision = make_retrain_decision(
        accuracy=95.0,
        staleness_days=2.0,
        min_accuracy=85.0,
        max_staleness_days=21,
        force=True,
    )
    assert decision.should_retrain is True
    assert "force" in decision.reason.lower()
    assert decision.phase_a_details["trigger"] == "force"


def test_harvest_fresh_trajectories_dry_run():
    count = harvest_fresh_trajectories(dry_run=True)
    assert count == 0


def test_rebuild_unified_dataset_dry_run():
    train_c, eval_c = rebuild_unified_dataset(dry_run=True)
    assert train_c == 0
    assert eval_c == 0


def test_sync_dataset_to_drive_dry_run():
    ok = sync_dataset_to_drive(dry_run=True)
    assert ok is True


def test_trigger_colab_training_dry_run():
    triggered, method = trigger_colab_training(retrain_brain=False, dry_run=True)
    assert triggered is False
    assert method == "dry_run"


def test_trigger_colab_training_manual_instructions():
    with patch("shutil.which", return_value=None), \
         patch("pathlib.Path.exists", return_value=False):
        triggered, method = trigger_colab_training(retrain_brain=False, dry_run=False)
        assert triggered is False
        assert method == "manual_instructions"


def test_post_training_verify():
    fixture = Path(__file__).resolve().parent / "fixtures" / "adaptive_golden_scenarios.yaml"
    score = post_training_verify(fixture)
    assert score is not None
    assert score >= 80.0


def test_run_pipeline_clean_no_retrain():
    # Force high accuracy and low staleness
    with patch("tools.retrain_pipeline.check_dataset_staleness", return_value=5.0), \
         patch("tools.retrain_pipeline.evaluate_routing_accuracy", return_value=AccuracyReport(composite_accuracy=95.0, total=25)):
        result = run_pipeline(
            min_accuracy=85.0,
            max_staleness_days=21,
            force_retrain=False,
            dry_run=True,
            output_format="json",
        )
        assert result.decision.should_retrain is False
        assert result.harvest_count == 0


def test_run_pipeline_dry_run_retrain_triggered():
    # Force low accuracy
    with patch("tools.retrain_pipeline.check_dataset_staleness", return_value=5.0), \
         patch("tools.retrain_pipeline.evaluate_routing_accuracy", return_value=AccuracyReport(composite_accuracy=78.0, total=25)):
        result = run_pipeline(
            min_accuracy=85.0,
            max_staleness_days=21,
            force_retrain=False,
            dry_run=True,
            output_format="json",
        )
        assert result.decision.should_retrain is True
        assert result.dry_run is True
        assert result.colab_method == "dry_run"


def test_pipeline_result_serialization():
    decision = RetrainDecision(
        should_retrain=True,
        reason="Test reason",
        accuracy=80.0,
        staleness_days=10.0,
        threshold_accuracy=85.0,
        threshold_staleness=21,
    )
    result = PipelineResult(
        decision=decision,
        harvest_count=50,
        dataset_train_size=100,
        dataset_eval_size=20,
        drive_sync_ok=True,
        colab_triggered=False,
        colab_method="manual_instructions",
        timestamp="2026-10-11T12:00:00Z",
    )
    d = result.to_dict()
    assert d["decision"]["should_retrain"] is True
    assert d["harvest_count"] == 50
    json_str = json.dumps(d)
    assert "Test reason" in json_str
