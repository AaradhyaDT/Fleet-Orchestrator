from __future__ import annotations

import pytest
from pathlib import Path

from tools.ci_secret_scanner import scan_text
from tools.ci_self_healing_runner import parse_pytest_failures
from tools.fleet_watchdog import (
    audit_database_schema,
    audit_worktree_hygiene,
    audit_template_integrity,
    audit_task_branches,
    audit_fleet_live_status,
    audit_capability_gaps,
    audit_routing_accuracy,
)


def test_secret_scanner_clean():
    clean_code = """
    def add(a: int, b: int) -> int:
        return a + b
    
    API_URL = "https://api.example.com/v1"
    """
    findings = scan_text(clean_code, "test_file.py")
    assert len(findings) == 0


def test_secret_scanner_detects_secrets():
    aws_sample = "AKIA" + "IOSFODNN7EXAMPLE"
    ghp_sample = "ghp_" + "123456789012345678901234567890123456"
    leak_sample = f"""
    aws_key = "{aws_sample}"
    pat = "{ghp_sample}"
    """
    findings = scan_text(leak_sample, "leak_sample.py")
    assert len(findings) >= 2
    patterns = [f["pattern"] for f in findings]
    assert any("AWS" in p for p in patterns)
    assert any("GitHub" in p for p in patterns)


def test_parse_pytest_failures():
    sample_pytest_output = """
=================================== FAILURES ===================================
__________________________________ test_fail_1 _________________________________
assert 1 == 2
=========================== short test summary info ===========================
FAILED tests/test_alpha.py::test_fail_1 - AssertionError: assert 1 == 2
FAILED tests/test_beta.py::test_fail_2 - ValueError: invalid input
========================= 2 failed, 10 passed in 1.23s =========================
    """
    failed = parse_pytest_failures(sample_pytest_output)
    assert len(failed) == 2
    assert "tests/test_alpha.py::test_fail_1" in failed
    assert "tests/test_beta.py::test_fail_2" in failed


@pytest.mark.asyncio
async def test_fleet_watchdog_components():
    root = Path(__file__).resolve().parent.parent
    db_ok = await audit_database_schema()
    assert db_ok is True

    wt_ok = audit_worktree_hygiene(root)
    assert wt_ok is True

    tpl_ok = audit_template_integrity(root)
    assert tpl_ok is True

    tb_ok = audit_task_branches(root, fix=False)
    assert tb_ok is True

    fl_ok = audit_fleet_live_status(root, fix=False)
    assert fl_ok is True

    cg_ok = audit_capability_gaps(root, fix=False)
    assert cg_ok is True

    ra_ok = audit_routing_accuracy(root)
    assert ra_ok is True


def test_fleet_watchdog_orphaned_worktree_cleanup(tmp_path: Path):
    import subprocess
    # Initialize dummy git repo
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    (repo_dir / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

    # Create dummy orphaned worktree folder
    wt_dir = repo_dir / ".worktrees" / "task_1799999999_dummy"
    wt_dir.mkdir(parents=True)
    (wt_dir / "dirty.txt").write_text("abandoned", encoding="utf-8")

    assert wt_dir.exists()
    ok = audit_worktree_hygiene(repo_dir, fix=True)
    assert ok is True
    # The orphaned folder must be pruned
    assert not wt_dir.exists()


def test_fleet_watchdog_live_status_stale_recovery(tmp_path: Path):
    import json
    live_status_dir = tmp_path / "orchestrator-state" / "live-status"
    live_status_dir.mkdir(parents=True)

    status_file = live_status_dir / "copilot-w1.json"
    status_file.write_text(
        json.dumps({
            "account": "copilot-w1",
            "status": "busy",
            "heartbeat_at": "2026-01-01T00:00:00Z",
            "current_task_id": "task_stale_001",
            "cooldown_until": "2026-01-01T01:00:00Z",
            "note": "Old stale session",
        }),
        encoding="utf-8",
    )

    ok = audit_fleet_live_status(tmp_path, fix=True, stale_hours=1.0)
    assert ok is True

    updated = json.loads(status_file.read_text(encoding="utf-8"))
    assert updated["status"] == "idle"
    assert updated["current_task_id"] is None
    assert updated["cooldown_until"] is None
    assert "Auto-recovered" in updated["note"]
