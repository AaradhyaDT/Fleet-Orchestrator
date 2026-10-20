"""tests/test_azmuth_phase12.py
----------------------------
Unit and integration tests for Phase 12:
- Multi-Universe U0-U5 sweep and sweep persistence
- Structured ingestion feed recording
- Azmuth GUI View [4] rendering and left panel inspection
- Colab Hyper-Burst remote worker generator and ledger updates
"""

import json
from pathlib import Path
import pytest
import tkinter as tk

from tools import azmuth_daemon as daemon, azmuth_gui as gui, azmuth_macro_graph as macro
from tools.azmuth_macro_graph import sweep_all_universes
from tools.azmuth_daemon import record_ingestion_event
from tools.azmuth_gui import AzmuthCommandCenterGUI
from tools.azmuth_colab_burst import write_remote_worker_script


@pytest.fixture(autouse=True)
def isolate_state(monkeypatch, tmp_path):
    """Legacy integration checks must not append to the operator's live feed."""
    monkeypatch.setattr(macro, "DEFAULT_STATE_DIR", tmp_path)
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path)
    monkeypatch.setattr(daemon, "INGESTION_FEED", tmp_path / "azmuth_ingestion_feed.jsonl")
    monkeypatch.setattr(gui, "check_and_enforce_gear_safety", lambda: ("whisper", {}))
    for name in ("GH_CACHE_FILE", "CORPUS_LEDGER", "ARENA_LEDGER", "MUTATION_LEDGER", "INGESTION_FEED", "RUN_LOG_JSON", "SWEEP_JSON"):
        source = getattr(gui, name)
        target = tmp_path / source.name
        if source.exists():
            target.write_bytes(source.read_bytes())
        monkeypatch.setattr(gui, name, target)


def test_sweep_all_universes(tmp_path):
    res = sweep_all_universes()
    assert res.get("total_cartridges", 0) >= 6
    assert "universes" in res
    assert "u0_ecosystem_mesh" in res["universes"]
    assert "u4_macro_capital_markets" in res["universes"]

    sweep_file = tmp_path / "macro_foresight_sweep.json"
    assert sweep_file.exists()
    saved = json.loads(sweep_file.read_text(encoding="utf-8"))
    assert saved.get("total_cartridges") >= 6


def test_record_ingestion_event(tmp_path):
    test_feed = tmp_path / "azmuth_ingestion_feed.jsonl"
    record_ingestion_event(
        event_type="TEST_EVENT",
        source="TestRunner",
        item_id="test_item_001",
        title="Test Ingestion Item",
        status="SUCCESS",
        details={"accuracy": 0.99},
    )
    assert test_feed.exists()
    lines = test_feed.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1
    last_event = json.loads(lines[-1])
    assert last_event["event_type"] == "TEST_EVENT"
    assert last_event["item_id"] == "test_item_001"
    assert last_event["details"]["accuracy"] == 0.99


def test_gui_view4_rendering():
    root = tk.Tk()
    root.withdraw()
    try:
        app = AzmuthCommandCenterGUI(root)
        app.switch_view("ingestion")
        assert app.active_view == "ingestion"
        assert len(app.left_items_meta) >= 1

        app._redraw_active_canvas()
        # Verify funnel cards + universe lobes rendered
        assert len(app.canvas_nodes) >= 10
        assert any("FUNNEL" in nid for nid in app.canvas_nodes.keys())
        assert any("UNIVERSE_LOBE" in nid for nid in app.canvas_nodes.keys())

        # Test selecting ingestion item
        app._inspect_ingestion_event({
            "event_type": "COLAB_A100_HYPERBURST",
            "source": "ColabCloudAccelerator",
            "title": "A100 80GB Hyper-Burst Active",
            "timestamp": "2026-10-18T16:55:00Z",
            "status": "SUCCESS",
            "details": {"system_ram_gb": 167.05, "vram_gb": 79.25},
        })
        insp_content = app.inspector_text.get("1.0", tk.END)
        assert "A100 80GB Hyper-Burst Active" in insp_content
        assert "167.05" in insp_content
    finally:
        root.destroy()


def test_remote_worker_script_generation(tmp_path):
    dest = tmp_path / "remote_worker.py"
    write_remote_worker_script(dest, monte_carlo_trials=500)
    assert dest.exists()
    code = dest.read_text(encoding="utf-8")
    assert "AZMUTH CLOUD HYPER-BURST ACTIVE" in code
    assert "/dev/shm/azmuth_burst" in code
    assert "Monte Carlo" in code
    # Verify syntax compiles cleanly
    compiled = compile(code, str(dest), "exec")
    assert compiled is not None
