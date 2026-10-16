"""tests/test_azmuth_ram_and_corpus.py
-------------------------------------
Unit tests for Azmuth RAM safety gates and autonomous corpus harvesting.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from tools.azmuth_daemon import get_memory_status_gb, has_sufficient_ram, execute_idle_burst
from tools.azmuth_corpus_harvester import (
    extract_invariants_from_solution,
    load_corpus_ledger,
    save_corpus_ledger,
)


def test_get_memory_status_gb():
    """Verify that memory status returns valid tuple (total, free, load)."""
    total, free, load = get_memory_status_gb()
    assert total > 0.0
    assert free >= 0.0
    assert 0 <= load <= 100


def test_has_sufficient_ram_logic():
    """Verify threshold enforcement for RAM safety."""
    with patch("tools.azmuth_daemon.get_memory_status_gb", return_value=(16.0, 8.0, 50)):
        assert has_sufficient_ram(min_avail_gb=4.0, max_load_percent=75) is True

    # Fails when free RAM < 4.0 GB
    with patch("tools.azmuth_daemon.get_memory_status_gb", return_value=(16.0, 3.2, 50)):
        assert has_sufficient_ram(min_avail_gb=4.0, max_load_percent=75) is False

    # Fails when load > 75%
    with patch("tools.azmuth_daemon.get_memory_status_gb", return_value=(16.0, 6.0, 85)):
        assert has_sufficient_ram(min_avail_gb=4.0, max_load_percent=75) is False


def test_execute_idle_burst_aborts_on_low_ram():
    """Verify that idle burst gracefully bails without work if RAM is below threshold."""
    with patch("tools.azmuth_daemon.has_sufficient_ram", return_value=False):
        res = execute_idle_burst()
        assert res.get("aborted_due_to_ram") is True
        assert len(res.get("tasks_executed", [])) == 0


def test_extract_invariants_cpp():
    """Test deterministic extraction of C++ fast I/O and zero-allocation graph patterns."""
    sample_cpp = """
    #include <iostream>
    #pragma GCC optimize("O3")
    using namespace std;

    int head[1000], to[2000], next_edge[2000];

    int main() {
        ios_base::sync_with_stdio(false);
        cin.tie(NULL);
        return 0;
    }
    """
    invariants = extract_invariants_from_solution(sample_cpp, lang="cpp")
    types = [inv["type"] for inv in invariants]
    assert "fast_io" in types
    assert "compiler_pragma" in types
    assert "zero_alloc_graph" in types


def test_corpus_ledger_roundtrip(tmp_path: Path):
    """Test reading and writing the incremental ingestion ledger."""
    test_ledger = tmp_path / "test_ledger.json"
    with patch("tools.azmuth_corpus_harvester.CORPUS_LEDGER", test_ledger):
        data = load_corpus_ledger()
        assert data["version"] == 1
        data["tasks_processed"].append("demo_task")
        save_corpus_ledger(data)

        reloaded = load_corpus_ledger()
        assert "demo_task" in reloaded["tasks_processed"]
