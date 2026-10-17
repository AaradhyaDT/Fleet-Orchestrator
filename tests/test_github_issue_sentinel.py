#!/usr/bin/env python3
"""
tests/test_github_issue_sentinel.py
Unit tests for Autonomous GitHub Issue Sentinel.
"""

from pathlib import Path
import pytest
import tempfile

from tools.github_issue_sentinel import (
    derive_branch_slug,
    GitHubIssueSentinel,
)


def test_derive_branch_slug():
    # Feature
    s1 = derive_branch_slug(42, "Support Z3 SMT Prover in Fleet", [{"name": "enhancement"}])
    assert s1 == "feat/support-z3-smt-prover-in-#42"

    # Bug / Fix
    s2 = derive_branch_slug(101, "Fix memory leak in buffer allocator", [{"name": "bug"}])
    assert s2 == "fix/fix-memory-leak-in-buffer-#101"

    # Refactor
    s3 = derive_branch_slug(77, "Refactor task scheduling loop", [{"name": "refactor"}])
    assert s3 == "refactor/refactor-task-scheduling-loop-#77"

    # Docs
    s4 = derive_branch_slug(12, "Update Azmuth Gene RFC", [{"name": "documentation"}])
    assert s4 == "docs/update-azmuth-gene-rfc-#12"


def test_sentinel_dry_run():
    with tempfile.TemporaryDirectory() as tmp_dir:
        sentinel = GitHubIssueSentinel(state_dir=Path(tmp_dir), dry_run=True)
        issue = {
            "number": 88,
            "title": "Implement Continuous DAG Queue",
            "body": "Add topological scheduler for multi-stage pipelines",
            "labels": [{"name": "enhancement"}],
        }
        res = sentinel.process_issue(issue)
        assert res["issue_number"] == 88
        assert res["dry_run"] is True
        assert res["status"] == "dry_run_passed"
        assert "feat/implement-continuous-dag-queue-#88" == res["branch_name"]
        assert "routing" in res
        assert "archetype" in res["routing"]


def test_sentinel_ledger_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        st_dir = Path(tmp_dir)
        sentinel = GitHubIssueSentinel(state_dir=st_dir, dry_run=False)
        issue = {
            "number": 99,
            "title": "Verify offline language harvest",
            "body": "Ensure 30 language reference cards pass schema validation",
            "labels": [{"name": "test"}],
        }
        res = sentinel.process_issue(issue, skip_tests=True)
        assert res["issue_number"] == 99
        assert res["status"] == "completed"

        ledger_file = st_dir / "sentinel_ledger.json"
        assert ledger_file.exists()

        import json
        data = json.loads(ledger_file.read_text(encoding="utf-8"))
        assert "99" in data["processed_issues"]
        assert data["processed_issues"]["99"]["title"] == "Verify offline language harvest"
