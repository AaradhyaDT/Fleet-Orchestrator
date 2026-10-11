"""Unit tests for tools.capability_gap_detector and Sentinel #6 integration."""

import json
from pathlib import Path

import pytest
from tools.capability_gap_detector import (
    Severity,
    create_issue_for_gap,
    detect_dead_adapters,
    detect_routing_misses,
    detect_stale_skills,
    detect_untested_adapters,
    generate_gap_report,
)
from tools.fleet_watchdog import audit_capability_gaps


def test_detect_dead_adapters_syntax_error(tmp_path: Path):
    adapters_dir = tmp_path / "client" / "adapters"
    adapters_dir.mkdir(parents=True)
    broken_adapter = adapters_dir / "broken_adapter.py"
    broken_adapter.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")

    gaps = detect_dead_adapters(tmp_path)
    assert len(gaps) == 1
    assert gaps[0].category == "dead_adapter"
    assert gaps[0].severity == Severity.CRITICAL
    assert "broken_adapter.py" in gaps[0].summary


def test_detect_untested_adapters(tmp_path: Path):
    adapters_dir = tmp_path / "client" / "adapters"
    adapters_dir.mkdir(parents=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    untested = adapters_dir / "new_model_adapter.py"
    untested.write_text("class NewModelAdapter: pass\n", encoding="utf-8")

    gaps = detect_untested_adapters(tmp_path)
    assert len(gaps) == 1
    assert gaps[0].category == "untested_adapter"
    assert gaps[0].severity == Severity.HIGH
    assert gaps[0].auto_fixable is True
    assert gaps[0].details["expected_test"] == "test_new_model_adapter.py"


def test_detect_untested_adapters_finds_none_when_tested(tmp_path: Path):
    adapters_dir = tmp_path / "client" / "adapters"
    adapters_dir.mkdir(parents=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    adapter = adapters_dir / "verified_adapter.py"
    adapter.write_text("class VerifiedAdapter: pass\n", encoding="utf-8")
    test_file = tests_dir / "test_verified_adapter.py"
    test_file.write_text("from client.adapters.verified_adapter import VerifiedAdapter\n", encoding="utf-8")

    gaps = detect_untested_adapters(tmp_path)
    assert len(gaps) == 0


def test_detect_routing_misses(tmp_path: Path):
    bench_dir = tmp_path / "orchestrator-state" / "bench"
    bench_dir.mkdir(parents=True)
    report_file = bench_dir / "decision_report_test.json"
    report_file.write_text(
        json.dumps({
            "prompt": "Test complex locked prompt",
            "decision": {
                "policy": "STRICT_INTERLOCK",
                "matrix_cell": "(V2, R2)",
            },
        }),
        encoding="utf-8",
    )

    gaps = detect_routing_misses(tmp_path, days=1)
    assert len(gaps) == 1
    assert gaps[0].category == "routing_miss"
    assert gaps[0].severity == Severity.MEDIUM
    assert gaps[0].details["cell"] == "(V2, R2)"


def test_detect_stale_skills(tmp_path: Path):
    skills_dir = tmp_path / ".agents" / "skills"
    good_skill = skills_dir / "good-skill"
    good_skill.mkdir(parents=True)
    (good_skill / "SKILL.md").write_text("# Good Skill\n", encoding="utf-8")

    stale_skill = skills_dir / "stale-skill"
    stale_skill.mkdir(parents=True)
    # Missing SKILL.md

    gaps = detect_stale_skills(tmp_path)
    assert len(gaps) == 1
    assert gaps[0].category == "stale_skill"
    assert gaps[0].details["skill_dir"] == "stale-skill"


def test_generate_gap_report_structure(tmp_path: Path):
    report = generate_gap_report(tmp_path, write_output=True)
    assert "generated_at" in report
    assert "total_gaps" in report
    assert "critical" in report
    assert "high" in report
    assert isinstance(report["gaps"], list)

    out_file = tmp_path / "orchestrator-state" / "gap_report.json"
    assert out_file.exists()


def test_create_issue_for_gap_dry_run(tmp_path: Path):
    gap = {
        "category": "untested_adapter",
        "severity": "HIGH",
        "summary": "Adapter 'custom_adapter.py' lacks test coverage",
        "details": {
            "adapter": "custom_adapter.py",
            "expected_test": "test_custom_adapter.py",
        },
        "auto_fixable": True,
    }

    url = create_issue_for_gap(gap, tmp_path, dry_run=True)
    assert url == "https://github.com/dry-run/issue"

    # Low severity should not create issues
    low_gap = dict(gap, severity="LOW")
    assert create_issue_for_gap(low_gap, tmp_path, dry_run=True) is None


def test_watchdog_audit_capability_gaps():
    root = Path(__file__).resolve().parent.parent
    ok = audit_capability_gaps(root, fix=False)
    assert ok is True
