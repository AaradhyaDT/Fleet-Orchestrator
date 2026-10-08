from __future__ import annotations

import pytest
from pathlib import Path

from tools.ci_secret_scanner import scan_text
from tools.ci_self_healing_runner import parse_pytest_failures
from tools.fleet_watchdog import (
    audit_database_schema,
    audit_worktree_hygiene,
    audit_template_integrity,
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
