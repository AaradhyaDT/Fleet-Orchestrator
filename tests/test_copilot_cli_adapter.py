"""Unit tests for CopilotCLIAdapter in Claude-Desktop."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from client.adapters.copilot_cli_adapter import CopilotCLIAdapter


@pytest.mark.asyncio
async def test_copilot_cli_init():
    adapter = CopilotCLIAdapter(
        worker_id="copilot-cli-1",
        nickname="Copilot Agent 1",
        copilot_path="copilot.exe",
        worktree="F:/tmp/workspace",
        model="gpt-5.4",
        timeout=60.0,
    )
    assert adapter.worker_id == "copilot-cli-1"
    assert adapter.copilot_path == "copilot.exe"
    assert adapter.model == "gpt-5.4"
    assert adapter.timeout == 60.0
    assert "code" in adapter.capabilities


@pytest.mark.asyncio
async def test_copilot_cli_build_command():
    adapter = CopilotCLIAdapter(
        worker_id="copilot-cli-1",
        nickname="Agent",
        copilot_path="copilot.exe",
        model="claude-3.7-sonnet",
        worktree="F:/workspace",
        max_autopilot_continues=3,
    )
    cmd = adapter.build_cli_command("Do the task", usage_file="usage.json")

    assert cmd[0] == "copilot.exe"
    assert "-p" in cmd
    assert "Do the task" in cmd
    assert "--autopilot" in cmd
    assert "--allow-all" in cmd
    assert "--no-ask-user" in cmd
    assert "--no-auto-update" in cmd
    assert "--model" in cmd
    assert "claude-3.7-sonnet" in cmd
    assert "--usage-output-file" in cmd
    assert "usage.json" in cmd
    assert "--max-autopilot-continues" in cmd
    assert "3" in cmd


@pytest.mark.asyncio
async def test_copilot_cli_check_health_success():
    adapter = CopilotCLIAdapter("cli-1", "Agent", copilot_path="copilot.exe")

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"GitHub Copilot CLI 1.0.91", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        health = await adapter.check_health()
        assert health is True


@pytest.mark.asyncio
async def test_copilot_cli_check_health_failure():
    adapter = CopilotCLIAdapter("cli-1", "Agent", copilot_path="nonexistent_copilot_bin")

    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("not found")):
        health = await adapter.check_health()
        assert health is False


@pytest.mark.asyncio
async def test_copilot_cli_execute_task_success(tmp_path):
    adapter = CopilotCLIAdapter(
        worker_id="cli-1",
        nickname="Agent",
        copilot_path="copilot.exe",
        worktree=str(tmp_path),
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"All tests created and verified passing.", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = await adapter.execute_task(
            task_id="task_cli_001",
            spec="Implement retry logic",
            stage="code",
            context={"lang": "python"},
        )

        assert res["success"] is True
        assert "All tests created" in res["result_text"]
        assert res["error"] is None


@pytest.mark.asyncio
async def test_copilot_cli_execute_task_timeout():
    adapter = CopilotCLIAdapter(
        worker_id="cli-1",
        nickname="Agent",
        copilot_path="copilot.exe",
        timeout=0.01,
    )

    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = asyncio.TimeoutError()
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = await adapter.execute_task(
            task_id="task_cli_timeout",
            spec="Long running task",
            stage="code",
            context={},
        )

        assert res["success"] is False
        assert "TIMEOUT" in res["error"]


@pytest.mark.asyncio
async def test_copilot_cli_env_and_credits_isolation(tmp_path):
    copilot_home = tmp_path / "custom_copilot_home"
    dummy_tok = "mock" + "_dummy_pat_123"
    adapter = CopilotCLIAdapter(
        worker_id="cli-isolated",
        nickname="Isolated Worker",
        copilot_path="copilot.exe",
        github_token=dummy_tok,
        copilot_home=copilot_home,
        max_ai_credits=25,
    )

    # Check CLI command contains max-ai-credits
    cmd = adapter.build_cli_command("Run isolated")
    assert "--max-ai-credits" in cmd
    assert "25" in cmd

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Execution complete", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        res = await adapter.execute_task("task_iso", "spec", "code", {})
        assert res["success"] is True

        # Verify child environment passed to subprocess
        _, kwargs = mock_exec.call_args
        env_passed = kwargs.get("env", {})
        assert env_passed.get("COPILOT_GITHUB_TOKEN") == dummy_tok
        assert env_passed.get("COPILOT_HOME") == str(copilot_home)
        assert env_passed.get("COPILOT_AUTO_UPDATE") == "0"
        assert env_passed.get("COPILOT_CACHE_HOME") == str(copilot_home / "cache")
        assert env_passed.get("COPILOT_PKG_CACHE_HOME") == str(copilot_home / "pkg_cache")
        assert copilot_home.exists()
        assert (copilot_home / "cache").exists()
        assert (copilot_home / "pkg_cache").exists()


@pytest.mark.asyncio
async def test_copilot_cli_usage_file_parsing():
    adapter = CopilotCLIAdapter(
        worker_id="cli-usage",
        nickname="Usage Tester",
        copilot_path="copilot.exe",
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Autopilot task completed", b"")

    async def fake_subprocess_exec(*args, **kwargs):
        # Find usage file from args
        if "--usage-output-file" in args:
            idx = args.index("--usage-output-file")
            usage_file = Path(args[idx + 1])
            usage_file.write_text(json.dumps({
                "total_tokens": 850,
                "credits_used": 3,
                "model": "gpt-4o",
            }), encoding="utf-8")
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess_exec):
        res = await adapter.execute_task("task_usage", "spec", "code", {})
        assert res["success"] is True
        assert res["credits_used"] == 3
        assert res["tokens_used"] == 850
        assert res["model_used"] == "gpt-4o"
        assert res["quota_exhausted"] is False


@pytest.mark.asyncio
async def test_copilot_cli_quota_exhaustion_detection():
    adapter = CopilotCLIAdapter(
        worker_id="cli-quota",
        nickname="Quota Tester",
        copilot_path="copilot.exe",
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"Error: Usage limit reached. 429 Rate limit / Out of credits.")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = await adapter.execute_task("task_quota", "spec", "code", {})
        assert res["success"] is False
        assert res["quota_exhausted"] is True


@pytest.mark.asyncio
async def test_copilot_cli_nano_aiu_parsing():
    adapter = CopilotCLIAdapter(
        worker_id="cli-nano",
        nickname="Nano AIU Tester",
        copilot_path="copilot.exe",
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Task done\nAI Credits 0.55 (12s)", b"")

    async def fake_subprocess_exec(*args, **kwargs):
        if "--usage-output-file" in args:
            idx = args.index("--usage-output-file")
            usage_file = Path(args[idx + 1])
            usage_file.write_text(json.dumps({
                "totalNanoAiu": 553220000,
                "currentModel": "mai-code-1.1-flash",
                "tokenDetails": {
                    "input": {"tokenCount": 27500},
                    "cache_read": {"tokenCount": 1280},
                    "output": {"tokenCount": 20},
                },
            }), encoding="utf-8")
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess_exec):
        res = await adapter.execute_task("task_nano", "spec", "code", {})
        assert res["success"] is True
        assert res["credits_used"] == 0.55
        assert res["tokens_used"] == 28800
        assert res["model_used"] == "mai-code-1.1-flash"


@pytest.mark.asyncio
async def test_copilot_cli_stdout_credits_fallback():
    adapter = CopilotCLIAdapter(
        worker_id="cli-fallback",
        nickname="Fallback Tester",
        copilot_path="copilot.exe",
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Changes +1 -0\nAI Credits 1.75 (10s)\nTokens 500", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = await adapter.execute_task("task_fallback", "spec", "code", {})
        assert res["success"] is True
        assert res["credits_used"] == 1.75


@pytest.mark.asyncio
async def test_copilot_cli_build_command_auto_tier():
    adapter = CopilotCLIAdapter(
        worker_id="copilot-cli-1",
        nickname="Agent",
        copilot_path="copilot.exe",
        auto_tier="balance",
    )
    cmd = adapter.build_cli_command("Run balance task")
    assert "--model" in cmd
    assert "auto" in cmd
    assert "--auto-tier" in cmd
    assert "balance" in cmd


@pytest.mark.asyncio
async def test_copilot_cli_auto_tier_precedence():
    # When auto_tier is specified, it should set --model auto and --auto-tier <tier>
    adapter = CopilotCLIAdapter(
        worker_id="copilot-cli-1",
        nickname="Agent",
        copilot_path="copilot.exe",
        model="gpt-5.4",
        auto_tier="efficiency",
    )
    cmd = adapter.build_cli_command("Run efficiency task")
    assert "--auto-tier" in cmd
    assert "efficiency" in cmd
    assert "auto" in cmd
    assert "gpt-5.4" not in cmd


@pytest.mark.asyncio
async def test_copilot_cli_build_command_rea_flags():
    # Test default disallow-temp-dir injection
    adapter_default = CopilotCLIAdapter("cli-rea-1", "Agent", copilot_path="copilot.exe")
    cmd_default = adapter_default.build_cli_command("Task prompt")
    assert "--disallow-temp-dir" in cmd_default
    assert "--headless" not in cmd_default

    # Test disallow_temp_dir=False
    adapter_allow_tmp = CopilotCLIAdapter("cli-rea-2", "Agent", copilot_path="copilot.exe", disallow_temp_dir=False)
    cmd_allow_tmp = adapter_allow_tmp.build_cli_command("Task prompt")
    assert "--disallow-temp-dir" not in cmd_allow_tmp

    # Test headless=True
    adapter_headless = CopilotCLIAdapter("cli-rea-3", "Agent", copilot_path="copilot.exe", headless=True)
    cmd_headless = adapter_headless.build_cli_command("Task prompt")
    assert "--headless" in cmd_headless
    assert "--disallow-temp-dir" in cmd_headless


@pytest.mark.asyncio
async def test_copilot_cli_child_env_hardening(tmp_path):
    captured_env = {}

    async def fake_spawn(*cmd, **kwargs):
        nonlocal captured_env
        captured_env = kwargs.get("env", {})
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"Done", b"")
        return proc

    adapter = CopilotCLIAdapter(
        worker_id="cli-env-test",
        nickname="Env Agent",
        copilot_path="copilot.exe",
        github_token="placeholder_token",
        copilot_home=str(tmp_path / "copilot_home"),
    )

    with patch("client.adapters.copilot_cli_adapter.spawn_background", side_effect=fake_spawn):
        res = await adapter.execute_task("t_env", "spec", "code", {})
        assert res["success"] is True
        assert captured_env.get("COPILOT_ALLOW_ALL") == "true"
        assert captured_env.get("COPILOT_FORCE_WINDOWS_HIDE") == "1"
        assert captured_env.get("COPILOT_DEBUG_SKIP_LAUNCH_CHECKS") == "1"
        assert captured_env.get("COPILOT_GITHUB_TOKEN") == "placeholder_token"


@pytest.mark.asyncio
async def test_copilot_cli_sqlite_telemetry_extraction(tmp_path):
    import sqlite3

    db_path = tmp_path / "session-store.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE assistant_usage_events (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            turn_index INTEGER,
            model TEXT,
            copilot_usage_model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_write_tokens INTEGER,
            reasoning_tokens INTEGER,
            total_nano_aiu INTEGER,
            request_multiplier REAL,
            duration_ms INTEGER,
            time_to_first_token_ms REAL,
            output_ttft_ms REAL,
            inter_token_latency_ms REAL,
            initiator TEXT,
            api_endpoint TEXT,
            reasoning_effort TEXT,
            finish_reason TEXT,
            content_filter_triggered INTEGER,
            token_details_json TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO assistant_usage_events (
            session_id, turn_index, model, input_tokens, output_tokens,
            cache_read_tokens, cache_write_tokens, reasoning_tokens,
            total_nano_aiu, duration_ms, api_endpoint, reasoning_effort, finish_reason
        ) VALUES (
            'test-session-uuid-1', 0, 'gpt-6-luna', 15000, 100,
            12000, 3000, 50,
            250000000, 3200, 'ws:/responses', 'medium', 'stop'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO assistant_usage_events (
            session_id, turn_index, model, input_tokens, output_tokens,
            cache_read_tokens, cache_write_tokens, reasoning_tokens,
            total_nano_aiu, duration_ms, api_endpoint, reasoning_effort, finish_reason
        ) VALUES (
            'test-session-uuid-1', 1, 'gpt-6-luna', 20000, 200,
            18000, 2000, 80,
            350000000, 4500, 'ws:/responses', 'medium', 'stop'
        )
        """
    )
    conn.commit()
    conn.close()

    telemetry = CopilotCLIAdapter.extract_sqlite_session_telemetry(tmp_path)
    assert telemetry["session_id"] == "test-session-uuid-1"
    assert telemetry["model"] == "gpt-6-luna"
    assert telemetry["total_input_tokens"] == 35000
    assert telemetry["total_output_tokens"] == 300
    assert telemetry["total_cache_read_tokens"] == 30000
    assert telemetry["total_reasoning_tokens"] == 130
    assert telemetry["total_nano_aiu"] == 600000000
    assert telemetry["total_duration_ms"] == 7700
    assert telemetry["api_endpoint"] == "ws:/responses"


@pytest.mark.asyncio
async def test_copilot_cli_rate_limit_categorization():
    adapter = CopilotCLIAdapter("cli-rl", "RateLimit Tester", copilot_path="copilot.exe")

    cases = [
        ("Error: user_weekly_rate_limited. Please wait for limit to reset", True, False, "user_weekly_rate_limited"),
        ("Error: user_model_rate_limited on gpt-5.4", False, True, "user_model_rate_limited"),
        ("Error: user_global_rate_limited in session", False, True, "user_global_rate_limited"),
        ("Error: integration_rate_limited: token limit reached", False, True, "integration_rate_limited"),
        ("HTTP 429: Too Many Requests", False, True, "rate_limited_429"),
        ("Error: monthly credits exhausted for account", True, False, "quota_exhausted"),
    ]

    for stderr_msg, exp_quota, exp_429, exp_kind in cases:
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"", stderr_msg.encode("utf-8"))

        with patch("client.adapters.copilot_cli_adapter.spawn_background", return_value=mock_proc):
            res = await adapter.execute_task("t_rl", "spec", "code", {})
            assert res["success"] is False
            assert res["quota_exhausted"] is exp_quota, f"Failed for {stderr_msg}"
            assert res["rate_limited_429"] is exp_429, f"Failed for {stderr_msg}"
            assert res["rate_limit_kind"] == exp_kind, f"Failed for {stderr_msg}"


@pytest.mark.asyncio
async def test_copilot_cli_execute_task_merges_sqlite_telemetry(tmp_path):
    import sqlite3

    db_path = tmp_path / "session-store.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE assistant_usage_events (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            turn_index INTEGER,
            model TEXT,
            copilot_usage_model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_write_tokens INTEGER,
            reasoning_tokens INTEGER,
            total_nano_aiu INTEGER,
            request_multiplier REAL,
            duration_ms INTEGER,
            time_to_first_token_ms REAL,
            output_ttft_ms REAL,
            inter_token_latency_ms REAL,
            initiator TEXT,
            api_endpoint TEXT,
            reasoning_effort TEXT,
            finish_reason TEXT,
            content_filter_triggered INTEGER,
            token_details_json TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO assistant_usage_events (
            session_id, turn_index, model, input_tokens, output_tokens,
            cache_read_tokens, cache_write_tokens, reasoning_tokens,
            total_nano_aiu, duration_ms, api_endpoint, reasoning_effort, finish_reason
        ) VALUES (
            'session-live-01', 0, 'gpt-6-luna', 50000, 500,
            40000, 10000, 200,
            1500000000, 6200, 'ws:/responses', 'medium', 'stop'
        )
        """
    )
    conn.commit()
    conn.close()

    adapter = CopilotCLIAdapter(
        worker_id="cli-merge-test",
        nickname="Merge Tester",
        copilot_path="copilot.exe",
        copilot_home=str(tmp_path),
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"All done successfully", b"")

    with patch("client.adapters.copilot_cli_adapter.spawn_background", return_value=mock_proc):
        res = await adapter.execute_task("t_merge", "spec", "code", {})
        assert res["success"] is True
        assert res["credits_used"] == 1.5  # 1,500,000,000 nanoAiu = 1.5 credits
        assert res["tokens_used"] == 50500
        assert res["model_used"] == "gpt-6-luna"
        assert res["session_telemetry"]["session_id"] == "session-live-01"
        assert res["session_telemetry"]["total_reasoning_tokens"] == 200
        assert res["rate_limit_kind"] is None

