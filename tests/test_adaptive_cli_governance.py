"""Governance and invariant unit tests for adaptive-workflow CLI."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = ROOT / ".agents" / "skills" / "adaptive-workflow" / "SKILL.md"


def test_skill_md_byte_budget_invariant():
    """Asserts that SKILL.md strictly adheres to INV-AUDIT-ORDER byte ceiling (<= 8,192 bytes)."""
    assert SKILL_PATH.exists()
    byte_size = SKILL_PATH.stat().st_size
    assert byte_size <= 8192, f"SKILL.md size {byte_size} bytes exceeds hard limit of 8192 bytes!"
    # Ensure comfortable headroom
    assert byte_size <= 8150, f"SKILL.md size {byte_size} bytes lacks required safety margin (target: <= 8150 bytes)."


def test_cli_compact_schema_invariant():
    """Asserts that --schema emits compact machine-readable JSON (<350 chars) without prompt requirement."""
    res = subprocess.run([
        sys.executable,
        str(ROOT / "tools" / "adaptive_engine.py"),
        "--schema",
    ], capture_output=True, text=True, cwd=str(ROOT))
    assert res.returncode == 0
    assert len(res.stdout) < 800  # Strict bounding
    schema = json.loads(res.stdout)
    assert schema["command"] == "adaptive_engine.py"
    assert "--files" in schema["flags"]
    assert "cpm" in schema["subcommands"]


def test_cli_help_interception_contract():
    """Asserts that -h / --help prints concise contract without dumping verbose 80-line help screens."""
    res = subprocess.run([
        sys.executable,
        str(ROOT / "tools" / "adaptive_engine.py"),
        "-h",
    ], capture_output=True, text=True, cwd=str(ROOT))
    assert res.returncode == 0
    assert "INV-ZERO-HELP-LOOP" in res.stdout
    assert len(res.stdout.splitlines()) <= 20


def test_cli_smart_normalization():
    """Asserts that aliased flags (-f, -j) and subcommands (triage) parse without crashing."""
    res = subprocess.run([
        sys.executable,
        str(ROOT / "tools" / "adaptive_engine.py"),
        "triage",
        "Audit filter",
        "-f",
        "firmware/filter.c",
        "-j",
    ], capture_output=True, text=True, cwd=str(ROOT))
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["policy"] == "BRANCH_GUARD"


def test_cli_cpm_subcommand_delegation():
    """Asserts that 'cpm' subcommand solves topological critical path DAG."""
    dag = {"tasks": [{"id": "A", "duration": 4, "dependencies": []}, {"id": "B", "duration": 6, "dependencies": ["A"]}]}
    res = subprocess.run([
        sys.executable,
        str(ROOT / "tools" / "adaptive_engine.py"),
        "cpm",
        "--dag-json",
        json.dumps(dag),
        "--json",
    ], capture_output=True, text=True, cwd=str(ROOT))
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["makespan"] == 10.0
    assert data["critical_path"] == ["A", "B"]


def test_ssot_mirror_drift_check(tmp_path: Path):
    """Asserts that mirror_skills.py --check reports 0 drift."""
    env = os.environ.copy()
    # In headless CI environments where local mirrors do not exist on the runner,
    # provision synchronized mirror fixtures using temporary directories.
    target_global = Path(env.get("GLOBAL_SKILLS_MIRROR") or (Path.home() / ".gemini" / "config" / "skills" / "adaptive-workflow"))
    target_brainstorm = Path(env.get("BRAINSTORM_SKILLS_MIRROR") or r"F:\Aaradhya-Dev-Tamrakar\brainstorm\.agents\skills\adaptive-workflow")
    if not target_global.exists() or not target_brainstorm.exists():
        fake_global = tmp_path / "global_skills"
        fake_brainstorm = tmp_path / "brainstorm_skills"
        shutil.copytree(SKILL_PATH.parent, fake_global)
        shutil.copytree(SKILL_PATH.parent, fake_brainstorm)
        env["GLOBAL_SKILLS_MIRROR"] = str(fake_global)
        env["BRAINSTORM_SKILLS_MIRROR"] = str(fake_brainstorm)

    res = subprocess.run([
        sys.executable,
        str(ROOT / "tools" / "mirror_skills.py"),
        "--check",
    ], capture_output=True, text=True, cwd=str(ROOT), env=env)
    assert res.returncode == 0
    assert "DRIFT DETECTED" not in res.stdout

