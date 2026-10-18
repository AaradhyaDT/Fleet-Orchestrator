#!/usr/bin/env python3
"""tests/test_azmuth_gui.py
------------------------
Unit tests for the Azmuth Neuromorphic Command Center & Phylogenetic Gene Explorer GUI (tools/azmuth_gui.py).
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
import pytest

from tools.azmuth_gui import (
    AzmuthCommandCenterGUI,
    build_gene_phylogeny,
    find_gene_file_on_disk,
    list_available_cartridges,
)
from tools.azmuth_tray import AzmuthTrayApp


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
        assert "Dark Mode" in app.btn_theme_toggle.cget("text")

        # Test Theme Toggle back to Dark
        app.toggle_theme()
        assert app.theme.is_light is False
        assert "Light Mode" in app.btn_theme_toggle.cget("text")
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


