"""tests/test_azmuth_github_sensor.py
-----------------------------------
Unit tests for the Azmuth Autonomous GitHub Sensory Harvester & Intelligence Radar.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import pytest

from tools.azmuth_github_sensor import (
    AzmuthGitHubSensor,
    GitHubTokenPool,
    RotatingGitHubClient,
)


@pytest.fixture
def mock_env_file(tmp_path: Path) -> Path:
    """Creates a temporary .env file with dummy PATs for isolated testing."""
    env_file = tmp_path / ".env.fleet.test"
    content = "\n".join([
        "# Test Accounts",
        "COPILOT_ACCOUNT_1_TOKEN=mock_1",
        "COPILOT_ACCOUNT_2_TOKEN=mock_2",
        "COPILOT_ACCOUNT_3_TOKEN=mock_3",
    ])
    env_file.write_text(content, encoding="utf-8")
    return env_file


def test_token_pool_initialization_and_rotation(mock_env_file: Path):
    pool = GitHubTokenPool(env_files=[mock_env_file])
    assert len(pool.tokens) == 3
    assert pool.tokens[0]["id"] == "account_1"
    assert pool.tokens[0]["status"] == "READY"

    # Rotation test
    tok1 = pool.acquire_token(scope="core")
    tok2 = pool.acquire_token(scope="core")
    tok3 = pool.acquire_token(scope="core")
    tok4 = pool.acquire_token(scope="core")

    assert tok1["id"] == "account_1"
    assert tok2["id"] == "account_2"
    assert tok3["id"] == "account_3"
    assert tok4["id"] == "account_1"  # Round-robin cycle


def test_token_pool_rate_limit_and_cooldown(mock_env_file: Path):
    pool = GitHubTokenPool(env_files=[mock_env_file])
    acc1 = pool.acquire_token(scope="core")

    # Simulate header update
    headers = {
        "x-ratelimit-remaining": "4500",
        "x-ratelimit-reset": str(time.time() + 3600),
    }
    pool.record_usage(acc1["id"], "core", 200, headers)
    assert pool.tokens[0]["remaining_core"] == 4500

    # Simulate rate limiting (remaining = 0)
    limit_headers = {
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": str(time.time() + 1800),
    }
    pool.record_usage(acc1["id"], "core", 403, limit_headers)
    assert pool.tokens[0]["remaining_core"] == 0

    # Next acquire should skip account_1
    next_acc = pool.acquire_token(scope="core")
    assert next_acc["id"] == "account_2"


def test_thalamic_noise_filter(tmp_path: Path):
    sensor = AzmuthGitHubSensor(cache_file=tmp_path / "cache.json", brief_file=tmp_path / "brief.md")
    raw = {
        "opportunities": [
            {"id": "test/repo#1", "salience": 1.8, "title": "Good issue"},
            {"id": "test/repo#2", "salience": 0.5, "title": "Low salience spam"},
        ],
        "releases": [{"repo": "unsloth", "tag": "v1.0"}],
        "cp_archives": [{"repo": "kactl", "stars": 3000}],
        "ecosystem": [{"repo": "brainstorm", "open_issues_count": 0}],
    }
    filtered = sensor.filter_actionable_signals(raw)
    assert len(filtered["opportunities"]) == 1
    assert filtered["opportunities"][0]["id"] == "test/repo#1"
    assert len(filtered["releases"]) == 1
    assert len(filtered["cp_archives"]) == 1


def test_offline_fallback_capabilities(tmp_path: Path):
    # Initialize with empty pool so all calls trigger fallback safely
    empty_pool = GitHubTokenPool(env_files=[tmp_path / "non_existent.env"])
    sensor = AzmuthGitHubSensor(cache_file=tmp_path / "cache.json", brief_file=tmp_path / "brief.md", pool=empty_pool)

    opps = sensor._fallback_lab_opportunities()
    assert len(opps) > 0
    assert "openvino" in opps[0]["repo"]

    rels = sensor._fallback_sota_releases()
    assert len(rels) > 0
    assert "unsloth" in rels[0]["repo"]

    cps = sensor._fallback_cp_archives()
    assert len(cps) > 0
    assert "ac-library" in cps[0]["repo"]


def test_cached_telemetry_lifecycle(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    brief_file = tmp_path / "brief.md"
    sensor = AzmuthGitHubSensor(cache_file=cache_file, brief_file=brief_file)

    # Patch client to return fast mock data
    mock_item = {
        "id": 1234,
        "number": 42,
        "title": "Add Fast LoRA Operator",
        "repository_url": "https://api.github.com/repos/org/repo",
        "html_url": "https://github.com/org/repo/issues/42",
        "labels": [{"name": "help wanted"}],
        "comments": 3,
        "created_at": "2026-10-17T00:00:00Z",
        "updated_at": "2026-10-17T01:00:00Z",
    }
    mock_search = {"items": [mock_item]}

    with patch.object(sensor.client, "request", return_value=(200, mock_search, {})):
        data = sensor.get_cached_telemetry(force_refresh=True)
        assert cache_file.exists()
        assert brief_file.exists()
        assert "opportunities" in data
        assert len(data["opportunities"]) >= 1

        # Second read within TTL should return cached state without network calls
        with patch.object(sensor.client, "request", side_effect=RuntimeError("Should not be called")):
            cached = sensor.get_cached_telemetry(force_refresh=False, ttl_seconds=600.0)
            assert cached == data
