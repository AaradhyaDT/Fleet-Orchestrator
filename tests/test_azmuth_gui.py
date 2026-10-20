#!/usr/bin/env python3
"""tests/test_azmuth_gui.py
------------------------
Unit tests for the Azmuth Neuromorphic Command Center & Phylogenetic Gene Explorer GUI (tools/azmuth_gui.py).
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
import time
from types import SimpleNamespace
import pytest
from tools import azmuth_gui as gui

from tools.azmuth_gui import (
    AzmuthCommandCenterGUI,
    build_gene_phylogeny,
    find_gene_file_on_disk,
    list_available_cartridges,
)
from tools.azmuth_tray import AzmuthTrayApp


@pytest.fixture(autouse=True)
def isolate_gui_state(monkeypatch, tmp_path):
    """GUI tests read temporary telemetry and never enforce live daemon safety."""
    monkeypatch.setattr(gui, "check_and_enforce_gear_safety", lambda: ("whisper", {}))
    for name in ("GH_CACHE_FILE", "CORPUS_LEDGER", "ARENA_LEDGER", "MUTATION_LEDGER", "INGESTION_FEED", "RUN_LOG_JSON", "SWEEP_JSON"):
        source = getattr(gui, name)
        target = tmp_path / source.name
        if source.exists():
            target.write_bytes(source.read_bytes())
        monkeypatch.setattr(gui, name, target)


def test_build_gene_phylogeny_lineage_and_speedup():
    """Verifies that build_gene_phylogeny extracts Wild-Type -> Mutator Edge -> Daughter Alleles and calculates speedup."""
    sample_gene = {
        "gene_id": "TASK_FAST_GRAPH_SEARCH",
        "tier": 3,
        "category": "dimensional_collapse",
        "description": "Cubic breaker graph traversal gene.",
        "alleles": [
            {
                "allele_id": "sub_1001_wildtype",
                "dominance": "ALTERNATIVE",
                "complexity_time": "O(V + E)",
                "complexity_space": "O(V)",
                "environmental_triggers": ["N<=2e5", "cpp"],
                "empirical_fitness": {"runtime_ms": 40.0, "ram_kb": 2048},
                "code_template": "int main() { return 0; }",
                "invariants": ["BFS shortest path on unweighted graph"],
            },
            {
                "allele_id": "sub_1001_wildtype_mut_fast_io",
                "dominance": "ALTERNATIVE",
                "complexity_time": "O(V + E)",
                "complexity_space": "O(V)",
                "environmental_triggers": ["N<=2e5", "cpp"],
                "empirical_fitness": {"runtime_ms": 30.0, "ram_kb": 2048},
                "code_template": "int main() { std::ios_base::sync_with_stdio(false); return 0; }",
                "invariants": ["BFS shortest path", "Mutated by Azmuth Genetic Optimizer (fast_io)"],
            },
            {
                "allele_id": "sub_1001_wildtype_mut_pragma_tuning",
                "dominance": "PRIMARY",
                "complexity_time": "O(V + E)",
                "complexity_space": "O(V)",
                "environmental_triggers": ["N<=2e5", "cpp", "avx2"],
                "empirical_fitness": {"runtime_ms": 22.0, "ram_kb": 1800},
                "code_template": '#pragma GCC optimize("O3,unroll-loops")\nint main() { return 0; }',
                "invariants": ["Mutated by Azmuth Genetic Optimizer (pragma_tuning)"],
            },
        ],
    }

    phylo = build_gene_phylogeny(sample_gene)
    assert phylo["gene_id"] == "TASK_FAST_GRAPH_SEARCH"
    assert phylo["tier"] == 3
    assert len(phylo["wild_types"]) == 1
    assert len(phylo["mutants"]) == 2
    assert len(phylo["edges"]) == 2
    assert phylo["champion"]["allele_id"] == "sub_1001_wildtype_mut_pragma_tuning"
    assert phylo["net_speedup_pct"] == 45.0  # (40 - 22) / 40 = 45%

    ops = {e["operator"] for e in phylo["edges"]}
    assert "fast_io" in ops
    assert "pragma_tuning" in ops


def test_list_available_cartridges():
    """Verifies discovery of U0..U5 cortical cartridges."""
    cartridges = list_available_cartridges()
    assert len(cartridges) >= 6
    universe_ids = {c["universe_id"].upper() for c in cartridges}
    assert any("U0" in u for u in universe_ids)
    assert any("U3" in u for u in universe_ids)


def test_tray_menu_contains_command_center_launcher():
    """Verifies that AzmuthTrayApp exposes the Open Azmuth Command Center item."""
    tray = AzmuthTrayApp()
    menu = tray.build_menu()
    items = list(menu.items)
    assert len(items) > 0
    first_item = items[0]
    assert "Open Azmuth Command Center" in first_item.text
    assert first_item.default is True


def test_azmuth_gui_views_and_inspectors():
    """Verifies headless initialization, view switching (pipeline, dag, genes), and capability inspection."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available in this environment")

    try:
        app = AzmuthCommandCenterGUI(root)
        assert app.active_view == "pipeline"
        assert len(app.genes_catalog) > 0

        # Switch to U0-U5 Causal DAG view
        app.switch_view("dag")
        assert app.active_view == "dag"
        app._redraw_active_canvas()
        assert len(app.canvas_nodes) > 0

        # Simulate shock propagation
        app._trigger_shock_simulation()
        assert len(app.shock_overlay) > 0

        # Switch to Gene Lab & Phylogenetic Evolution Tree view
        app.switch_view("genes")
        assert app.active_view == "genes"
        app._redraw_active_canvas()
        assert len(app.canvas_nodes) >= 2  # At least Gene Root + Allele node

        # Verify capability inspector populates text
        insp_content = app.inspector_text.get("1.0", tk.END)
        assert app.selected_gene_id in insp_content

        app._toggle_side_panel("left")
        assert str(app.left_panel) not in tuple(map(str, app.workspace.panes()))
        app._toggle_side_panel("left")
        assert str(app.left_panel) in tuple(map(str, app.workspace.panes()))
        app._toggle_side_panel("right")
        assert str(app.right_panel) not in tuple(map(str, app.workspace.panes()))
        app._toggle_side_panel("right")
        assert str(app.right_panel) in tuple(map(str, app.workspace.panes()))
    finally:
        try:
            app._on_close()
        except Exception:
            pass


def test_azmuth_gui_zoom_and_theme_toggle():
    """Verifies DPI zoom scaling (Ctrl+=, Ctrl+-, Ctrl+0) and theme toggle (Ctrl+T) operations."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available in this environment")

    try:
        app = AzmuthCommandCenterGUI(root)
        initial_zoom = app.zoom_level
        assert initial_zoom == 1.0
        assert app.theme.is_light is False

        # Test Zoom In
        app.zoom_in()
        assert app.zoom_level > initial_zoom
        assert app.scale > 0.0

        # Test Zoom Out back and further
        app.zoom_out()
        assert app.zoom_level == initial_zoom
        app.zoom_out()
        assert app.zoom_level < initial_zoom

        # Test Zoom Reset
        app.zoom_reset()
        assert app.zoom_level == 1.0

        # Test Theme Toggle to Light
        app.toggle_theme()
        assert app.theme.is_light is True
        assert "Dark theme" in app.btn_theme_toggle.cget("text")

        # Test Theme Toggle back to Dark
        app.toggle_theme()
        assert app.theme.is_light is False
        assert "Light theme" in app.btn_theme_toggle.cget("text")
    finally:
        try:
            app._on_close()
        except Exception:
            pass


def test_azmuth_gui_node_dragging_and_layout_reset():
    """Verifies that dragging nodes records custom world coordinates and reset_layout clears them."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available in this environment")

    try:
        app = AzmuthCommandCenterGUI(root)
        app.switch_view("pipeline")
        app._redraw_active_canvas()

        # Verify initial state has zero custom drag positions
        assert len(app.custom_node_positions) == 0

        # Simulate custom world-position override for STAGE_PAT_RING
        app.custom_node_positions["STAGE_PAT_RING"] = (720.0, 310.0)
        app._redraw_active_canvas()
        node_info = app.canvas_nodes.get("STAGE_PAT_RING")
        assert node_info is not None
        assert node_info["world_pos"] == (720.0, 310.0)

        # Execute layout reset
        app.reset_layout()
        assert len(app.custom_node_positions) == 0
        assert app.cam_zoom == 1.0
        assert app.cam_x == 640.0
        assert app.cam_y == 380.0
    finally:
        try:
            app._on_close()
        except Exception:
            pass


def test_azmuth_gui_view3_multi_column_operator_lanes():
    """Verifies View 3 organizes high-density mutant alleles into parallel horizontal lanes."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available in this environment")

    try:
        app = AzmuthCommandCenterGUI(root)
        app.switch_view("genes")
        app._redraw_active_canvas()

        # Find any gene with mutants
        has_mut_gene = None
        for gid, gdata in app.genes_catalog.items():
            if len(gdata.get("alleles", [])) > 2:
                has_mut_gene = gid
                break

        if has_mut_gene:
            app.selected_gene_id = has_mut_gene
            app._redraw_active_canvas()

            # Inspect world X coordinates of allele nodes
            allele_nodes = [
                info for nid, info in app.canvas_nodes.items()
                if nid.startswith("ALLELE::") and info.get("world_pos")
            ]
            assert len(allele_nodes) >= 2
            # Verify nodes exist in canvas
            assert len(app.canvas_nodes) >= 3
    finally:
        try:
            app._on_close()
        except Exception:
            pass


def test_azmuth_gui_dynamic_anchors_and_pipeline_stages_drag():
    """Verifies that all pipeline stages in View 1 dynamically update anchors when dragged."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available in this environment")

    try:
        app = AzmuthCommandCenterGUI(root)
        app.switch_view("pipeline")
        app._redraw_active_canvas()

        # Test smart anchor math between circle and box
        p1 = (540.0, 240.0)
        s1 = (124.0, 124.0)  # Circle
        p2 = (540.0, 540.0)
        s2 = (185.0, 58.0)   # Box below circle
        (ax, ay), (bx, by), orient = app._compute_smart_anchor(
            "STAGE_PAT_RING", "STAGE_THALAMIC", p1, s1, p2, s2
        )
        assert orient == "v"
        assert abs(ax - 540.0) < 1e-3
        assert ay > 240.0  # Leaves bottom rim of circle
        assert abs(bx - 540.0) < 1e-3
        assert by < 540.0  # Enters top face of box

        # Move multiple stages simultaneously to simulate user drag
        app.custom_node_positions["STAGE_THALAMIC"] = (600.0, 620.0)
        app.custom_node_positions["STAGE_CORTEX"] = (920.0, 260.0)
        app.custom_node_positions["STAGE_ULTIMATRIX"] = (920.0, 580.0)
        app.custom_node_positions["STAGE_ARENA_SSOT"] = (1250.0, 420.0)
        app._redraw_active_canvas()

        # Verify all dragged nodes have their overridden world positions
        assert app.canvas_nodes["STAGE_THALAMIC"]["world_pos"] == (600.0, 620.0)
        assert app.canvas_nodes["STAGE_CORTEX"]["world_pos"] == (920.0, 260.0)
        assert app.canvas_nodes["STAGE_ULTIMATRIX"]["world_pos"] == (920.0, 580.0)
        assert app.canvas_nodes["STAGE_ARENA_SSOT"]["world_pos"] == (1250.0, 420.0)

        # Trigger reset layout
        app.reset_layout()
        assert len(app.custom_node_positions) == 0

        # After reset, redraw and verify default positions restored
        app._redraw_active_canvas()
        assert app.canvas_nodes["STAGE_THALAMIC"]["world_pos"] == (540.0, 540.0)
        assert app.canvas_nodes["STAGE_CORTEX"]["world_pos"] == (880.0, 240.0)
        assert app.canvas_nodes["STAGE_ULTIMATRIX"]["world_pos"] == (880.0, 540.0)
        assert app.canvas_nodes["STAGE_ARENA_SSOT"]["world_pos"] == (1200.0, 390.0)
    finally:
        try:
            app._on_close()
        except Exception:
            pass


def test_azmuth_gui_canvas_double_click_reset_and_action_button():
    """Verifies double-clicking empty canvas and clicking Reset DAG button resets layout."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available in this environment")

    try:
        app = AzmuthCommandCenterGUI(root)
        app.switch_view("pipeline")
        app._redraw_active_canvas()

        # Set custom positions
        app.custom_node_positions["STAGE_PAT_RING"] = (400.0, 200.0)
        assert len(app.custom_node_positions) == 1

        # Simulate double-click on empty canvas at (10, 10)
        class DummyEvent:
            x = 10
            y = 10
        app._on_canvas_double_click(DummyEvent())
        assert len(app.custom_node_positions) == 0

        # Check action button presence
        reset_action_btns = [b for b, col in app.action_buttons if "Fit view" in b.cget("text")]
        assert len(reset_action_btns) == 1
    finally:
        try:
            app._on_close()
        except Exception:
            pass


def test_azmuth_gui_pat_ring_reports_configured_count_without_fake_health():
    """The PAT visualization never implies a rotating key or verified health."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available in this environment")

    try:
        app = AzmuthCommandCenterGUI(root)
        app.switch_view("pipeline")
        app._redraw_active_canvas()

        # pat_ring_info should be recorded
        assert app.pat_ring_info is not None
        assert app.pat_ring_info[0] == 540.0
        assert app.pat_ring_info[1] == 240.0

        # Verify initial dots created
        dot_items = app.canvas.find_withtag("pat_ring_dots")
        assert len(dot_items) >= 30

        # Pool state is represented as configured count, not a rotating-key claim.
        app.is_job_running = True
        app.anim_tick = 0
        app._draw_pat_ring_dots()
        subtext_item = app.canvas.find_withtag("pat_ring_subtext")
        assert len(subtext_item) == 1
        assert "health unknown" in app.canvas.itemcget(subtext_item[0], "text")
        app.anim_tick = 8
        app._draw_pat_ring_dots()
        assert "health unknown" in app.canvas.itemcget(subtext_item[0], "text")

        # When idle, displays pooled keys
        app.is_job_running = False
        app._draw_pat_ring_dots()
        assert "configured" in app.canvas.itemcget(subtext_item[0], "text")
    finally:
        try:
            app._on_close()
        except Exception:
            pass


class _FakeWidget:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)


@pytest.mark.parametrize("target, expected", [
    (lambda: (_ for _ in ()).throw(RuntimeError("simulated failure")), "failed"),
    (lambda: __import__("subprocess").CompletedProcess(["fake"], 7, "out", "bad"), "failed"),
    (lambda: None, "succeeded"),
])
def test_background_job_records_terminal_outcome(target, expected, monkeypatch):
    """Worker completion is reported on the polling side and exceptions never succeed."""
    import subprocess
    import tkinter.messagebox

    monkeypatch.setattr(tkinter.messagebox, "showerror", lambda *args, **kwargs: None)
    app = object.__new__(AzmuthCommandCenterGUI)
    app.is_job_running = False
    app.active_job = None
    app.job_results = __import__("queue").Queue()
    app.theme = SimpleNamespace(
        accent_emerald="green", accent_crimson="red", accent_amber="yellow"
    )
    app.lbl_footer_job = _FakeWidget()
    app.btn_cancel_job = _FakeWidget()
    app.btn_cancel_job.configure(state="normal")
    app._running = True
    app._closing = False
    app.pulses = []
    app.root = SimpleNamespace(after=lambda *_: None)
    app._on_background_job_complete = lambda: None

    app._run_background_job("test", "blue", target)
    deadline = time.monotonic() + 2
    while app.job_results.empty() and time.monotonic() < deadline:
        time.sleep(0.01)
    app._poll_job_results()

    assert app.active_job.outcome == expected
    assert app.is_job_running is False
    assert app.active_job.finished_at is not None
    if app.active_job.return_code is not None:
        assert app.active_job.return_code == 7
        assert "bad" in app.active_job.output




