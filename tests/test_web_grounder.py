"""Unit tests for tools/web_grounder.py (INV-REALTIME-GROUNDING)."""

import json
from pathlib import Path
from tools.web_grounder import (
    load_grounding_cache,
    atomic_save_cache,
    query_pypi,
    inspect_local_cli,
    get_grounding_summary,
)


def test_load_and_atomic_save_cache(tmp_path, monkeypatch):
    test_cache_file = tmp_path / "test_grounding_cache.json"
    monkeypatch.setattr("tools.web_grounder.CACHE_FILE", test_cache_file)

    cache = load_grounding_cache()
    assert "packages" in cache
    assert "cli_tools" in cache

    cache["packages"]["test-pkg"] = {"latest_version": "1.0.0"}
    success = atomic_save_cache(cache)
    assert success is True
    assert test_cache_file.exists()

    reloaded = load_grounding_cache()
    assert reloaded["packages"]["test-pkg"]["latest_version"] == "1.0.0"


def test_query_pypi_validation():
    # Invalid package names with traversal or illegal characters must be rejected
    res = query_pypi("../../etc/passwd")
    assert "error" in res
    assert "Invalid package name format" in res["error"]

    res2 = query_pypi("invalid name with spaces")
    assert "error" in res2


def test_inspect_local_cli():
    # python executable should always be detected
    res = inspect_local_cli("python")
    assert res["installed"] is True
    assert "installed_version" in res
    assert res["source"] == "host_binary"


def test_get_grounding_summary():
    summary = get_grounding_summary()
    assert "[REAL-TIME GROUNDING KNOWLEDGE BASE]" in summary
