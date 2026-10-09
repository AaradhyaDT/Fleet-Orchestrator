"""
Unit tests for Antigravity Context Bridge in Fleet-Orchestrator.
Tests conversation discovery, chat context harvesting, Antigravity customizations,
worktree context projection, and ephemeral cleanup.
"""

import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch

from client.antigravity_bridge import (
    get_brain_dir,
    get_active_conversation_id,
    harvest_chat_context,
    harvest_antigravity_customizations,
    build_antigravity_scope,
    format_prompt_directives,
    project_worktree_context,
    cleanup_worktree_context,
)
from client.adapters.copilot_cli_adapter import CopilotCLIAdapter


def test_get_brain_dir(tmp_path):
    custom_app_data = tmp_path / "custom_agy"
    brain = get_brain_dir(custom_app_data)
    assert brain == custom_app_data / "brain"


def test_get_active_conversation_id(tmp_path):
    app_data = tmp_path / "antigravity"
    brain = app_data / "brain"
    brain.mkdir(parents=True)

    # Empty directory returns None
    assert get_active_conversation_id(app_data) is None

    # Create two conversations
    c1 = brain / "conv_old"
    c1.mkdir()
    c2 = brain / "conv_new"
    c2.mkdir()

    # Touch transcript in conv_new to make it newest
    t2 = c2 / ".system_generated" / "logs"
    t2.mkdir(parents=True)
    (t2 / "transcript.jsonl").write_text("{}", encoding="utf-8")

    active_id = get_active_conversation_id(app_data)
    assert active_id == "conv_new"


def test_harvest_chat_context(tmp_path):
    app_data = tmp_path / "antigravity"
    brain = app_data / "brain"
    cid = "test_conv_123"
    conv_dir = brain / cid
    logs_dir = conv_dir / ".system_generated" / "logs"
    logs_dir.mkdir(parents=True)

    # Mock transcript
    transcript_lines = [
        json.dumps({
            "step_index": 0,
            "type": "USER_INPUT",
            "content": "<USER_REQUEST>\nImplement rate damping governor in Fleet\n</USER_REQUEST>\n<ADDITIONAL_METADATA>\ntime=12:00\n</ADDITIONAL_METADATA>",
        }),
        json.dumps({
            "step_index": 1,
            "type": "PLANNER_RESPONSE",
            "content": "Understood.",
        }),
        json.dumps({
            "step_index": 2,
            "type": "USER_INPUT",
            "content": "<USER_REQUEST>\nExpand Antigravity scope to fleet orchestrator\n</USER_REQUEST>",
        }),
    ]
    (logs_dir / "transcript.jsonl").write_text("\n".join(transcript_lines), encoding="utf-8")

    # Mock artifact
    plan_file = conv_dir / "plan_execution.md"
    plan_file.write_text("# Execution Plan for Fleet Expansion\nDetails here...", encoding="utf-8")

    ctx = harvest_chat_context(conversation_id=cid, app_data_dir=app_data)
    assert ctx["conversation_id"] == cid
    assert "Expand Antigravity scope to fleet orchestrator" in ctx["session_goal"]
    assert len(ctx["recent_user_requests"]) == 2
    assert len(ctx["active_artifacts"]) == 1
    assert ctx["active_artifacts"][0]["title"] == "Execution Plan for Fleet Expansion"


def test_harvest_antigravity_customizations(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "AGENTS.md").write_text("# Agent Rules\nRule 1...", encoding="utf-8")

    config_dir = tmp_path / "config"
    skills_dir = config_dir / "skills"
    skills_dir.mkdir(parents=True)
    s1 = skills_dir / "writing-like-claude"
    s1.mkdir()
    (s1 / "SKILL.md").write_text("---\nname: writing-like-claude\n---\n", encoding="utf-8")

    custom = harvest_antigravity_customizations(repo_root=repo_root, config_dir=config_dir)
    assert "Commit Integrity" in custom["rules"][0]
    assert custom["repo_rules_path"] == str((repo_root / "AGENTS.md").resolve())
    assert "writing-like-claude" in custom["active_skills"]


def test_format_prompt_directives():
    scope = {
        "chat_context": {
            "conversation_id": "test_id_999",
            "session_goal": "Upgrade adaptive-workflow with Antigravity bridge",
            "recent_user_requests": ["First prompt", "Second prompt"],
            "active_artifacts": [{"file": "plan.md", "title": "Master Plan"}],
        },
        "antigravity_customizations": {
            "rules": ["Commit integrity enforced", "Calm writing standard"],
        },
    }
    header = format_prompt_directives(scope)
    assert "ANTIGRAVITY SESSION DIRECTIVES & LIVING CHAT CONTEXT" in header
    assert "Conversation ID: test_id_999" in header
    assert "Session Goal:    Upgrade adaptive-workflow with Antigravity bridge" in header
    assert "plan.md: Master Plan" in header
    assert "Commit integrity enforced" in header


def test_project_and_cleanup_worktree_context(tmp_path):
    worktree = tmp_path / "worktree_task_001"
    worktree.mkdir()

    scope = {
        "chat_context": {
            "conversation_id": "conv_abc",
            "session_goal": "Build filter kernel",
            "active_artifacts": [{"file": "spec.md", "title": "Filter Spec", "path": "F:/spec.md"}],
        },
        "antigravity_customizations": {
            "rules": ["Zero placeholder SHAs", "Local commit authorization"],
        },
    }

    # Project context
    project_worktree_context(worktree, scope)

    task_context_path = worktree / "TASK_CONTEXT.md"
    copilot_instr_path = worktree / ".github" / "copilot-instructions.md"
    marker_path = worktree / ".antigravity_projected"

    assert task_context_path.exists()
    assert copilot_instr_path.exists()
    assert marker_path.exists()

    content = task_context_path.read_text(encoding="utf-8")
    assert "conv_abc" in content
    assert "Build filter kernel" in content
    assert "Zero placeholder SHAs" in content

    # Cleanup context
    cleanup_worktree_context(worktree)

    assert not task_context_path.exists()
    assert not copilot_instr_path.exists()
    assert not marker_path.exists()


@pytest.mark.asyncio
async def test_copilot_cli_adapter_with_antigravity_scope(tmp_path):
    adapter = CopilotCLIAdapter(
        worker_id="cli-test",
        nickname="Tester",
        copilot_path="copilot.exe",
        worktree=str(tmp_path),
        allow_custom_instructions=True,
    )

    cmd = adapter.build_cli_command("Run test")
    assert "--no-custom-instructions" not in cmd

    scope = {
        "chat_context": {
            "conversation_id": "conv_xyz",
            "session_goal": "DSP filter tuning",
        },
        "antigravity_customizations": {
            "rules": ["Enforce type annotations"],
        },
    }

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Task completed successfully.", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        res = await adapter.execute_task(
            task_id="task_dsp_1",
            spec="Tune FIR coefficients",
            stage="code",
            context={"antigravity_scope": scope},
        )
        assert res["success"] is True
        # Verify prompt had the directives header
        call_args = mock_exec.call_args[0]
        p_index = call_args.index("-p")
        injected_prompt = call_args[p_index + 1]
        assert "ANTIGRAVITY SESSION DIRECTIVES" in injected_prompt
        assert "conv_xyz" in injected_prompt
        assert "DSP filter tuning" in injected_prompt
