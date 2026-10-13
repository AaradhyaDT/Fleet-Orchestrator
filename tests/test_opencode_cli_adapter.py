from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from client.adapters.opencode_cli_adapter import OpenCodeCLIAdapter


def _adapter(workspace, **kwargs):
    return OpenCodeCLIAdapter(
        worker_id="opencode-test",
        nickname="OpenCode Test",
        workspace_dir=workspace,
        **kwargs,
    )


def test_build_command_has_worktree_model_variant_and_auto(tmp_path):
    adapter = _adapter(
        tmp_path,
        opencode_path="opencode-test",
        model="openai/gpt-5",
        variant="high",
    )

    assert adapter.build_cli_command("do work") == [
        "opencode-test",
        "run",
        "--format",
        "json",
        "--dir",
        str(tmp_path.resolve()),
        "--model",
        "openai/gpt-5",
        "--variant",
        "high",
        "--auto",
        "do work",
    ]


def test_build_command_omits_optional_flags_when_unset(tmp_path):
    adapter = _adapter(tmp_path, auto_approve=False)
    command = adapter.build_cli_command("do work")

    assert "--model" not in command
    assert "--variant" not in command
    assert "--auto" not in command
    assert command[-1] == "do work"


def test_build_command_requires_configured_worktree():
    adapter = _adapter(None)
    with pytest.raises(ValueError, match="Workspace or Worktree"):
        adapter.build_cli_command("do work")


def test_parse_jsonl_text_events_and_malformed_output():
    output = "\n".join(
        [
            '{"type":"step_start","part":{"type":"step-start"}}',
            '{"type":"text","part":{"type":"text","text":"Done."}}',
            "this is not json",
        ]
    )
    assert OpenCodeCLIAdapter._parse_jsonl_output(output) == ("Done.", None)
    assert OpenCodeCLIAdapter._parse_jsonl_output("not json") == (
        "",
        "OpenCode CLI returned malformed JSON event output",
    )


@pytest.mark.asyncio
async def test_execute_task_returns_text_from_json_events(tmp_path):
    proc = SimpleNamespace(
        returncode=0,
        communicate=AsyncMock(
            return_value=(
                b'{"type":"text","part":{"text":"Completed the requested change."}}\n',
                b"",
            )
        ),
    )
    adapter = _adapter(tmp_path)
    with patch(
        "client.adapters.opencode_cli_adapter.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)
    ) as spawn:
        result = await adapter.execute_task("task-1", "make a change", "code", {})

    assert result["success"] is True
    assert result["result_text"] == "Completed the requested change."
    assert result["task_id"] == "task-1"
    assert spawn.await_args.kwargs["cwd"] == str(tmp_path.resolve())


@pytest.mark.asyncio
async def test_execute_task_surfaces_nonzero_process_and_stderr(tmp_path):
    proc = SimpleNamespace(
        returncode=2,
        communicate=AsyncMock(return_value=(b"", b"authentication or quota failure")),
    )
    adapter = _adapter(tmp_path)
    with patch("client.adapters.opencode_cli_adapter.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        result = await adapter.execute_task("task-2", "do work", "code", {})

    assert result["success"] is False
    assert "authentication or quota failure" in result["error"]


@pytest.mark.asyncio
async def test_execute_task_times_out_and_kills_process(tmp_path):
    async def slow_communicate():
        await asyncio.sleep(1)

    proc = SimpleNamespace(
        returncode=None,
        communicate=AsyncMock(side_effect=slow_communicate),
        kill=lambda: setattr(proc, "returncode", -9),
        wait=AsyncMock(),
    )
    adapter = _adapter(tmp_path, timeout=0.01)
    with patch("client.adapters.opencode_cli_adapter.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        result = await adapter.execute_task("task-3", "do work", "code", {})

    assert result["success"] is False
    assert "timed out after 0.01s" in result["error"]
    proc.wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_task_fails_if_worktree_is_missing(tmp_path):
    adapter = _adapter(tmp_path / "does-not-exist")
    result = await adapter.execute_task("task-4", "do work", "code", {})

    assert result["success"] is False
    assert "does not exist" in result["error"]
