"""Deterministic verification suite for gh.ps1 and gh.bat GitHub CLI workflow wrappers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GH_BAT = REPO_ROOT / "gh.bat"
GH_PS1 = REPO_ROOT / "gh.ps1"
PWSH_EXE = shutil.which("pwsh") or shutil.which("powershell") or "powershell"


def run_gh_bat(*args: str) -> subprocess.CompletedProcess[str]:
    """Execute gh.bat with the provided arguments and capture UTF-8 output."""
    return subprocess.run(
        [str(GH_BAT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )


def run_gh_ps1(*args: str) -> subprocess.CompletedProcess[str]:
    """Execute gh.ps1 directly via PowerShell (preserving multi-line arguments)."""
    return subprocess.run(
        [PWSH_EXE, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(GH_PS1), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )


def test_gh_wrapper_files_exist() -> None:
    """Verify gh.ps1 and gh.bat exist at repository root."""
    assert GH_PS1.is_file(), "gh.ps1 missing at repository root"
    assert GH_BAT.is_file(), "gh.bat missing at repository root"


def test_gh_wrapper_help_routing() -> None:
    """Verify --gh-help and /? return wrapper documentation cleanly via gh.bat and gh.ps1."""
    for flag in ("--gh-help", "/?"):
        res = run_gh_bat(flag)
        assert res.returncode == 0, f"Help flag {flag} failed: {res.stderr}"
        assert "INV-GH-BODY-FILE" in res.stdout
        assert "issue-create" in res.stdout
        assert "close-verified" in res.stdout

    res_ps1 = run_gh_ps1("--gh-help")
    assert res_ps1.returncode == 0
    assert "INV-GH-BODY-FILE" in res_ps1.stdout


def test_gh_ps1_multiline_body_interception_and_cleanup() -> None:
    """Verify multi-line inline --body with LaTeX math, backticks, and backslashes via gh.ps1."""
    complex_markdown = (
        "## Overview\n"
        "Formula $L(\\theta) = \\sum_{i=1}^n x_i^2$ with `inline_code()` "
        "and Windows path C:\\Users\\test\\file.py\n"
        "- [ ] Task 1\n"
        "- [ ] Task 2"
    )
    res = run_gh_ps1(
        "--DryRunWrapper",
        "issue",
        "create",
        "--title",
        "[Feature] Test Body File Interception",
        "--body",
        complex_markdown,
    )
    assert res.returncode == 0, f"DryRunWrapper failed: {res.stderr}"
    payload = json.loads(res.stdout)
    assert payload["dry_run"] is True
    assert payload["gh_binary"].lower().endswith("gh.exe")

    args = payload["arguments"]
    assert "--body" not in args
    assert "--body-file" in args

    temp_files = payload["temp_files"]
    assert len(temp_files) == 1
    assert temp_files[0]["content"] == complex_markdown

    # Verify finally{} block cleaned up the temporary file after process exit
    temp_path = Path(temp_files[0]["path"])
    assert not temp_path.exists(), f"Temporary body file was not cleaned up: {temp_path}"


def test_gh_bat_singleline_body_and_notes_interception() -> None:
    """Verify gh.bat intercepts inline --body and release --notes without shell corruption."""
    notes_md = "Release notes with $variable, `backticks`, and C:\\Users\\test\\path."
    res = run_gh_bat(
        "--DryRunWrapper",
        "release",
        "create",
        "v1.2.0",
        "--notes",
        notes_md,
    )
    assert res.returncode == 0, f"DryRunWrapper failed: {res.stderr}"
    payload = json.loads(res.stdout)
    assert "--notes" not in payload["arguments"]
    assert "--notes-file" in payload["arguments"]
    assert payload["temp_files"][0]["content"] == notes_md


def test_gh_bat_escaped_newline_expansion_preserves_latex_and_paths() -> None:
    """Verify single-line \\n sequences expand via gh.bat while preserving LaTeX \\neq and C:\\new."""
    inline_md = r"## Overview\nFormula $a \neq b$ at C:\new\path\n\n## Tasks\n- [ ] Task 1"
    res = run_gh_bat(
        "--DryRunWrapper",
        "issue",
        "edit",
        "234",
        "--body",
        inline_md,
    )
    assert res.returncode == 0, f"DryRunWrapper failed: {res.stderr}"
    payload = json.loads(res.stdout)
    expected = "## Overview\nFormula $a \\neq b$ at C:\\new\\path\n\n## Tasks\n- [ ] Task 1"
    assert payload["temp_files"][0]["content"] == expected


def test_gh_issue_create_shortcut_dry_run() -> None:
    """Verify issue-create shortcut constructs expected arguments and native type metadata."""
    body_md = "## Tasks\n- [ ] Task 1\n- [ ] Task 2"
    res = run_gh_ps1(
        "--DryRunWrapper",
        "issue-create",
        "--title",
        "[Feature] Add gh.ps1 Wrapper",
        "--assignee",
        "AaradhyaDT",
        "--label",
        "enhancement",
        "--type",
        "Feature",
        "--milestone",
        "M1",
        "--body",
        body_md,
    )
    assert res.returncode == 0, f"issue-create dry-run failed: {res.stderr}"
    payload = json.loads(res.stdout)
    assert payload["shortcut"] == "issue-create"
    assert payload["issue_type"] == "Feature"
    create_args = payload["create_args"]
    assert create_args[:4] == ["issue", "create", "--title", "[Feature] Add gh.ps1 Wrapper"]
    assert "--assignee" in create_args
    assert "--milestone" in create_args
    assert "--body-file" in create_args
    assert payload["temp_files"][0]["content"] == body_md


def test_gh_sub_issue_shortcut_dry_run() -> None:
    """Verify sub-issue shortcut parses parent/child issue numbers and repository."""
    res = run_gh_bat(
        "--DryRunWrapper",
        "sub-issue",
        "--parent",
        "#28",
        "--child",
        "#29",
        "--repo",
        "Aaradhya-Dev-Tamrakar/Fleet-Orchestrator",
    )
    assert res.returncode == 0, f"sub-issue dry-run failed: {res.stderr}"
    payload = json.loads(res.stdout)
    assert payload["shortcut"] == "sub-issue"
    assert payload["repository"] == "Aaradhya-Dev-Tamrakar/Fleet-Orchestrator"
    assert payload["parent_num"] == 28
    assert payload["child_num"] == 29


def test_gh_close_verified_shortcut_dry_run() -> None:
    """Verify close-verified shortcut attaches commit SHA and uses --body-file."""
    res = run_gh_bat(
        "--DryRunWrapper",
        "close-verified",
        "#42",
        "--sha",
        "a1b2c3d",
        "--comment",
        "Verified 100% pytest pass.",
    )
    assert res.returncode == 0, f"close-verified dry-run failed: {res.stderr}"
    payload = json.loads(res.stdout)
    assert payload["shortcut"] == "close-verified"
    assert payload["issue_number"] == 42
    assert payload["commit_sha"] == "a1b2c3d"
    assert "Completed in commit a1b2c3d. Verified 100% pytest pass." == payload["comment_body"]
    assert "--body-file" in payload["comment_args"]
    assert payload["close_args"][:3] == ["issue", "close", "42"]
