#!/usr/bin/env python3
"""tools/azmuth_gui.py
---------------------
Azmuth Autonomous Neuromorphic Command Center & Phylogenetic Gene Explorer.

High-agency desktop command center with:
1. Dynamic Resolution & DPI Auto-Scaling with Interactive Zoom:
   - Ctrl + = / Ctrl + + : Zoom In
   - Ctrl + - / Ctrl + _ : Zoom Out
   - Ctrl + 0            : Reset Zoom to Default (100%)
   - Ctrl + MouseWheel   : Smooth Canvas Zooming
2. Dynamic Dark / Light Theme Switching (Ctrl + T or Header Toggle):
   - Seamlessly switches full window palette, canvas grid, code inspector, and Windows 11 titlebar.
3. Unified Mission Control Layout:
   - Top Telemetry Bar: Live Gear Switcher, 60FPS RAM Oscilloscope Sparkline with Circuit Breaker line,
     30-PAT Ring indicator, live Thalamic |Z|-score threshold tuner, zoom controls, and theme toggle.
4. Switchable 60FPS Graph & Flow Canvases:
   - [1] End-to-End Pipeline & PAT Flow: Sensory streams -> 30-PAT ring -> Thalamic sieve -> Cortex -> Gene Sequencer -> SSOT.
   - [2] U0-U5 Neuromorphic Causal DAG: Swappable cortical cartridges, homeostatic node colors, axonal synapses,
         Egocentric First-Person View (FPV), and Multi-Hop Shock propagation (+2.0σ).
   - [3] Phylogenetic Gene Evolution Tree & Allele Arena: 349+ genes across Tiers 0-5, branching Wild-Type ->
         Mutator Edge (+fast_io, +pragma_tuning, +static_memory, +bitwise_unrolling, +python_stdlib_accel) ->
         Mutated Daughter Allele -> Arena PRIMARY Champion, with live "Mutate & Race Now" execution.
5. Interactive Capability & Code Diff Inspector:
   - Big-O Time/Space bounds, Environmental Triggers, Mathematical Invariants, Empirical Fitness comparison bars,
     and syntax-highlighted code template viewer.
"""

from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# Anchor repository root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Protect stdio under pythonw.exe and hide console if started via python.exe
if sys.platform == "win32":
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    try:
        _hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
        if _hwnd_console:
            ctypes.windll.user32.ShowWindow(_hwnd_console, 0)
    except Exception:
        pass

import tkinter as tk
from tkinter import font as tkFont
from tkinter import ttk

from tools.azmuth_daemon import (
    GEARS,
    check_and_enforce_gear_safety,
    execute_cycle,
    get_current_gear,
    get_memory_status_gb,
    get_windows_idle_seconds,
    is_paused,
    set_current_gear,
    set_paused,
)
from tools.azmuth_corpus_harvester import CORPUS_LEDGER, harvest_single_task
from tools.azmuth_github_sensor import AzmuthGitHubSensor, BRIEF_FILE as GH_BRIEF_FILE, CACHE_FILE as GH_CACHE_FILE
from tools.azmuth_macro_graph import (
    CorticalCartridgeLoader,
    DEFAULT_CARTRIDGE_DIR,
    ForesightAlphaEngine,
    HomeostaticBaselineNormalizer,
    PreContactAvoidanceGate,
    SpikingMacroGraph,
)
from tools.ultimatrix_mutator import CODON_STREAM, MUTATION_LEDGER, load_mutation_ledger, mutate_gene_file
from tools.ultimatrix_splicer import load_all_genes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AzmuthGUI] %(message)s",
)
logger = logging.getLogger("azmuth_gui")

# --- Paths ---
STATE_DIR = ROOT / "orchestrator-state"
ARENA_LEDGER = STATE_DIR / "ultimatrix_arena_ledger.json"
MACRO_BRIEF_JSON = STATE_DIR / "macro_foresight_brief.json"
SWEEP_JSON = STATE_DIR / "macro_foresight_sweep.json"
INGESTION_FEED = STATE_DIR / "azmuth_ingestion_feed.jsonl"
RUN_LOG_JSON = STATE_DIR / "azmuth_run.json"


# ============================================================================
# Dynamic Theme Engine (Dark & Light)
# ============================================================================

class GUITheme:
    """Encapsulates color palette tokens for Dark and Light modes."""

    def __init__(self, is_light: bool = False):
        self.is_light = is_light
        if is_light:
            self.bg_void = "#f8fafc"
            self.bg_main = "#f1f5f9"
            self.bg_panel = "#ffffff"
            self.bg_card = "#f8fafc"
            self.bg_card_hover = "#e2e8f0"
            self.bg_input = "#ffffff"
            self.border_subtle = "#e2e8f0"
            self.border_active = "#cbd5e1"
            self.text_primary = "#0f172a"
            self.text_secondary = "#334155"
            self.text_muted = "#64748b"
            self.grid_line = "#e2e8f0"
            self.code_bg = "#f1f5f9"
            self.code_fg = "#0f172a"
            self.code_diff_bg = "#dcfce7"
            self.code_diff_fg = "#15803d"
            self.accent_cyan = "#0284c7"
            self.accent_blue = "#2563eb"
            self.accent_emerald = "#059669"
            self.accent_amber = "#d97706"
            self.accent_crimson = "#dc2626"
            self.accent_indigo = "#4f46e5"
            self.accent_purple = self.accent_indigo
            self.accent_gold = "#b45309"
        else:
            self.bg_void = "#090b0e"
            self.bg_main = "#0d0f14"
            self.bg_panel = "#12151c"
            self.bg_card = "#171b24"
            self.bg_card_hover = "#1e2430"
            self.bg_input = "#0f1218"
            self.border_subtle = "#222834"
            self.border_active = "#384152"
            self.text_primary = "#f3f4f6"
            self.text_secondary = "#cbd5e1"
            self.text_muted = "#64748b"
            self.grid_line = "#0e1218"
            self.code_bg = "#0b0e14"
            self.code_fg = "#e2e8f0"
            self.code_diff_bg = "#062e1e"
            self.code_diff_fg = "#4ade80"
            self.accent_cyan = "#06b6d4"
            self.accent_blue = "#3b82f6"
            self.accent_emerald = "#10b981"
            self.accent_amber = "#f59e0b"
            self.accent_crimson = "#ef4444"
            self.accent_indigo = "#6366f1"
            self.accent_purple = self.accent_indigo
            self.accent_gold = "#eab308"

        self.tier_colors = {
            0: "#f43f5e",  # T0 Hardware Substrate
            1: self.accent_amber,  # T1 Language Runtime
            2: self.accent_cyan,   # T2 Primitives
            3: self.accent_indigo, # T3 Cubic Breakers
            4: self.accent_emerald,# T4 Symbolic Frontier
            5: self.accent_gold,   # T5 Super-Domain Foresight
        }


TIER_NAMES = {
    0: "T0: Hardware Substrate",
    1: "T1: Language Runtime",
    2: "T2: Primitives & Structures",
    3: "T3: Dimensional / Cubic Breakers",
    4: "T4: Symbolic & CAS Frontier",
    5: "T5: Super-Domain Foresight",
}

ZOOM_LEVELS = [0.65, 0.75, 0.85, 1.0, 1.15, 1.30, 1.50, 1.75, 2.0, 2.25]


# ============================================================================
# Win32 DPI & Desktop Attachment Helpers
# ============================================================================

def attach_default_desktop() -> bool:
    """Attach the calling thread to the interactive 'Default' desktop in WinSta0."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_def:
            user32.SetThreadDesktop(h_def)
            user32.CloseDesktop(h_def)
            return True
    except Exception:
        pass
    return False


def get_system_dpi_scale() -> float:
    """Detects native display scaling (e.g. 1.0, 1.25, 1.5, 2.0)."""
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            dpi = user32.GetDpiForSystem()
            if dpi and dpi > 0:
                return max(1.0, round(dpi / 96.0, 2))
        except Exception:
            pass
    return 1.0


def set_window_dark_mode(root: tk.Tk, is_dark: bool) -> None:
    """Sets the Windows 11/10 titlebar to light or dark mode."""
    if sys.platform != "win32":
        return
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()
        val = ctypes.c_int(1 if is_dark else 0)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)
            )
    except Exception:
        pass


def enable_win32_dpi_and_dark_bar(root: Optional[tk.Tk] = None, is_dark: bool = True) -> None:
    """Enables Windows 11/10 Per-Monitor High-DPI awareness and dark title bar."""
    if sys.platform != "win32":
        return
    attach_default_desktop()
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    if root is not None:
        set_window_dark_mode(root, is_dark)


# ============================================================================
# Pure Data & Lineage Builders (Testable Headlessly)
# ============================================================================

def build_gene_phylogeny(gene_data: Dict[str, Any]) -> Dict[str, Any]:
    """Constructs a structured Two-Level Phylogenetic Evolution Tree from a gene dictionary."""
    gene_id = gene_data.get("gene_id", "UNKNOWN_GENE")
    tier = int(gene_data.get("tier", 2))
    category = gene_data.get("category", "primitive_structure")
    description = gene_data.get("description", "")
    alleles = gene_data.get("alleles", [])

    wild_types: List[Dict[str, Any]] = []
    mutants: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    allele_map: Dict[str, Dict[str, Any]] = {}

    for a in alleles:
        aid = a.get("allele_id", "unknown")
        allele_map[aid] = a
        if "_mut_" in aid:
            mutants.append(a)
        else:
            wild_types.append(a)

    if not wild_types and alleles:
        wild_types.append(alleles[0])
        mutants = alleles[1:]

    for m in mutants:
        mid = m.get("allele_id", "")
        parent_id, op_name = mid.split("_mut_", 1)
        if parent_id not in allele_map and wild_types:
            parent_id = wild_types[0].get("allele_id", "")

        parent_rt = float(allele_map.get(parent_id, {}).get("empirical_fitness", {}).get("runtime_ms", 50.0))
        mut_rt = float(m.get("empirical_fitness", {}).get("runtime_ms", 50.0))
        speedup_pct = 0.0
        if parent_rt > 0:
            speedup_pct = round(((parent_rt - mut_rt) / parent_rt) * 100.0, 1)

        edges.append({
            "source_allele": parent_id,
            "target_allele": mid,
            "operator": op_name,
            "speedup_pct": speedup_pct,
            "promoted_to_primary": m.get("dominance") == "PRIMARY",
        })

    champion = None
    for a in alleles:
        if a.get("dominance") == "PRIMARY":
            champion = a
            break
    if not champion and alleles:
        champion = min(
            alleles,
            key=lambda x: float(x.get("empirical_fitness", {}).get("runtime_ms", 9999.0)),
        )

    base_rts = [
        float(w.get("empirical_fitness", {}).get("runtime_ms", 50.0))
        for w in wild_types
        if w.get("empirical_fitness", {}).get("runtime_ms") is not None
    ]
    champ_rt = float(champion.get("empirical_fitness", {}).get("runtime_ms", 50.0)) if champion else 50.0
    baseline_rt = max(base_rts) if base_rts else champ_rt
    net_speedup_pct = round(((baseline_rt - champ_rt) / baseline_rt) * 100.0, 1) if baseline_rt > 0 else 0.0

    return {
        "gene_id": gene_id,
        "tier": tier,
        "tier_label": TIER_NAMES.get(tier, f"T{tier}"),
        "category": category,
        "description": description,
        "wild_types": wild_types,
        "mutants": mutants,
        "edges": edges,
        "champion": champion,
        "total_alleles": len(alleles),
        "net_speedup_pct": max(0.0, net_speedup_pct),
    }


def find_gene_file_on_disk(gene_id: str) -> Optional[Path]:
    """Locates the JSON file for a given gene_id inside CODON_STREAM."""
    if not CODON_STREAM.exists():
        return None
    target_lower = gene_id.lower()
    for tier_dir in CODON_STREAM.iterdir():
        if tier_dir.is_dir() and tier_dir.name.startswith("tier"):
            for f in tier_dir.glob("*.json"):
                if f.stem.lower() == target_lower or target_lower in f.stem.lower():
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        if data.get("gene_id") == gene_id:
                            return f
                    except Exception:
                        pass
    return None


def list_available_cartridges() -> List[Dict[str, Any]]:
    """Lists all cortical cartridges (U0..U5) available in DEFAULT_CARTRIDGE_DIR."""
    results: List[Dict[str, Any]] = []
    if not DEFAULT_CARTRIDGE_DIR.exists():
        return results
    for f in sorted(DEFAULT_CARTRIDGE_DIR.glob("u*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "stem": f.stem,
                "path": f,
                "universe_id": data.get("universe_id", f.stem.upper()),
                "cortical_lobe": data.get("cortical_lobe", f.stem),
                "node_count": len(data.get("nodes", [])),
                "synapse_count": len(data.get("synapses", [])),
            })
        except Exception:
            pass
    return results


# ============================================================================
# Main GUI Application with Zoom & Light Theme
# ============================================================================

class AzmuthCommandCenterGUI:
    """Industry-Grade Native Desktop Command Center & Visual Flow Graph for Azmuth."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Azmuth Autonomous Neuromorphic Command Center — Foresight & Ultimatrix Gene Lab")

        # 1. Scaling & Resolution Setup
        self.system_dpi: float = get_system_dpi_scale()
        self.zoom_idx: int = 3  # default 1.0x in ZOOM_LEVELS
        self.zoom_level: float = ZOOM_LEVELS[self.zoom_idx]
        self.theme: GUITheme = GUITheme(is_light=False)

        # Base window geometry adapted to system DPI
        base_w = int(1440 * self.system_dpi)
        base_h = int(880 * self.system_dpi)
        self.root.geometry(f"{min(base_w, 1920)}x{min(base_h, 1080)}")
        self.root.minsize(980, 620)
        self.root.configure(bg=self.theme.bg_main)

        enable_win32_dpi_and_dark_bar(self.root, is_dark=not self.theme.is_light)

        # 2. Runtime State & Tunable Parameters
        self.active_view: str = "pipeline"  # "pipeline" | "dag" | "genes"
        self.thalamic_z_threshold: tk.DoubleVar = tk.DoubleVar(value=0.80)
        self.ram_circuit_limit_gb: tk.DoubleVar = tk.DoubleVar(value=3.00)
        self.search_query_var: tk.StringVar = tk.StringVar(value="")
        self.selected_tier_filter: int = -1  # -1 = All Tiers

        # 3. Live Telemetry Buffers
        self.ram_history: List[float] = [50.0] * 80
        self.avail_gb_history: List[float] = [8.0] * 80
        self.active_job_label: str = "IDLE — Monitoring Telemetry"
        self.is_job_running: bool = False

        # 4. Animation & Canvas State
        self.anim_tick: int = 0
        self.pulses: List[Dict[str, Any]] = []
        self.canvas_nodes: Dict[str, Dict[str, Any]] = {}
        self.selected_node_id: Optional[str] = None

        # 4b. Virtual Camera & Canvas Viewport Transform
        self.cam_x: float = 640.0   # World center X
        self.cam_y: float = 380.0   # World center Y
        self.cam_zoom: float = 1.0  # Camera magnification (0.5x to 2.5x)
        self.pan_start: Optional[Tuple[float, float]] = None
        self.is_panning: bool = False
        self.press_pos: Tuple[float, float] = (0.0, 0.0)
        self.action_buttons: List[Tuple[tk.Button, str]] = []

        # 4c. Interactive Node Dragging & Session Layout
        self.custom_node_positions: Dict[str, Tuple[float, float]] = {}
        self.dragged_node_id: Optional[str] = None
        self.is_node_dragging: bool = False
        self.node_drag_start_world: Optional[Tuple[float, float]] = None

        # 5. Cached Subsystems Data
        self.gh_sensor = AzmuthGitHubSensor()
        self.gh_cache_data: Dict[str, Any] = {}
        self.cartridges: List[Dict[str, Any]] = list_available_cartridges()
        self.current_cartridge_idx: int = 0
        self.current_macro_graph: Optional[SpikingMacroGraph] = None
        self.current_cartridge_raw: Dict[str, Any] = {}
        self.shock_overlay: Dict[str, float] = {}

        self.genes_catalog: Dict[str, Dict[str, Any]] = {}
        self.selected_gene_id: Optional[str] = None
        self.selected_allele_id: Optional[str] = None
        self.arena_ledger_data: Dict[str, Any] = {}
        self.mutation_ledger_data: Dict[str, Any] = {}
        self.corpus_ledger_data: Dict[str, Any] = {}

        # Load initial telemetry
        self._reload_all_telemetry()

        # Build UI Components
        self._configure_ttk_styles()
        self._build_top_telemetry_bar()
        self._build_tuning_and_action_bar()
        self._build_main_workspace()
        self._build_status_footer()

        # Bind Keybindings for Zoom & Theme
        self._bind_zoom_and_theme_shortcuts()

        # Populate initial view
        self.switch_view("pipeline")

        # 60FPS Canvas Animation Loop & 2s Telemetry Poller
        self._running = True
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_animation_frame()
        self._schedule_telemetry_poll()

    # ------------------------------------------------------------------------
    # Dynamic Scaling & Font Helpers
    # ------------------------------------------------------------------------

    @property
    def scale(self) -> float:
        """Returns effective scaling factor combining display DPI and camera zoom."""
        return max(0.5, round(self.system_dpi * self.cam_zoom, 2))

    def s(self, px: float) -> int:
        """Scales a pixel dimension by camera zoom."""
        return max(1, int(round(px * self.cam_zoom)))

    def font(self, family: str = "Segoe UI", base_pt: int = 9, weight: str = "normal") -> tuple:
        """Returns a system-DPI scaled font specification for UI chrome."""
        scaled_pt = max(7, int(round(base_pt * self.system_dpi)))
        return (family, scaled_pt, weight) if weight != "normal" else (family, scaled_pt)

    def w2s(self, wx: float, wy: float, cw: float, ch: float) -> Tuple[float, float]:
        """Transforms logical World coordinates to screen Canvas pixels."""
        sx = (wx - self.cam_x) * self.cam_zoom + cw / 2.0
        sy = (wy - self.cam_y) * self.cam_zoom + ch / 2.0
        return sx, sy

    def s2w(self, sx: float, sy: float, cw: float, ch: float) -> Tuple[float, float]:
        """Transforms screen Canvas pixels to logical World coordinates."""
        wx = (sx - cw / 2.0) / max(0.01, self.cam_zoom) + self.cam_x
        wy = (sy - ch / 2.0) / max(0.01, self.cam_zoom) + self.cam_y
        return wx, wy

    # ------------------------------------------------------------------------
    # Zoom Controls & Keyboard Shortcuts
    # ------------------------------------------------------------------------

    def _bind_zoom_and_theme_shortcuts(self) -> None:
        # Zoom In: Ctrl + = / Ctrl + + / Ctrl + NumpadAdd
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-KP_Add>", lambda e: self.zoom_in())

        # Zoom Out: Ctrl + - / Ctrl + _ / Ctrl + NumpadSubtract
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-underscore>", lambda e: self.zoom_out())
        self.root.bind("<Control-KP_Subtract>", lambda e: self.zoom_out())

        # Reset Zoom: Ctrl + 0 / Ctrl + Numpad0
        self.root.bind("<Control-Key-0>", lambda e: self.zoom_reset())
        self.root.bind("<Control-KP_0>", lambda e: self.zoom_reset())

        # Theme Toggle: Ctrl + T
        self.root.bind("<Control-t>", lambda e: self.toggle_theme())
        self.root.bind("<Control-T>", lambda e: self.toggle_theme())

        # Reset / Refresh DAG Layout: Ctrl + R / F5
        self.root.bind("<Control-r>", lambda e: self.reset_layout())
        self.root.bind("<Control-R>", lambda e: self.reset_layout())
        self.root.bind("<F5>", lambda e: self.reset_layout())

        # MouseWheel Zooming with Control held down
        self.root.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)

    def _on_ctrl_mousewheel(self, event: Any) -> None:
        if event.delta > 0:
            self.zoom_in()
        elif event.delta < 0:
            self.zoom_out()

    def zoom_in(self) -> None:
        if self.zoom_idx < len(ZOOM_LEVELS) - 1:
            self.zoom_idx += 1
            self.zoom_level = ZOOM_LEVELS[self.zoom_idx]
            self.cam_zoom = self.zoom_level
            self._apply_zoom_and_layout()

    def zoom_out(self) -> None:
        if self.zoom_idx > 0:
            self.zoom_idx -= 1
            self.zoom_level = ZOOM_LEVELS[self.zoom_idx]
            self.cam_zoom = self.zoom_level
            self._apply_zoom_and_layout()

    def zoom_reset(self) -> None:
        self.zoom_idx = ZOOM_LEVELS.index(1.0) if 1.0 in ZOOM_LEVELS else 3
        self.zoom_level = ZOOM_LEVELS[self.zoom_idx]
        self.cam_zoom = self.zoom_level
        self.cam_x = 640.0
        self.cam_y = 380.0
        self._apply_zoom_and_layout()

    def reset_layout(self) -> None:
        """Clears user manual node dragging offsets and restores default camera view and DAG render."""
        self.custom_node_positions.clear()
        self.dragged_node_id = None
        self.is_node_dragging = False
        self.pan_start = None
        self.is_panning = False
        self.zoom_reset()
        if hasattr(self, "lbl_footer_job"):
            self.lbl_footer_job.configure(
                text="● Status: DAG layout reset to default schematic render",
                fg=self.theme.accent_cyan,
            )
        self._spawn_pulse_wave(color=self.theme.accent_cyan, count=6)

    def _apply_zoom_and_layout(self) -> None:
        """Refreshes layout widths, widget font sizes, and canvas nodes for current zoom level."""
        self.cam_zoom = self.zoom_level
        pct_str = f"{int(self.zoom_level * 100)}%"
        self.btn_zoom_reset.configure(text=pct_str)
        self.lbl_footer_zoom.configure(text=f"Zoom: {pct_str} (Ctrl+= / Ctrl+- / Ctrl+0)")

        # Proportional Viewport Clamping (Guarantees >= 50% width for central canvas)
        win_w = max(1000, self.root.winfo_width())
        left_w = min(int(win_w * 0.22), max(220, int(260 * self.system_dpi)))
        right_w = min(int(win_w * 0.28), max(280, int(340 * self.system_dpi)))
        self.left_panel.configure(width=left_w)
        self.right_panel.configure(width=right_w)

        # Update font on core labels
        self.lbl_title.configure(font=self.font("Segoe UI Semibold", 11))
        self.lbl_engine_sub.configure(font=self.font("Segoe UI", 8))
        self.left_header_lbl.configure(font=self.font("Segoe UI Semibold", 9))
        self.right_title_lbl.configure(font=self.font("Segoe UI Semibold", 9))
        self.lbl_canvas_mode.configure(font=self.font("Segoe UI Semibold", 9))
        self.lbl_canvas_hint.configure(font=self.font("Segoe UI", 8))
        self.inspector_text.configure(font=self.font("Consolas", 9))
        self.left_listbox.configure(font=self.font("Consolas", 8))

        # Re-render canvas
        self._redraw_active_canvas()

    # ------------------------------------------------------------------------
    # Theme Toggling (Dark / Light)
    # ------------------------------------------------------------------------

    def toggle_theme(self) -> None:
        """Toggles between Dark and Light mode, updating colors and Windows 11 titlebar."""
        self.theme = GUITheme(is_light=not self.theme.is_light)
        set_window_dark_mode(self.root, is_dark=not self.theme.is_light)
        self.btn_theme_toggle.configure(
            text="☾ Dark Mode" if self.theme.is_light else "☼ Light Mode",
            bg=self.theme.bg_card,
            fg=self.theme.text_primary,
        )
        self._apply_theme_colors()
        self._redraw_active_canvas()

    def _apply_theme_colors(self) -> None:
        t = self.theme
        self.root.configure(bg=t.bg_main)
        self.top_header.configure(bg=t.bg_panel, highlightbackground=t.border_subtle)
        self.brand_frame.configure(bg=t.bg_panel)
        self.title_row.configure(bg=t.bg_panel)
        self.status_dot.configure(bg=t.bg_panel)
        self.lbl_title.configure(bg=t.bg_panel, fg=t.text_primary)
        self.lbl_engine_sub.configure(bg=t.bg_panel, fg=t.text_muted)

        self.gear_frame.configure(bg=t.bg_panel)
        self.btn_row.configure(bg=t.bg_panel)
        self.lbl_gear_hdr.configure(bg=t.bg_panel, fg=t.text_muted)

        self.osc_frame.configure(bg=t.bg_panel)
        self.osc_top.configure(bg=t.bg_panel)
        self.lbl_osc_hdr.configure(bg=t.bg_panel, fg=t.text_muted)
        self.lbl_ram_readout.configure(bg=t.bg_panel)
        self.osc_canvas.configure(bg=t.bg_void, highlightbackground=t.border_subtle)

        self.kpi_container.configure(bg=t.bg_panel)
        for card in self.kpi_cards:
            card.configure(bg=t.bg_card, highlightbackground=t.border_subtle)
        for lbl_t in self.kpi_title_lbls:
            lbl_t.configure(bg=t.bg_card, fg=t.text_muted)
        for lbl_v in self.kpi_labels.values():
            lbl_v.configure(bg=t.bg_card)

        self.bar.configure(bg=t.bg_card, highlightbackground=t.border_subtle)
        self.view_frame.configure(bg=t.bg_card)
        self.tune_frame.configure(bg=t.bg_card)
        self.act_frame.configure(bg=t.bg_card)
        self.lbl_tune_z.configure(bg=t.bg_card, fg=t.text_secondary)
        self.lbl_tune_ram.configure(bg=t.bg_card, fg=t.text_secondary)
        self.spin_z.configure(bg=t.bg_input, fg=t.accent_cyan, buttonbackground=t.bg_panel)
        self.spin_ram.configure(bg=t.bg_input, fg=t.accent_amber, buttonbackground=t.bg_panel)

        self.left_panel.configure(bg=t.bg_panel, highlightbackground=t.border_subtle)
        self.left_header_lbl.configure(bg=t.bg_card, fg=t.text_primary)
        self.left_filter_frame.configure(bg=t.bg_panel)
        self.search_entry.configure(bg=t.bg_input, fg=t.text_primary, insertbackground=t.accent_cyan)
        self.tier_filter_row.configure(bg=t.bg_panel)
        self.left_listbox.configure(
            bg=t.bg_void,
            fg=t.text_secondary,
            selectbackground=t.accent_blue,
            selectforeground=t.text_primary,
            highlightbackground=t.border_subtle,
        )

        self.right_panel.configure(bg=t.bg_panel, highlightbackground=t.border_subtle)
        self.right_hdr.configure(bg=t.bg_card)
        self.right_title_lbl.configure(bg=t.bg_card, fg=t.text_primary)
        self.cap_summary_frame.configure(bg=t.bg_panel)
        self.inspector_text.configure(
            bg=t.bg_void,
            fg=t.text_secondary,
            highlightbackground=t.border_subtle,
        )
        self.canvas_bar.configure(bg=t.bg_main)
        self.lbl_canvas_hint.configure(bg=t.bg_main, fg=t.text_muted)
        self.canvas.configure(bg=t.bg_void)

        self.footer.configure(bg=t.bg_panel, highlightbackground=t.border_subtle)
        self.lbl_footer_right.configure(bg=t.bg_panel, fg=t.text_muted)
        self.lbl_footer_zoom.configure(bg=t.bg_panel, fg=t.text_muted)
        self.lbl_footer_job.configure(bg=t.bg_panel)

        # Header Zoom and Theme Controls Re-theming
        if hasattr(self, "ctrl_header_frame"):
            self.ctrl_header_frame.configure(bg=t.bg_panel)
            self.zoom_row.configure(bg=t.bg_panel)
            self.btn_zoom_out.configure(bg=t.bg_card, fg=t.text_primary)
            self.btn_zoom_reset.configure(bg=t.bg_card, fg=t.accent_cyan)
            self.btn_zoom_in.configure(bg=t.bg_card, fg=t.text_primary)
            self.btn_theme_toggle.configure(bg=t.bg_card, fg=t.text_primary)

        # Action Buttons Re-theming (Eliminate black box artifacts in light mode)
        for b, color in self.action_buttons:
            b.configure(
                bg=t.bg_panel,
                fg=color,
                highlightbackground=color,
                activebackground=color,
                activeforeground=t.bg_void,
            )

        # Daemon Gear Controls Re-theming
        for g_k, g_b in self.gear_buttons.items():
            g_b.configure(bg=t.bg_card, fg=t.text_secondary)
        if hasattr(self, "btn_pause"):
            self.btn_pause.configure(bg=t.bg_card, fg=t.text_secondary)
        self._refresh_header_indicators()

        # View Buttons Re-theming
        for v_id, v_btn in self.view_buttons.items():
            if v_id == self.active_view:
                v_btn.configure(bg=t.accent_blue, fg=t.text_primary)
            else:
                v_btn.configure(bg=t.bg_panel, fg=t.text_secondary)

        self.lbl_canvas_mode.configure(bg=t.bg_main)
        if hasattr(self, "canvas_bar"):
            self.canvas_bar.configure(bg=t.bg_main)
        if hasattr(self, "lbl_canvas_hint"):
            self.lbl_canvas_hint.configure(bg=t.bg_main, fg=t.text_muted)
        if hasattr(self, "btn_reset_layout"):
            self.btn_reset_layout.configure(
                bg=t.bg_panel,
                fg=t.accent_cyan,
                activebackground=t.accent_cyan,
                activeforeground=t.bg_void,
            )

        # Update text syntax highlight tags
        self.inspector_text.tag_configure("h1", font=self.font("Segoe UI Semibold", 10), foreground=t.text_primary)
        self.inspector_text.tag_configure("h2", font=self.font("Segoe UI Semibold", 9), foreground=t.accent_cyan)
        self.inspector_text.tag_configure("gold", foreground=t.accent_gold, font=self.font("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("emerald", foreground=t.accent_emerald, font=self.font("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("crimson", foreground=t.accent_crimson, font=self.font("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("purple", foreground=t.accent_purple, font=self.font("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("muted", foreground=t.text_muted)
        self.inspector_text.tag_configure("mutation_add", foreground=t.code_diff_fg, background=t.code_diff_bg)
        self.inspector_text.tag_configure("code", foreground=t.code_fg, background=t.code_bg)

        self._refresh_header_indicators()

    # ------------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------------

    def _reload_all_telemetry(self) -> None:
        if GH_CACHE_FILE.exists():
            try:
                self.gh_cache_data = json.loads(GH_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.gh_cache_data = {}

        if CORPUS_LEDGER.exists():
            try:
                self.corpus_ledger_data = json.loads(CORPUS_LEDGER.read_text(encoding="utf-8"))
            except Exception:
                pass
        if ARENA_LEDGER.exists():
            try:
                self.arena_ledger_data = json.loads(ARENA_LEDGER.read_text(encoding="utf-8"))
            except Exception:
                pass
        self.mutation_ledger_data = load_mutation_ledger()

        self._load_selected_cartridge()

        try:
            self.genes_catalog = load_all_genes()
            if not self.selected_gene_id and self.genes_catalog:
                for gid, gdata in self.genes_catalog.items():
                    if any("_mut_" in a.get("allele_id", "") for a in gdata.get("alleles", [])):
                        self.selected_gene_id = gid
                        break
                if not self.selected_gene_id:
                    self.selected_gene_id = sorted(self.genes_catalog.keys())[0]
        except Exception as e:
            logger.debug(f"Error loading genes: {e}")

    def _load_selected_cartridge(self) -> None:
        if not self.cartridges:
            return
        idx = min(max(self.current_cartridge_idx, 0), len(self.cartridges) - 1)
        c_info = self.cartridges[idx]
        try:
            self.current_cartridge_raw = CorticalCartridgeLoader.load_cartridge(c_info["path"])
            z_thresh = float(self.thalamic_z_threshold.get())
            self.current_macro_graph = SpikingMacroGraph(
                self.current_cartridge_raw.get("nodes", []),
                self.current_cartridge_raw.get("synapses", []),
                habituate_threshold=z_thresh,
            )
        except Exception as e:
            logger.debug(f"Failed loading cartridge: {e}")

    # ------------------------------------------------------------------------
    # UI Building
    # ------------------------------------------------------------------------

    def _configure_ttk_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Vertical.TScrollbar",
            background=self.theme.bg_card,
            troughcolor=self.theme.bg_panel,
            bordercolor=self.theme.bg_panel,
            arrowcolor=self.theme.text_muted,
        )

    def _build_top_telemetry_bar(self) -> None:
        t = self.theme
        self.top_header = tk.Frame(self.root, bg=t.bg_panel, highlightthickness=1, highlightbackground=t.border_subtle)
        self.top_header.pack(fill=tk.X, side=tk.TOP)

        # 1. Brand & Engine Status
        self.brand_frame = tk.Frame(self.top_header, bg=t.bg_panel, padx=12, pady=8)
        self.brand_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.title_row = tk.Frame(self.brand_frame, bg=t.bg_panel)
        self.title_row.pack(anchor="w")

        self.status_dot = tk.Canvas(self.title_row, width=12, height=12, bg=t.bg_panel, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.status_dot.create_oval(2, 2, 10, 10, fill=t.accent_emerald, outline="", tags="dot")

        self.lbl_title = tk.Label(
            self.title_row,
            text="AZMUTH NEUROMORPHIC CORE",
            font=self.font("Segoe UI Semibold", 11),
            fg=t.text_primary,
            bg=t.bg_panel,
        )
        self.lbl_title.pack(side=tk.LEFT)

        self.lbl_engine_sub = tk.Label(
            self.brand_frame,
            text="U0-U5 Foresight • 30-PAT Sensory Radar • Ultimatrix Gene Lab",
            font=self.font("Segoe UI", 8),
            fg=t.text_muted,
            bg=t.bg_panel,
        )
        self.lbl_engine_sub.pack(anchor="w")

        # 2. Live Gear Selector Pills
        self.gear_frame = tk.Frame(self.top_header, bg=t.bg_panel, padx=10, pady=8)
        self.gear_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.lbl_gear_hdr = tk.Label(self.gear_frame, text="DAEMON GEAR", font=self.font("Segoe UI", 8), fg=t.text_muted, bg=t.bg_panel)
        self.lbl_gear_hdr.pack(anchor="w")
        self.btn_row = tk.Frame(self.gear_frame, bg=t.bg_panel)
        self.btn_row.pack(anchor="w", pady=(2, 0))

        self.gear_buttons: Dict[str, tk.Button] = {}
        for g_key, g_label in [("whisper", "● Whisper"), ("balanced", "● Balanced"), ("turbo", "● Turbo")]:
            b = tk.Button(
                self.btn_row,
                text=g_label,
                font=self.font("Segoe UI", 8),
                bg=t.bg_card,
                fg=t.text_secondary,
                relief=tk.FLAT,
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda k=g_key: self._on_select_gear(k),
            )
            b.pack(side=tk.LEFT, padx=(0, 3))
            self.gear_buttons[g_key] = b

        self.btn_pause = tk.Button(
            self.btn_row,
            text="⏸ Pause",
            font=self.font("Segoe UI", 8),
            bg=t.bg_card,
            fg=t.text_secondary,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._on_toggle_pause,
        )
        self.btn_pause.pack(side=tk.LEFT, padx=(3, 0))

        # 3. 60FPS RAM Oscilloscope Sparkline
        self.osc_frame = tk.Frame(self.top_header, bg=t.bg_panel, padx=10, pady=8)
        self.osc_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.osc_top = tk.Frame(self.osc_frame, bg=t.bg_panel)
        self.osc_top.pack(fill=tk.X)
        self.lbl_osc_hdr = tk.Label(self.osc_top, text="RAM OSCILLOSCOPE", font=self.font("Segoe UI", 8), fg=t.text_muted, bg=t.bg_panel)
        self.lbl_osc_hdr.pack(side=tk.LEFT)
        self.lbl_ram_readout = tk.Label(
            self.osc_top, text="8.0 GB Free (50%)", font=self.font("Consolas", 8), fg=t.accent_cyan, bg=t.bg_panel
        )
        self.lbl_ram_readout.pack(side=tk.RIGHT, padx=(6, 0))

        self.osc_canvas = tk.Canvas(
            self.osc_frame, width=170, height=28, bg=t.bg_void, highlightthickness=1, highlightbackground=t.border_subtle
        )
        self.osc_canvas.pack(pady=(2, 0))

        # 4. KPI Telemetry Cards
        self.kpi_container = tk.Frame(self.top_header, bg=t.bg_panel, padx=8, pady=8)
        self.kpi_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.kpi_labels: Dict[str, tk.Label] = {}
        self.kpi_cards: List[tk.Frame] = []
        self.kpi_title_lbls: List[tk.Label] = []
        kpis = [
            ("pat_pool", "GITHUB PAT POOL", f"{len(self.gh_sensor.pool.tokens)} / 30 Ready", t.accent_cyan),
            ("genes", "GENES SEQUENCED", f"{len(self.genes_catalog)} Loci", t.accent_purple),
            ("mutations", "MUTATIONS", f"{self.mutation_ledger_data.get('mutations_applied', 0)}", t.accent_emerald),
            ("arena", "ARENA RACES", f"{self.arena_ledger_data.get('tournaments_run', 0)}", t.accent_gold),
        ]
        for k_id, k_title, k_val, k_color in kpis:
            card = tk.Frame(self.kpi_container, bg=t.bg_card, padx=8, pady=4, highlightthickness=1, highlightbackground=t.border_subtle)
            card.pack(side=tk.LEFT, fill=tk.Y, padx=3)
            self.kpi_cards.append(card)
            t_lbl = tk.Label(card, text=k_title, font=self.font("Segoe UI", 7), fg=t.text_muted, bg=t.bg_card)
            t_lbl.pack(anchor="w")
            self.kpi_title_lbls.append(t_lbl)
            lbl = tk.Label(card, text=k_val, font=self.font("Segoe UI Semibold", 9), fg=k_color, bg=t.bg_card)
            lbl.pack(anchor="w")
            self.kpi_labels[k_id] = lbl

        # 5. Zoom & Theme Controls in Header (Far Right)
        self.ctrl_header_frame = tk.Frame(self.top_header, bg=t.bg_panel, padx=10, pady=8)
        self.ctrl_header_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.zoom_row = tk.Frame(self.ctrl_header_frame, bg=t.bg_panel)
        self.zoom_row.pack(anchor="e")

        self.btn_zoom_out = tk.Button(
            self.zoom_row, text=" - ", font=self.font("Consolas", 8, "bold"), bg=t.bg_card, fg=t.text_primary,
            relief=tk.FLAT, padx=4, pady=1, cursor="hand2", command=self.zoom_out
        )
        self.btn_zoom_out.pack(side=tk.LEFT, padx=1)

        self.btn_zoom_reset = tk.Button(
            self.zoom_row, text="100%", font=self.font("Consolas", 8), bg=t.bg_card, fg=t.accent_cyan,
            relief=tk.FLAT, padx=6, pady=1, cursor="hand2", command=self.zoom_reset
        )
        self.btn_zoom_reset.pack(side=tk.LEFT, padx=1)

        self.btn_zoom_in = tk.Button(
            self.zoom_row, text=" + ", font=self.font("Consolas", 8, "bold"), bg=t.bg_card, fg=t.text_primary,
            relief=tk.FLAT, padx=4, pady=1, cursor="hand2", command=self.zoom_in
        )
        self.btn_zoom_in.pack(side=tk.LEFT, padx=1)

        # Light / Dark Theme Toggle Pill
        self.btn_theme_toggle = tk.Button(
            self.ctrl_header_frame,
            text="☼ Light Mode" if not t.is_light else "☾ Dark Mode",
            font=self.font("Segoe UI", 8),
            bg=t.bg_card,
            fg=t.text_primary,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.toggle_theme,
        )
        self.btn_theme_toggle.pack(anchor="e", pady=(4, 0))

    def _build_tuning_and_action_bar(self) -> None:
        t = self.theme
        self.bar = tk.Frame(self.root, bg=t.bg_card, highlightthickness=1, highlightbackground=t.border_subtle)
        self.bar.pack(fill=tk.X, side=tk.TOP)

        # View Switcher Tabs (Left)
        self.view_frame = tk.Frame(self.bar, bg=t.bg_card, padx=8, pady=4)
        self.view_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.view_buttons: Dict[str, tk.Button] = {}
        views = [
            ("pipeline", "1 • Pipeline & PAT Flow"),
            ("dag", "2 • U0–U5 Causal DAG"),
            ("genes", "3 • Gene Lab & Evolution Tree"),
            ("ingestion", "4 • Live Ingestion & Ledger"),
        ]
        for v_id, v_text in views:
            btn = tk.Button(
                self.view_frame,
                text=v_text,
                font=self.font("Segoe UI Semibold", 9),
                bg=t.bg_panel,
                fg=t.text_secondary,
                relief=tk.FLAT,
                padx=10,
                pady=4,
                cursor="hand2",
                command=lambda v=v_id: self.switch_view(v),
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.view_buttons[v_id] = btn

        # Tuning Controls (Middle)
        self.tune_frame = tk.Frame(self.bar, bg=t.bg_card, padx=6, pady=4)
        self.tune_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.lbl_tune_z = tk.Label(self.tune_frame, text="Thalamic |Z| Gate:", font=self.font("Segoe UI", 8), fg=t.text_secondary, bg=t.bg_card)
        self.lbl_tune_z.pack(side=tk.LEFT, padx=(4, 2))

        self.spin_z = tk.Spinbox(
            self.tune_frame,
            from_=0.1,
            to=3.0,
            increment=0.1,
            textvariable=self.thalamic_z_threshold,
            width=5,
            font=self.font("Consolas", 8),
            bg=t.bg_input,
            fg=t.accent_cyan,
            buttonbackground=t.bg_panel,
            relief=tk.FLAT,
            command=self._on_parameter_tuned,
        )
        self.spin_z.pack(side=tk.LEFT, padx=(0, 8))
        self.spin_z.bind("<Return>", lambda e: self._on_parameter_tuned())

        self.lbl_tune_ram = tk.Label(self.tune_frame, text="RAM Breaker:", font=self.font("Segoe UI", 8), fg=t.text_secondary, bg=t.bg_card)
        self.lbl_tune_ram.pack(side=tk.LEFT, padx=(4, 2))

        self.spin_ram = tk.Spinbox(
            self.tune_frame,
            from_=1.5,
            to=8.0,
            increment=0.5,
            textvariable=self.ram_circuit_limit_gb,
            width=5,
            font=self.font("Consolas", 8),
            bg=t.bg_input,
            fg=t.accent_amber,
            buttonbackground=t.bg_panel,
            relief=tk.FLAT,
            command=self._on_parameter_tuned,
        )
        self.spin_ram.pack(side=tk.LEFT, padx=(0, 8))

        # Action Buttons (Right)
        self.act_frame = tk.Frame(self.bar, bg=t.bg_card, padx=8, pady=4)
        self.act_frame.pack(side=tk.RIGHT, fill=tk.Y)

        actions = [
            ("☁️ A100 Burst", t.accent_crimson, self._trigger_colab_cloud_burst),
            ("◈ Scan GitHub", t.accent_cyan, self._trigger_github_scan),
            ("✦ Synthesize DAG", t.accent_blue, self._trigger_macro_synthesis),
            ("▶ Mutate & Race", t.accent_purple, self._trigger_mutate_selected_gene),
            ("☷ Harvest Task", t.accent_emerald, self._trigger_harvest_task),
            ("🔄 Reset DAG", t.accent_cyan, self.reset_layout),
            ("↻ Verify Cycle", t.accent_gold, self._trigger_full_cycle),
        ]
        self.action_buttons.clear()
        for label, color, cmd in actions:
            b = tk.Button(
                self.act_frame,
                text=label,
                font=self.font("Segoe UI", 8),
                bg=t.bg_panel,
                fg=color,
                activebackground=color,
                activeforeground=t.bg_void,
                highlightthickness=1,
                highlightbackground=color,
                relief=tk.FLAT,
                padx=8,
                pady=3,
                cursor="hand2",
                command=cmd,
            )
            b.pack(side=tk.LEFT, padx=2)
            self.action_buttons.append((b, color))

    def _build_main_workspace(self) -> None:
        t = self.theme
        workspace = tk.Frame(self.root, bg=t.bg_main)
        workspace.pack(fill=tk.BOTH, expand=True)

        # 1. Left Sidebar
        self.left_panel = tk.Frame(
            workspace, bg=t.bg_panel, width=max(220, int(round(300 * self.scale))),
            highlightthickness=1, highlightbackground=t.border_subtle
        )
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)

        self.left_header_lbl = tk.Label(
            self.left_panel,
            text="SENSORY & GENOMIC EXPLORER",
            font=self.font("Segoe UI Semibold", 9),
            fg=t.text_primary,
            bg=t.bg_card,
            anchor="w",
            padx=10,
            pady=6,
        )
        self.left_header_lbl.pack(fill=tk.X)

        self.left_filter_frame = tk.Frame(self.left_panel, bg=t.bg_panel, padx=6, pady=4)
        self.left_filter_frame.pack(fill=tk.X)

        self.search_entry = tk.Entry(
            self.left_filter_frame,
            textvariable=self.search_query_var,
            font=self.font("Segoe UI", 9),
            bg=t.bg_input,
            fg=t.text_primary,
            insertbackground=t.accent_cyan,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=t.border_active,
        )
        self.search_entry.pack(fill=tk.X, ipady=3)
        self.search_query_var.trace_add("write", lambda *_: self._populate_left_panel())

        self.tier_filter_row = tk.Frame(self.left_panel, bg=t.bg_panel, padx=4, pady=2)
        self.tier_filter_row.pack(fill=tk.X)
        self.tier_pill_btns: Dict[int, tk.Button] = {}
        for t_idx, t_short in [(-1, "ALL"), (0, "T0"), (1, "T1"), (2, "T2"), (3, "T3"), (4, "T4"), (5, "T5")]:
            tb = tk.Button(
                self.tier_filter_row,
                text=t_short,
                font=self.font("Consolas", 8, "bold"),
                bg=t.bg_card,
                fg=t.tier_colors.get(t_idx, t.text_secondary),
                relief=tk.FLAT,
                padx=4,
                pady=1,
                cursor="hand2",
                command=lambda ti=t_idx: self._set_tier_filter(ti),
            )
            tb.pack(side=tk.LEFT, padx=1, expand=True, fill=tk.X)
            self.tier_pill_btns[t_idx] = tb

        list_container = tk.Frame(self.left_panel, bg=t.bg_panel, padx=4, pady=4)
        list_container.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL)
        self.left_listbox = tk.Listbox(
            list_container,
            bg=t.bg_void,
            fg=t.text_secondary,
            selectbackground=t.accent_blue,
            selectforeground=t.text_primary,
            font=self.font("Consolas", 8),
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=t.border_subtle,
            activestyle="none",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.left_listbox.yview)
        self.left_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.left_listbox.bind("<<ListboxSelect>>", self._on_left_list_select)
        self.left_items_meta: List[Dict[str, Any]] = []

        # 2. Right Panel (Capability & Telemetry Inspector)
        self.right_panel = tk.Frame(
            workspace, bg=t.bg_panel, width=max(280, int(round(390 * self.scale))),
            highlightthickness=1, highlightbackground=t.border_subtle
        )
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)

        self.right_hdr = tk.Frame(self.right_panel, bg=t.bg_card)
        self.right_hdr.pack(fill=tk.X)
        self.right_title_lbl = tk.Label(
            self.right_hdr,
            text="CAPABILITY & NODE INSPECTOR",
            font=self.font("Segoe UI Semibold", 9),
            fg=t.text_primary,
            bg=t.bg_card,
            anchor="w",
            padx=10,
            pady=6,
        )
        self.right_title_lbl.pack(side=tk.LEFT)

        self.btn_contextual_action = tk.Button(
            self.right_hdr,
            text="⚡ Action",
            font=self.font("Segoe UI", 8),
            bg=t.accent_purple,
            fg=t.text_primary,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._on_contextual_inspector_action,
        )
        self.btn_contextual_action.pack(side=tk.RIGHT, padx=6, pady=4)

        self.cap_summary_frame = tk.Frame(self.right_panel, bg=t.bg_panel, padx=8, pady=6)
        self.cap_summary_frame.pack(fill=tk.X)

        insp_text_frame = tk.Frame(self.right_panel, bg=t.bg_panel, padx=8, pady=4)
        insp_text_frame.pack(fill=tk.BOTH, expand=True)

        insp_scroll = ttk.Scrollbar(insp_text_frame, orient=tk.VERTICAL)
        self.inspector_text = tk.Text(
            insp_text_frame,
            bg=t.bg_void,
            fg=t.text_secondary,
            font=self.font("Consolas", 8),
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=8,
            pady=6,
            highlightthickness=1,
            highlightbackground=t.border_subtle,
            yscrollcommand=insp_scroll.set,
        )
        insp_scroll.config(command=self.inspector_text.yview)
        self.inspector_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        insp_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.inspector_text.tag_configure("h1", font=self.font("Segoe UI Semibold", 10), foreground=t.text_primary)
        self.inspector_text.tag_configure("h2", font=self.font("Segoe UI Semibold", 9), foreground=t.accent_cyan)
        self.inspector_text.tag_configure("gold", foreground=t.accent_gold, font=self.font("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("emerald", foreground=t.accent_emerald, font=self.font("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("crimson", foreground=t.accent_crimson, font=self.font("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("purple", foreground=t.accent_purple, font=self.font("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("muted", foreground=t.text_muted)
        self.inspector_text.tag_configure("mutation_add", foreground=t.code_diff_fg, background=t.code_diff_bg)
        self.inspector_text.tag_configure("code", foreground=t.code_fg, background=t.code_bg)

        # 3. Central 60FPS Interactive Canvas
        center_frame = tk.Frame(workspace, bg=t.bg_void)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_bar = tk.Frame(center_frame, bg=t.bg_main, padx=10, pady=3)
        self.canvas_bar.pack(fill=tk.X, side=tk.TOP)
        self.lbl_canvas_mode = tk.Label(
            self.canvas_bar,
            text="VIEW [1] — END-TO-END SENSORY, THALAMIC & GENOMIC PIPELINE FLOW",
            font=self.font("Segoe UI Semibold", 9),
            fg=t.accent_cyan,
            bg=t.bg_main,
        )
        self.lbl_canvas_mode.pack(side=tk.LEFT)

        self.btn_reset_layout = tk.Button(
            self.canvas_bar,
            text="🔄 Reset DAG Layout",
            font=self.font("Segoe UI", 8, "bold"),
            bg=t.bg_panel,
            fg=t.accent_cyan,
            activebackground=t.accent_cyan,
            activeforeground=t.bg_void,
            relief=tk.FLAT,
            padx=8,
            pady=1,
            cursor="hand2",
            command=self.reset_layout,
        )
        self.btn_reset_layout.pack(side=tk.RIGHT, padx=(6, 0))

        self.lbl_canvas_hint = tk.Label(
            self.canvas_bar,
            text="Drag Node: Move • Canvas: Pan • Zoom: Wheel • Reset: Ctrl+R / F5",
            font=self.font("Segoe UI", 8),
            fg=t.text_muted,
            bg=t.bg_main,
        )
        self.lbl_canvas_hint.pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(center_frame, bg=t.bg_void, highlightthickness=0, cursor="fleur")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_motion)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)
        self.canvas.bind("<ButtonPress-3>", self._on_pan_start)
        self.canvas.bind("<B3-Motion>", self._on_pan_motion)
        self.canvas.bind("<ButtonRelease-3>", self._on_pan_end)
        self.canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)
        self.canvas.bind("<Configure>", lambda e: self._redraw_active_canvas())

    def _build_status_footer(self) -> None:
        t = self.theme
        self.footer = tk.Frame(self.root, bg=t.bg_panel, height=26, highlightthickness=1, highlightbackground=t.border_subtle)
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer.pack_propagate(False)

        self.lbl_footer_job = tk.Label(
            self.footer,
            text="● Status: IDLE — Event-Driven Telemetry Active (60 FPS)",
            font=self.font("Consolas", 8),
            fg=t.accent_emerald,
            bg=t.bg_panel,
            padx=10,
        )
        self.lbl_footer_job.pack(side=tk.LEFT)

        self.lbl_footer_zoom = tk.Label(
            self.footer,
            text="Zoom: 100% (Ctrl+= / Ctrl+- / Ctrl+0)",
            font=self.font("Segoe UI", 8),
            fg=t.text_muted,
            bg=t.bg_panel,
            padx=10,
        )
        self.lbl_footer_zoom.pack(side=tk.RIGHT)

        self.lbl_footer_right = tk.Label(
            self.footer,
            text="Reset DAG: Ctrl+R / F5 | Theme: Ctrl+T | Subsystem: Win32 GUI",
            font=self.font("Segoe UI", 8),
            fg=t.text_muted,
            bg=t.bg_panel,
            padx=10,
        )
        self.lbl_footer_right.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------------
    # View Switching & Left Panel
    # ------------------------------------------------------------------------

    def switch_view(self, view_name: str) -> None:
        self.active_view = view_name
        self.selected_node_id = None
        self.shock_overlay.clear()
        t = self.theme

        for v_id, btn in self.view_buttons.items():
            if v_id == view_name:
                btn.configure(bg=t.accent_blue, fg=t.text_primary)
            else:
                btn.configure(bg=t.bg_panel, fg=t.text_secondary)

        if view_name == "pipeline":
            self.left_header_lbl.configure(text="4-STREAM RADAR & 30-PAT POOL")
            self.lbl_canvas_mode.configure(
                text="VIEW [1] — END-TO-END SENSORY, THALAMIC & GENOMIC PIPELINE FLOW", fg=t.accent_cyan
            )
            self.btn_contextual_action.configure(text="◈ Scan Radar", bg=t.accent_cyan, fg=t.bg_void)
        elif view_name == "dag":
            self.left_header_lbl.configure(text="CORTICAL CARTRIDGES (U0–U5)")
            self.lbl_canvas_mode.configure(
                text="VIEW [2] — U0–U5 NEUROMORPHIC CAUSAL DAG & SHOCK PROPAGATION", fg=t.accent_blue
            )
            self.btn_contextual_action.configure(text="⚡ Shock (+2.0σ)", bg=t.accent_crimson, fg=t.text_primary)
        elif view_name == "genes":
            self.left_header_lbl.configure(text=f"GENOMIC TAXONOMY ({len(self.genes_catalog)} GENES)")
            self.lbl_canvas_mode.configure(
                text="VIEW [3] — PHYLOGENETIC GENE EVOLUTION TREE & ALLELE ARENA", fg=t.accent_purple
            )
            self.btn_contextual_action.configure(text="▶ Mutate & Race", bg=t.accent_purple, fg=t.text_primary)
        elif view_name == "ingestion":
            self.left_header_lbl.configure(text="INGESTION & TELEMETRY STREAM")
            self.lbl_canvas_mode.configure(
                text="VIEW [4] — LIVE INGESTION FUNNEL & MULTI-UNIVERSE RADAR", fg=t.accent_emerald
            )
            self.btn_contextual_action.configure(text="☁️ A100 Burst", bg=t.accent_crimson, fg=t.text_primary)

        self._populate_left_panel()
        self._redraw_active_canvas()

    def _set_tier_filter(self, tier_idx: int) -> None:
        self.selected_tier_filter = tier_idx
        t = self.theme
        for ti, btn in self.tier_pill_btns.items():
            if ti == tier_idx:
                btn.configure(bg=t.accent_blue, fg=t.text_primary)
            else:
                btn.configure(bg=t.bg_card, fg=t.tier_colors.get(ti, t.text_secondary))
        if self.active_view != "genes":
            self.switch_view("genes")
        else:
            self._populate_left_panel()

    def _populate_left_panel(self) -> None:
        self.left_listbox.delete(0, tk.END)
        self.left_items_meta.clear()
        q = self.search_query_var.get().strip().lower()

        if self.active_view == "pipeline":
            t = self.gh_cache_data.get("telemetry", {})
            streams = [
                ("STREAM_U3_LABS", f"◈ [U3] Lab Alpha ({len(t.get('opportunities', []))} hits)"),
                ("STREAM_U1_RELEASES", f"▶ [U1/U2] SOTA Releases ({len(t.get('releases', []))} tags)"),
                ("STREAM_CODON_CP", f"✦ [Codon] CP Archives ({len(t.get('cp_archives', []))} repos)"),
                ("STREAM_U0_ECO", f"● [U0] Ecosystem Health ({len(t.get('ecosystem', []))} repos)"),
                ("STAGE_PAT_RING", f"◈ 30-PAT Token Pool ({len(self.gh_sensor.pool.tokens)} tokens)"),
                ("STAGE_THALAMIC", f"⚡ Thalamic Sieve (|Z| >= {self.thalamic_z_threshold.get():.1f}σ)"),
                ("STAGE_ULTIMATRIX", f"✦ Ultimatrix Arena ({self.arena_ledger_data.get('tournaments_run', 0)} races)"),
            ]
            for s_id, s_label in streams:
                if not q or q in s_label.lower():
                    self.left_listbox.insert(tk.END, f" {s_label}")
                    self.left_items_meta.append({"type": "pipeline_stage", "id": s_id})

            for opp in t.get("opportunities", []):
                lbl = f"   • [U3] {opp.get('repo', '')}: {opp.get('title', '')[:30]}"
                if not q or q in lbl.lower():
                    self.left_listbox.insert(tk.END, lbl)
                    self.left_items_meta.append({"type": "gh_item", "stream": "U3", "data": opp})

            for rel in t.get("releases", []):
                lbl = f"   • [Rel] {rel.get('repo', '')} ({rel.get('tag', '')})"
                if not q or q in lbl.lower():
                    self.left_listbox.insert(tk.END, lbl)
                    self.left_items_meta.append({"type": "gh_item", "stream": "U1/U2", "data": rel})

        elif self.active_view == "dag":
            for idx, c in enumerate(self.cartridges):
                marker = "▶" if idx == self.current_cartridge_idx else " "
                lbl = f"{marker} [{c['universe_id']}] {c['cortical_lobe']} ({c['node_count']}N)"
                if not q or q in lbl.lower():
                    self.left_listbox.insert(tk.END, lbl)
                    self.left_items_meta.append({"type": "cartridge", "index": idx})

            if self.current_macro_graph:
                self.left_listbox.insert(tk.END, " ─── ACTIVE CORTICAL NODES ───")
                self.left_items_meta.append({"type": "separator"})
                for nid, node in self.current_macro_graph.nodes.items():
                    z = node.get("z_score", 0.0)
                    state_short = "SPIKE" if abs(z) >= self.thalamic_z_threshold.get() else "EQ"
                    lbl = f"  [{state_short}] {nid} (Z={z:+.2f}σ)"
                    if not q or q in lbl.lower() or q in node.get("label", "").lower():
                        self.left_listbox.insert(tk.END, lbl)
                        self.left_items_meta.append({"type": "dag_node", "id": nid})

        elif self.active_view == "genes":
            sorted_genes = sorted(
                self.genes_catalog.values(),
                key=lambda g: (
                    0 if any("_mut_" in a.get("allele_id", "") for a in g.get("alleles", [])) else 1,
                    int(g.get("tier", 2)),
                    g.get("gene_id", ""),
                ),
            )
            for g in sorted_genes:
                gid = g.get("gene_id", "")
                tier = int(g.get("tier", 2))
                if self.selected_tier_filter != -1 and tier != self.selected_tier_filter:
                    continue
                desc = g.get("description", "")
                allele_cnt = len(g.get("alleles", []))
                has_mut = any("_mut_" in a.get("allele_id", "") for a in g.get("alleles", []))
                tag = "✦" if has_mut else "●"
                lbl = f" {tag} [T{tier}] {gid} ({allele_cnt}A)"
                if not q or q in gid.lower() or q in desc.lower() or q in g.get("category", "").lower():
                    self.left_listbox.insert(tk.END, lbl)
                    self.left_items_meta.append({"type": "gene", "gene_id": gid})

        elif self.active_view == "ingestion":
            events = self._load_recent_ingestion_events(limit=100)
            if not events:
                self.left_listbox.insert(tk.END, "  [i] No ingestion events recorded yet.")
            for ev in events:
                etype = ev.get("event_type", "EVENT")
                src = ev.get("source", "System")
                title = ev.get("title", ev.get("item_id", ""))
                ts = ev.get("timestamp", "")[11:19]
                lbl = f" [{ts}] {etype[:12]:<12} • {title[:28]}"
                if not q or q in etype.lower() or q in src.lower() or q in title.lower():
                    self.left_listbox.insert(tk.END, lbl)
                    self.left_items_meta.append({"type": "ingestion_event", "data": ev})

    def _on_left_list_select(self, event: Any) -> None:
        sel = self.left_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.left_items_meta):
            return
        meta = self.left_items_meta[idx]
        mtype = meta.get("type")

        if mtype == "pipeline_stage":
            self.selected_node_id = meta["id"]
            self._inspect_pipeline_stage(meta["id"])
            self._redraw_active_canvas()
        elif mtype == "gh_item":
            self._inspect_github_item(meta["stream"], meta["data"])
        elif mtype == "cartridge":
            self.current_cartridge_idx = meta["index"]
            self.shock_overlay.clear()
            self._load_selected_cartridge()
            self._populate_left_panel()
            self._redraw_active_canvas()
        elif mtype == "dag_node":
            self.selected_node_id = meta["id"]
            self._inspect_dag_node(meta["id"])
            self._redraw_active_canvas()
        elif mtype == "gene":
            self.selected_gene_id = meta["gene_id"]
            self.selected_allele_id = None
            self._inspect_gene_or_allele(self.selected_gene_id, None)
            self._redraw_active_canvas()
        elif mtype == "ingestion_event":
            self._inspect_ingestion_event(meta["data"])

    # ------------------------------------------------------------------------
    # Scaled Canvas Rendering (with Zoom & Resolution Adaptation)
    # ------------------------------------------------------------------------

    def _redraw_active_canvas(self) -> None:
        self.canvas.delete("all")
        self.canvas_nodes.clear()
        w = max(self.canvas.winfo_width(), 680)
        h = max(self.canvas.winfo_height(), 500)
        t = self.theme

        # Technical grid lines scaled to zoom
        grid_step = max(24, int(round(36 * self.zoom_level)))
        for gx in range(0, w, grid_step):
            self.canvas.create_line(gx, 0, gx, h, fill=t.grid_line, width=1)
        for gy in range(0, h, grid_step):
            self.canvas.create_line(0, gy, w, gy, fill=t.grid_line, width=1)

        if self.active_view == "pipeline":
            self._draw_pipeline_flow_view(w, h)
        elif self.active_view == "dag":
            self._draw_causal_dag_view(w, h)
        elif self.active_view == "genes":
            self._draw_gene_phylogeny_view(w, h)
        elif self.active_view == "ingestion":
            self._draw_ingestion_view(w, h)

        self._draw_active_pulses()

    def _register_clickable_node(
        self,
        node_id: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        payload: Dict[str, Any],
        world_pos: Optional[Tuple[float, float]] = None,
        world_dim: Optional[Tuple[float, float]] = None,
    ) -> None:
        self.canvas_nodes[node_id] = {
            "bbox": (x1, y1, x2, y2),
            "center": ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
            "payload": payload,
            "world_pos": world_pos,
            "world_dim": world_dim,
        }

    def _draw_node_box(
        self,
        node_id: str,
        wx: float,
        wy: float,
        base_w: float,
        base_h: float,
        title: str,
        subtitle: str,
        accent: str,
        badge: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        t = self.theme
        cw = max(self.canvas.winfo_width(), 680)
        ch = max(self.canvas.winfo_height(), 500)

        # Check for user-dragged override in world space
        if node_id in self.custom_node_positions:
            wx, wy = self.custom_node_positions[node_id]

        sx, sy = self.w2s(wx, wy, cw, ch)

        # Scaled typography metrics (SVG-Style vector auto-fitting)
        title_sz = max(7, min(14, int(round(9 * self.cam_zoom))))
        sub_sz = max(6, min(12, int(round(8 * self.cam_zoom))))
        badge_sz = max(6, min(11, int(round(7 * self.cam_zoom))))

        f_title = tkFont.Font(family="Segoe UI Semibold", size=title_sz)
        f_sub = tkFont.Font(family="Consolas", size=sub_sz)
        f_badge = tkFont.Font(family="Consolas", size=badge_sz, weight="bold") if badge else None

        tw = f_title.measure(title)
        sw = f_sub.measure(subtitle)
        bw = (f_badge.measure(badge) + int(12 * self.cam_zoom)) if f_badge else 0

        # Auto-fit width and height to comfortably enclose text
        stripe_w = max(3, int(5 * self.cam_zoom))
        text_w = max(tw, sw)
        req_w = text_w + bw + stripe_w + int(24 * self.cam_zoom)
        req_h = f_title.metrics("linespace") + f_sub.metrics("linespace") + int(14 * self.cam_zoom)

        nw = max(base_w * self.cam_zoom, float(req_w))
        nh = max(base_h * self.cam_zoom, float(req_h))

        x1, y1 = sx - nw / 2.0, sy - nh / 2.0
        x2, y2 = sx + nw / 2.0, sy + nh / 2.0

        # Frustum culling margin (generous to allow smooth panning and off-screen selection)
        cull_margin = max(cw, 800.0)
        if x2 < -cull_margin or x1 > cw + cull_margin or y2 < -cull_margin or y1 > ch + cull_margin:
            self._register_clickable_node(
                node_id, x1, y1, x2, y2,
                payload or {"id": node_id, "title": title},
                world_pos=(wx, wy),
                world_dim=(nw / self.cam_zoom, nh / self.cam_zoom)
            )
            return

        is_sel = self.selected_node_id == node_id
        border_col = accent if is_sel else t.border_active
        border_w = max(2, int(2 * self.cam_zoom)) if is_sel else 1
        bg_col = t.bg_card_hover if is_sel else t.bg_card

        if is_sel:
            pad = max(2, int(3 * self.cam_zoom))
            self.canvas.create_rectangle(
                x1 - pad, y1 - pad, x2 + pad, y2 + pad, outline=accent, width=1, dash=(3, 3)
            )

        self.canvas.create_rectangle(x1, y1, x2, y2, fill=bg_col, outline=border_col, width=border_w)
        # Left accent stripe
        self.canvas.create_rectangle(x1, y1, x1 + stripe_w, y2, fill=accent, outline="")

        # Title & Subtitle with bounded scaled typography
        self.canvas.create_text(
            x1 + stripe_w + max(4, int(8 * self.cam_zoom)),
            y1 + nh * 0.33,
            text=title,
            fill=t.text_primary,
            font=("Segoe UI Semibold", title_sz),
            anchor="w",
        )
        self.canvas.create_text(
            x1 + stripe_w + max(4, int(8 * self.cam_zoom)),
            y1 + nh * 0.67,
            text=subtitle,
            fill=t.text_muted,
            font=("Consolas", sub_sz),
            anchor="w",
        )
        if badge:
            self.canvas.create_text(
                x2 - max(4, int(8 * self.cam_zoom)),
                y1 + nh * 0.33,
                text=badge,
                fill=accent,
                font=("Consolas", badge_sz, "bold"),
                anchor="e",
            )

        # Store world and screen coordinates in node registry
        self._register_clickable_node(
            node_id, x1, y1, x2, y2,
            payload or {"id": node_id, "title": title},
            world_pos=(wx, wy),
            world_dim=(nw / self.cam_zoom, nh / self.cam_zoom)
        )

    def _compute_smart_anchor(
        self,
        src_id: str,
        dst_id: str,
        pos1: Tuple[float, float],
        size1: Tuple[float, float],
        pos2: Tuple[float, float],
        size2: Tuple[float, float],
    ) -> Tuple[Tuple[float, float], Tuple[float, float], str]:
        """Calculates dynamic node edge anchor coordinates and flow orientation ('h' or 'v')."""
        x1, y1 = pos1
        w1, h1 = size1
        x2, y2 = pos2
        w2, h2 = size2

        dx = x2 - x1
        dy = y2 - y1

        is_src_circle = (src_id == "STAGE_PAT_RING")
        is_dst_circle = (dst_id == "STAGE_PAT_RING")

        r1 = w1 / 2.0
        r2 = w2 / 2.0
        hw1, hh1 = w1 / 2.0, h1 / 2.0
        hw2, hh2 = w2 / 2.0, h2 / 2.0

        # Determine dominant flow axis
        if abs(dx) >= abs(dy) * 0.75:
            orientation = "h"
            if dx >= 0:
                ax = x1 + (r1 if is_src_circle else hw1)
                ay = y1
                bx = x2 - (r2 if is_dst_circle else hw2)
                by = y2
            else:
                ax = x1 - (r1 if is_src_circle else hw1)
                ay = y1
                bx = x2 + (r2 if is_dst_circle else hw2)
                by = y2
        else:
            orientation = "v"
            if dy >= 0:
                ax = x1
                ay = y1 + (r1 if is_src_circle else hh1)
                bx = x2
                by = y2 - (r2 if is_dst_circle else hh2)
            else:
                ax = x1
                ay = y1 - (r1 if is_src_circle else hh1)
                bx = x2
                by = y2 + (r2 if is_dst_circle else hh2)

        # For circular nodes, compute radial angle towards anchor for smooth radial fanning
        if is_src_circle:
            ang1 = math.atan2(by - y1, bx - x1)
            ax = x1 + r1 * math.cos(ang1)
            ay = y1 + r1 * math.sin(ang1)
        if is_dst_circle:
            ang2 = math.atan2(ay - y2, ax - x2)
            bx = x2 + r2 * math.cos(ang2)
            by = y2 + r2 * math.sin(ang2)

        return (ax, ay), (bx, by), orientation

    def _draw_directed_edge(
        self,
        wx1: float,
        wy1: float,
        wx2: float,
        wy2: float,
        color: str = "#384152",
        label: str = "",
        dashed: bool = False,
        base_width: int = 2,
        orientation: str = "h",
    ) -> None:
        t = self.theme
        cw = max(self.canvas.winfo_width(), 680)
        ch = max(self.canvas.winfo_height(), 500)
        x1, y1 = self.w2s(wx1, wy1, cw, ch)
        x2, y2 = self.w2s(wx2, wy2, cw, ch)

        # Frustum culling margin (generous to allow smooth panning)
        cull_margin = max(cw, 800.0)
        if max(x1, x2) < -cull_margin or min(x1, x2) > cw + cull_margin or max(y1, y2) < -cull_margin or min(y1, y2) > ch + cull_margin:
            return

        dash_pat = (4, 4) if dashed else None
        ew = max(1, int(round(base_width * self.cam_zoom)))
        arr_len = max(5, int(round(8 * self.cam_zoom)))

        # Smooth cubic Bezier spline control points
        if orientation == "v":
            dy = max(24.0 * self.cam_zoom, abs(y2 - y1) * 0.45)
            sign_y = 1.0 if y2 >= y1 else -1.0
            cp1_x, cp1_y = x1, y1 + dy * sign_y
            cp2_x, cp2_y = x2, y2 - dy * sign_y
        else:
            dx = max(24.0 * self.cam_zoom, abs(x2 - x1) * 0.45)
            sign_x = 1.0 if x2 >= x1 else -1.0
            cp1_x, cp1_y = x1 + dx * sign_x, y1
            cp2_x, cp2_y = x2 - dx * sign_x, y2

        self.canvas.create_line(
            x1, y1, cp1_x, cp1_y, cp2_x, cp2_y, x2, y2,
            fill=color,
            width=ew,
            smooth=True,
            arrow=tk.LAST,
            arrowshape=(arr_len, arr_len + 2, 4),
            dash=dash_pat,
        )
        if label:
            mx = 0.125 * x1 + 0.375 * cp1_x + 0.375 * cp2_x + 0.125 * x2
            my = 0.125 * y1 + 0.375 * cp1_y + 0.375 * cp2_y + 0.125 * y2
            lbl_sz = max(6, min(10, int(round(7 * self.cam_zoom))))
            bw = max(26, int(len(label) * lbl_sz * 0.44 + 8))
            bh = max(10, int(lbl_sz * 1.5))
            self.canvas.create_rectangle(
                mx - bw, my - bh, mx + bw, my + bh,
                fill=t.bg_card,
                outline=t.border_subtle,
                width=1,
            )
            self.canvas.create_text(
                mx, my,
                text=label,
                fill=color,
                font=("Consolas", lbl_sz),
            )

    # --- VIEW 1: Pipeline & 30-PAT Ring Schematic ---

    def _draw_pipeline_flow_view(self, w: float, h: float) -> None:
        t = self.theme
        tel = self.gh_cache_data.get("telemetry", {})
        opp_cnt = len(tel.get("opportunities", []))
        rel_cnt = len(tel.get("releases", []))
        cp_cnt = len(tel.get("cp_archives", []))
        eco_cnt = len(tel.get("ecosystem", []))

        # World Coordinate Schematic Default Layout
        col1_wx = 190.0
        def_pat_wx, def_pat_wy = 540.0, 240.0
        def_thal_wx, def_thal_wy = 540.0, 540.0
        def_cortex_wx, def_cortex_wy = 880.0, 240.0
        def_gene_wx, def_gene_wy = 880.0, 540.0
        def_arena_wx, def_arena_wy = 1200.0, 390.0

        box_w = 175.0
        box_h = 48.0
        ring_world_r = 52.0
        ring_diam = (ring_world_r + 10.0) * 2.0

        stream_defs = [
            ("STREAM_U3_LABS", "U3 Lab Opportunity Alpha", f"{opp_cnt} Actionable Issues", t.accent_cyan, 140.0),
            ("STREAM_U1_RELEASES", "U1/U2 SOTA AI Releases", f"{rel_cnt} Upstream Tags", t.accent_blue, 300.0),
            ("STREAM_CODON_CP", "Codon Stream CP Archives", f"{cp_cnt} Algorithmic Repos", t.accent_purple, 460.0),
            ("STREAM_U0_ECO", "U0 Public Ecosystem", f"{eco_cnt} Monitored Repos", t.accent_emerald, 620.0),
        ]

        # Resolve effective positions (custom drag override or default layout)
        stage_positions: Dict[str, Tuple[float, float]] = {}
        stage_sizes: Dict[str, Tuple[float, float]] = {}

        for s_id, s_title, s_sub, s_col, def_sy in stream_defs:
            stage_positions[s_id] = self.custom_node_positions.get(s_id, (col1_wx, def_sy))
            stage_sizes[s_id] = (box_w, box_h)

        stage_positions["STAGE_PAT_RING"] = self.custom_node_positions.get("STAGE_PAT_RING", (def_pat_wx, def_pat_wy))
        stage_sizes["STAGE_PAT_RING"] = (ring_diam, ring_diam)

        stage_positions["STAGE_THALAMIC"] = self.custom_node_positions.get("STAGE_THALAMIC", (def_thal_wx, def_thal_wy))
        stage_sizes["STAGE_THALAMIC"] = (185.0, 58.0)

        stage_positions["STAGE_CORTEX"] = self.custom_node_positions.get("STAGE_CORTEX", (def_cortex_wx, def_cortex_wy))
        stage_sizes["STAGE_CORTEX"] = (185.0, 58.0)

        stage_positions["STAGE_ULTIMATRIX"] = self.custom_node_positions.get("STAGE_ULTIMATRIX", (def_gene_wx, def_gene_wy))
        stage_sizes["STAGE_ULTIMATRIX"] = (185.0, 58.0)

        stage_positions["STAGE_ARENA_SSOT"] = self.custom_node_positions.get("STAGE_ARENA_SSOT", (def_arena_wx, def_arena_wy))
        stage_sizes["STAGE_ARENA_SSOT"] = (180.0, 64.0)

        # 1. Draw all connecting directed edges first (so nodes sit cleanly on top)
        pipeline_edges = [
            ("STREAM_U3_LABS", "STAGE_PAT_RING", t.accent_cyan, "", False, 1),
            ("STREAM_U1_RELEASES", "STAGE_PAT_RING", t.accent_blue, "", False, 1),
            ("STREAM_CODON_CP", "STAGE_PAT_RING", t.accent_purple, "", False, 1),
            ("STREAM_U0_ECO", "STAGE_PAT_RING", t.accent_emerald, "", False, 1),
            ("STAGE_PAT_RING", "STAGE_THALAMIC", t.accent_cyan, "150k req/hr", False, 2),
            ("STAGE_THALAMIC", "STAGE_CORTEX", t.accent_blue, "Salient Spikes", False, 2),
            ("STAGE_THALAMIC", "STAGE_ULTIMATRIX", t.accent_purple, "Codon Feed", False, 2),
            ("STAGE_CORTEX", "STAGE_ARENA_SSOT", t.accent_blue, "Foresight Directives", False, 2),
            ("STAGE_ULTIMATRIX", "STAGE_ARENA_SSOT", t.accent_purple, "Evolved Alleles", False, 2),
        ]

        for src_id, dst_id, e_col, e_lbl, e_dash, e_width in pipeline_edges:
            p1 = stage_positions[src_id]
            s1 = stage_sizes[src_id]
            p2 = stage_positions[dst_id]
            s2 = stage_sizes[dst_id]
            (ax, ay), (bx, by), orient = self._compute_smart_anchor(src_id, dst_id, p1, s1, p2, s2)
            self._draw_directed_edge(
                ax, ay, bx, by,
                color=e_col,
                label=e_lbl,
                dashed=e_dash,
                base_width=e_width,
                orientation=orient,
            )

        # 2. Draw 4 Sensory Stream Stage Boxes
        for s_id, s_title, s_sub, s_col, def_sy in stream_defs:
            swx, swy = stage_positions[s_id]
            self._draw_node_box(
                s_id, swx, swy, box_w, box_h, s_title, s_sub, s_col, payload={"type": "pipeline_stage", "id": s_id}
            )

        # 3. Draw 30-PAT Ring in World Coordinates
        pat_wx, pat_wy = stage_positions["STAGE_PAT_RING"]
        pat_sx, pat_sy = self.w2s(pat_wx, pat_wy, w, h)
        screen_r = ring_world_r * self.cam_zoom
        ring_pad = 10.0 * self.cam_zoom

        self.canvas.create_oval(
            pat_sx - screen_r - ring_pad,
            pat_sy - screen_r - ring_pad,
            pat_sx + screen_r + ring_pad,
            pat_sy + screen_r + ring_pad,
            fill=t.bg_card,
            outline=t.border_active,
            width=1,
        )
        tokens = self.gh_sensor.pool.tokens
        n_tok = max(len(tokens), 30)
        ptr = self.gh_sensor.pool._pointer % max(len(tokens), 1)
        for i in range(n_tok):
            angle = (2 * math.pi * i / n_tok) - math.pi / 2
            tx = pat_sx + screen_r * math.cos(angle)
            ty = pat_sy + screen_r * math.sin(angle)
            is_active = (i == ptr) or (self.is_job_running and (i == (self.anim_tick // 4) % n_tok))
            dot_col = t.accent_gold if is_active else (t.accent_cyan if i < len(tokens) else t.border_subtle)
            rd = max(3, int(4 * self.cam_zoom)) if is_active else max(2, int(2.5 * self.cam_zoom))
            self.canvas.create_oval(tx - rd, ty - rd, tx + rd, ty + rd, fill=dot_col, outline="")

        lbl_fnt_sz = max(7, min(10, int(9 * self.cam_zoom)))
        sub_fnt_sz = max(6, min(9, int(8 * self.cam_zoom)))
        self.canvas.create_text(pat_sx, pat_sy - 6 * self.cam_zoom, text="30-PAT RING", fill=t.text_primary, font=("Segoe UI Semibold", lbl_fnt_sz))
        self.canvas.create_text(
            pat_sx, pat_sy + 8 * self.cam_zoom, text=f"{len(tokens)} Pooled Keys", fill=t.accent_cyan, font=("Consolas", sub_fnt_sz)
        )
        self._register_clickable_node(
            "STAGE_PAT_RING",
            pat_sx - screen_r - ring_pad,
            pat_sy - screen_r - ring_pad,
            pat_sx + screen_r + ring_pad,
            pat_sy + screen_r + ring_pad,
            {"type": "pipeline_stage", "id": "STAGE_PAT_RING"},
            world_pos=(pat_wx, pat_wy),
            world_dim=((ring_world_r + 10.0) * 2, (ring_world_r + 10.0) * 2),
        )

        # 4. Thalamic Salience Gate
        thal_wx, thal_wy = stage_positions["STAGE_THALAMIC"]
        z_gate = self.thalamic_z_threshold.get()
        self._draw_node_box(
            "STAGE_THALAMIC",
            thal_wx,
            thal_wy,
            185.0,
            58.0,
            "Thalamic Salience Gate",
            f"Prunes Noise |Z| < {z_gate:.2f}σ",
            t.accent_amber,
            badge="SIEVE",
            payload={"type": "pipeline_stage", "id": "STAGE_THALAMIC"},
        )

        # 5. U0-U5 Cortical Foresight
        cortex_wx, cortex_wy = stage_positions["STAGE_CORTEX"]
        self._draw_node_box(
            "STAGE_CORTEX",
            cortex_wx,
            cortex_wy,
            185.0,
            58.0,
            "U0–U5 Cortical Foresight",
            f"6 Cartridges • {len(self.cartridges)} Lobes",
            t.accent_blue,
            badge="DAG",
            payload={"type": "pipeline_stage", "id": "STAGE_CORTEX"},
        )

        # 6. Ultimatrix Gene Sequencer
        gene_wx, gene_wy = stage_positions["STAGE_ULTIMATRIX"]
        mut_cnt = self.mutation_ledger_data.get("mutations_applied", 0)
        self._draw_node_box(
            "STAGE_ULTIMATRIX",
            gene_wx,
            gene_wy,
            185.0,
            58.0,
            "Ultimatrix Gene Sequencer",
            f"{len(self.genes_catalog)} Genes • {mut_cnt} Muts",
            t.accent_purple,
            badge="T0-T5",
            payload={"type": "pipeline_stage", "id": "STAGE_ULTIMATRIX"},
        )

        # 7. Arena & SSOT Ledgers
        arena_wx, arena_wy = stage_positions["STAGE_ARENA_SSOT"]
        races = self.arena_ledger_data.get("tournaments_run", 0)
        promos = self.arena_ledger_data.get("promotions", 0)
        self._draw_node_box(
            "STAGE_ARENA_SSOT",
            arena_wx,
            arena_wy,
            180.0,
            64.0,
            "Arena & SSOT Ledgers",
            f"{races} Races • {promos} Promoted",
            t.accent_gold,
            badge="VERIFIED",
            payload={"type": "pipeline_stage", "id": "STAGE_ARENA_SSOT"},
        )

        if not self.selected_node_id:
            self.selected_node_id = "STAGE_THALAMIC"
            self._inspect_pipeline_stage("STAGE_THALAMIC")

    # --- VIEW 2: U0-U5 Neuromorphic Causal DAG ---

    def _draw_causal_dag_view(self, w: float, h: float) -> None:
        t = self.theme
        if not self.current_macro_graph:
            self._load_selected_cartridge()
        if not self.current_macro_graph or not self.current_macro_graph.nodes:
            self.canvas.create_text(w / 2, h / 2, text="No Cortical Cartridge Loaded", fill=t.text_muted, font=self.font("Segoe UI", 11))
            return

        nodes = list(self.current_macro_graph.nodes.values())
        synapses = self.current_macro_graph.synapses

        positions: Dict[str, Tuple[float, float]] = {}
        in_deg: Dict[str, int] = {n["id"]: 0 for n in nodes}
        for s in synapses:
            if s["target"] in in_deg:
                in_deg[s["target"]] += 1

        roots = [n for n in nodes if in_deg.get(n["id"], 0) == 0]
        others = [n for n in nodes if in_deg.get(n["id"], 0) > 0]
        mid_split = max(1, len(others) // 2)
        mids = others[:mid_split]
        sinks = others[mid_split:]

        layers = [l for l in [roots, mids, sinks] if l]
        layer_spacing = 380.0
        start_wx = 200.0

        for l_idx, layer in enumerate(layers):
            lx = start_wx + l_idx * layer_spacing
            n_in_layer = len(layer)
            # Ensure at least 110 world units clearance between vertically stacked nodes
            v_step = max(110.0, 600.0 / max(n_in_layer + 1, 1))
            total_h = (n_in_layer - 1) * v_step
            base_y = 380.0 - (total_h / 2.0)
            for r_idx, n in enumerate(layer):
                ly = base_y + r_idx * v_step
                positions[n["id"]] = self.custom_node_positions.get(n["id"], (lx, ly))

        node_bw = 160.0
        node_bh = 50.0

        for s in synapses:
            src, tgt = s["source"], s["target"]
            if src in positions and tgt in positions:
                wx1, wy1 = positions[src]
                wx2, wy2 = positions[tgt]
                weight = float(s.get("weight", 0.0))
                lag = int(s.get("lag_days", 0))
                edge_col = t.accent_emerald if weight >= 0 else t.accent_crimson
                if tgt in self.shock_overlay:
                    edge_col = t.accent_gold
                (ax, ay), (bx, by), orient = self._compute_smart_anchor(
                    src, tgt, (wx1, wy1), (node_bw, node_bh), (wx2, wy2), (node_bw, node_bh)
                )
                self._draw_directed_edge(
                    ax,
                    ay,
                    bx,
                    by,
                    color=edge_col,
                    label=f"w={weight:+.2f} ({lag}d)",
                    base_width=2 if abs(weight) >= 0.5 else 1,
                    orientation=orient,
                )

        z_thresh = self.thalamic_z_threshold.get()
        for n in nodes:
            nid = n["id"]
            wx, wy = positions.get(nid, (640.0, 380.0))
            z = float(n.get("z_score", 0.0))
            shock_delta = self.shock_overlay.get(nid, 0.0)
            eff_z = z + shock_delta

            if abs(eff_z) < z_thresh:
                col = t.text_muted
                badge = "HABITUATED"
            elif abs(eff_z) < 2.0:
                col = t.accent_cyan
                badge = f"Z={eff_z:+.2f}σ"
            elif abs(eff_z) < 3.0:
                col = t.accent_amber
                badge = f"WARN {eff_z:+.1f}σ"
            else:
                col = t.accent_crimson
                badge = f"SPIKE {eff_z:+.1f}σ"

            if shock_delta != 0.0:
                badge = f"⚡ Δ{shock_delta:+.2f}"
                col = t.accent_gold

            self._draw_node_box(
                nid,
                wx,
                wy,
                node_bw,
                node_bh,
                nid[:16],
                f"{n.get('label', '')[:22]}",
                col,
                badge=badge,
                payload={"type": "dag_node", "id": nid},
            )

        if not self.selected_node_id and nodes:
            self.selected_node_id = nodes[0]["id"]
            self._inspect_dag_node(self.selected_node_id)

    # --- VIEW 3: Phylogenetic Gene Evolution Tree & Capabilities ---

    def _draw_gene_phylogeny_view(self, w: float, h: float) -> None:
        t = self.theme
        if not self.selected_gene_id or self.selected_gene_id not in self.genes_catalog:
            if self.genes_catalog:
                self.selected_gene_id = next(iter(self.genes_catalog.keys()))
            else:
                self.canvas.create_text(w / 2, h / 2, text="No Sequenced Genes Found", fill=t.text_muted, font=self.font("Segoe UI", 11))
                return

        gene_data = self.genes_catalog[self.selected_gene_id]
        phylo = build_gene_phylogeny(gene_data)
        tier_col = t.tier_colors.get(phylo["tier"], t.accent_cyan)

        # Top Banner on canvas
        banner_h = max(32, int(42 * self.zoom_level))
        self.canvas.create_rectangle(14, 10, w - 14, 10 + banner_h, fill=t.bg_card, outline=t.border_subtle)
        self.canvas.create_text(
            24,
            10 + banner_h / 2,
            text=f"GENE LOCUS: {phylo['gene_id']}  |  {phylo['tier_label']}  |  Category: {phylo['category'].upper()}",
            fill=tier_col,
            font=self.font("Segoe UI Semibold", 9),
            anchor="w",
        )
        speedup_txt = (
            f"★ Fitness Gain: +{phylo['net_speedup_pct']:.1f}% Speedup  ({phylo['total_alleles']} Alleles)"
        )
        self.canvas.create_text(w - 24, 10 + banner_h / 2, text=speedup_txt, fill=t.accent_gold, font=self.font("Segoe UI Semibold", 9), anchor="e")

        root_wx, root_wy = 240.0, 380.0
        wt_wx = 640.0
        mut_wx = 1040.0

        root_bw = 180.0
        root_bh = 64.0
        half_rbw = root_bw / 2.0

        self._draw_node_box(
            f"GENE_ROOT::{phylo['gene_id']}",
            root_wx,
            root_wy,
            root_bw,
            root_bh,
            phylo["gene_id"][:18],
            f"{phylo['tier_label'][:22]}",
            tier_col,
            badge=f"T{phylo['tier']}",
            payload={"type": "gene_root", "gene_id": phylo["gene_id"]},
        )

        wild_types = phylo["wild_types"]
        wt_positions: Dict[str, Tuple[float, float]] = {}
        allele_bw = 195.0
        allele_bh = 56.0
        half_abw = allele_bw / 2.0

        n_wt = len(wild_types)
        wt_vstep = max(110.0, 600.0 / max(n_wt + 1, 1))
        wt_total_h = (n_wt - 1) * wt_vstep
        wt_base_y = 380.0 - (wt_total_h / 2.0)

        for idx, wt in enumerate(wild_types):
            aid = wt.get("allele_id", f"wt_{idx}")
            wy = wt_base_y + idx * wt_vstep
            wt_positions[aid] = (wt_wx, wy)

            is_prim = wt.get("dominance") == "PRIMARY"
            col = t.accent_gold if is_prim else t.accent_cyan
            fit = wt.get("empirical_fitness", {})
            rt = fit.get("runtime_ms", "?")
            ram = fit.get("ram_kb", "?")
            comp = wt.get("complexity_time", "O(N)")

            self._draw_directed_edge(root_wx + half_rbw, root_wy, wt_wx - half_abw, wy, color=tier_col, label="Wild-Type")
            self._draw_node_box(
                f"ALLELE::{aid}",
                wt_wx,
                wy,
                allele_bw,
                allele_bh,
                aid[:20],
                f"{comp} • {rt} ms • {ram} KB",
                col,
                badge="★ PRIMARY" if is_prim else "BASE",
                payload={"type": "allele", "gene_id": phylo["gene_id"], "allele_id": aid},
            )

        mutants = phylo["mutants"]
        edge_lookup = {e["target_allele"]: e for e in phylo["edges"]}

        if mutants:
            # Group mutants by operator into clean parallel lanes to prevent massive single-column vertical pileups
            operator_lanes: Dict[str, List[Dict[str, Any]]] = {}
            for mut in mutants:
                mid = mut.get("allele_id", "")
                e_info = edge_lookup.get(mid, {})
                op_raw = e_info.get("operator", "mutation")
                # Normalize operator key for lane grouping
                op_key = op_raw.replace("operator_", "").replace("+", "").strip()
                operator_lanes.setdefault(op_key, []).append(mut)

            # Sort lanes so primary/fastest operators appear first
            sorted_op_keys = sorted(operator_lanes.keys(), key=lambda k: ("pragma" not in k, "bitwise" not in k, k))
            lane_base_x = 1040.0
            lane_spacing = 380.0

            for lane_idx, op_key in enumerate(sorted_op_keys):
                lane_mutants = operator_lanes[op_key]
                cur_lane_wx = lane_base_x + lane_idx * lane_spacing
                n_lane_mut = len(lane_mutants)
                mut_vstep = max(78.0, 560.0 / max(n_lane_mut + 1, 1))
                mut_total_h = (n_lane_mut - 1) * mut_vstep
                mut_base_y = 380.0 - (mut_total_h / 2.0)

                for idx, mut in enumerate(lane_mutants):
                    mid = mut.get("allele_id", f"mut_{idx}")
                    my = mut_base_y + idx * mut_vstep
                    e_info = edge_lookup.get(mid, {})
                    parent_id = e_info.get("source_allele", "")
                    op_name = e_info.get("operator", op_key)
                    speedup = e_info.get("speedup_pct", 0.0)

                    px, py = wt_positions.get(parent_id, (wt_wx, root_wy))
                    is_prim = mut.get("dominance") == "PRIMARY"
                    col = t.accent_gold if is_prim else t.accent_emerald

                    fit = mut.get("empirical_fitness", {})
                    rt = fit.get("runtime_ms", "?")
                    ram = fit.get("ram_kb", "?")

                    self._draw_directed_edge(
                        px + half_abw,
                        py,
                        cur_lane_wx - half_abw,
                        my,
                        color=col,
                        label=f"+{op_name} ({speedup:+.0f}%)",
                        base_width=2,
                    )
                    self._draw_node_box(
                        f"ALLELE::{mid}",
                        cur_lane_wx,
                        my,
                        allele_bw,
                        allele_bh,
                        mid[-22:],
                        f"Mutant • {rt} ms • {ram} KB",
                        col,
                        badge="★ CHAMPION" if is_prim else f"+{op_key[:8]}",
                        payload={"type": "allele", "gene_id": phylo["gene_id"], "allele_id": mid},
                    )
        else:
            self._draw_directed_edge(
                wt_wx + half_abw,
                root_wy,
                mut_wx - half_abw,
                root_wy,
                color=t.border_active,
                label="Click 'Mutate & Race'",
                dashed=True,
            )
            self._draw_node_box(
                "MUTATE_CTA",
                mut_wx,
                root_wy,
                allele_bw,
                allele_bh,
                "⚡ Evolve Daughter Allele",
                "Inject +fast_io / +pragma / +bitwise",
                t.accent_purple,
                badge="READY",
                payload={"type": "trigger_mutate", "gene_id": phylo["gene_id"]},
            )

        if not self.selected_node_id:
            self.selected_node_id = f"GENE_ROOT::{phylo['gene_id']}"
            self._inspect_gene_or_allele(phylo["gene_id"], self.selected_allele_id)

    def _draw_ingestion_view(self, cw: float, ch: float) -> None:
        """Renders View [4]: Live Ingestion Funnel, Universe Touch Radar & Activity Ledger."""
        t = self.theme
        cx, cy = cw / 2.0, ch / 2.0

        # Load sweep telemetry
        sweep_data: dict[str, Any] = {}
        if SWEEP_JSON.exists():
            try:
                sweep_data = json.loads(SWEEP_JSON.read_text(encoding="utf-8"))
            except Exception:
                pass
        universes = sweep_data.get("universes", {})

        # Top Pipeline Funnel Cards
        funnel_items = [
            ("INDEXED PROBLEMS", f"{self.corpus_ledger_data.get('tasks_indexed', 696)}+ Tasks", t.accent_cyan),
            ("VERIFIED SOLVES", f"{self.arena_ledger_data.get('tournaments_run', 266)}+ Solved", t.accent_blue),
            ("SEQUENCED GENES", f"{len(self.genes_catalog)} Loci", t.accent_purple),
            ("ALLELE MUTATIONS", f"{self.mutation_ledger_data.get('mutations_applied', 711)}+ Mutated", t.accent_emerald),
            ("ARENA PROMOTIONS", f"{self.mutation_ledger_data.get('promotions_won', 213)}+ Won", t.accent_gold),
        ]

        card_w = 110.0
        card_h = 55.0
        spacing = 125.0
        start_wx = cx - ((len(funnel_items) - 1) * spacing) / 2.0
        top_wy = cy - 160.0

        for i, (f_title, f_val, f_col) in enumerate(funnel_items):
            wx = start_wx + (i * spacing)
            self._draw_node_box(
                f"FUNNEL_{i}",
                wx,
                top_wy,
                card_w,
                card_h,
                f_title,
                f_val,
                f_col,
                badge="FUNNEL",
                payload={"type": "ingestion_funnel", "title": f_title, "value": f_val},
            )
            if i < len(funnel_items) - 1:
                next_wx = start_wx + ((i + 1) * spacing)
                self._draw_directed_edge(
                    wx + card_w / 2.0,
                    top_wy,
                    next_wx - card_w / 2.0,
                    top_wy,
                    color=t.border_active,
                    dashed=True,
                )

        # Bottom 6 Universe Lobes Matrix (U0-U5)
        u_lobes = [
            ("u0_ecosystem_mesh", "U0: Ecosystem Mesh", "28 Modules • Swarm Mesh", t.accent_cyan),
            ("u1_research_arbitrage", "U1: Research Arbitrage", "SOTA AI • Fellowship Lab", t.accent_blue),
            ("u2_ai_compute_frontier", "U2: Compute Frontier", "16GB RAM • Colab A100", t.accent_purple),
            ("u3_career_opportunity_alpha", "U3: Career Alpha", "KU Faculty • Grants", t.accent_emerald),
            ("u4_macro_capital_markets", "U4: Capital Markets", "Foundry Supply • NEPSE", t.accent_gold),
            ("u5_hardware_physics_bom", "U5: Physical BOM", "ESP32-S3 • 200Hz IMU", t.accent_crimson),
        ]

        u_cols = 3
        u_spacing_x = 220.0
        u_spacing_y = 90.0
        u_start_wx = cx - u_spacing_x
        u_start_wy = cy + 20.0

        for idx, (u_id, u_label, u_sub, u_col) in enumerate(u_lobes):
            col_idx = idx % u_cols
            row_idx = idx // u_cols
            wx = u_start_wx + (col_idx * u_spacing_x)
            wy = u_start_wy + (row_idx * u_spacing_y)

            u_meta = universes.get(u_id, {})
            spikes = u_meta.get("spikes_count", 0)
            choke = u_meta.get("top_chokepoint", "None")
            status_badge = f"{spikes} Spikes" if spikes > 0 else "EQ (0σ)"

            self._draw_node_box(
                f"UNIVERSE_LOBE_{u_id}",
                wx,
                wy,
                195.0,
                68.0,
                u_label,
                f"{u_sub}\nChokepoint: {choke}",
                u_col,
                badge=status_badge,
                payload={"type": "universe_status", "universe_id": u_id, "meta": u_meta},
            )

        # Center connector from Funnel to Universes
        self._draw_directed_edge(
            cx,
            top_wy + card_h / 2.0,
            cx,
            u_start_wy - 34.0,
            color=t.accent_emerald,
            label="Continuous Sensory Grounding",
            dashed=True,
        )

    # ------------------------------------------------------------------------
    # Inspector Population
    # ------------------------------------------------------------------------

    def _clear_inspector_badges(self) -> None:
        for child in self.cap_summary_frame.winfo_children():
            child.destroy()

    def _inspect_pipeline_stage(self, stage_id: str) -> None:
        self._clear_inspector_badges()
        self.inspector_text.delete("1.0", tk.END)
        t = self.theme
        tel = self.gh_cache_data.get("telemetry", {})

        tk.Label(
            self.cap_summary_frame,
            text=f"STAGE: {stage_id}",
            font=self.font("Segoe UI Semibold", 9),
            fg=t.accent_cyan,
            bg=t.bg_panel,
        ).pack(anchor="w")

        if stage_id == "STAGE_PAT_RING":
            self.inspector_text.insert(tk.END, "30-PAT ASYMMETRIC GITHUB TOKEN POOL\n", "h1")
            self.inspector_text.insert(
                tk.END,
                f"Active Tokens Discovered: {len(self.gh_sensor.pool.tokens)}\n"
                f"Combined Core Capacity: {len(self.gh_sensor.pool.tokens) * 5000:,} req/hr\n"
                f"Combined Search Capacity: {len(self.gh_sensor.pool.tokens) * 30:,} req/min\n\n",
                "emerald",
            )
            for tok in self.gh_sensor.pool.tokens[:15]:
                self.inspector_text.insert(
                    tk.END,
                    f"• [{tok['id']:<10}] {tok['status']} | Core: {tok['remaining_core']} | Search: {tok['remaining_search']}\n",
                    "code",
                )
        elif stage_id == "STAGE_THALAMIC":
            z_gate = self.thalamic_z_threshold.get()
            self.inspector_text.insert(tk.END, "THALAMIC SALIENCE FILTER\n", "h1")
            self.inspector_text.insert(
                tk.END,
                f"Active Threshold: |Z| >= {z_gate:.2f}σ\n"
                "Silences noisy low-salience repositories and habituated homeostatic nodes.\n\n",
                "gold",
            )
            self.inspector_text.insert(tk.END, "SALIENT U3 LAB OPPORTUNITIES:\n", "h2")
            for opp in tel.get("opportunities", []):
                sal = float(opp.get("salience", 1.0))
                status_tag = "emerald" if sal >= z_gate else "muted"
                self.inspector_text.insert(
                    tk.END,
                    f"  [Z={sal:+.2f}σ] {opp.get('repo')}\n    {opp.get('title')}\n    URL: {opp.get('url')}\n\n",
                    status_tag,
                )
        else:
            self.inspector_text.insert(tk.END, f"TELEMETRY SNAPSHOT — {stage_id}\n\n", "h1")
            self.inspector_text.insert(
                tk.END, json.dumps(self.gh_cache_data.get("telemetry", {}), indent=2)[:3500], "code"
            )

    def _inspect_github_item(self, stream: str, item_data: Dict[str, Any]) -> None:
        self._clear_inspector_badges()
        self.inspector_text.delete("1.0", tk.END)
        t = self.theme
        tk.Label(
            self.cap_summary_frame,
            text=f"GITHUB RADAR HIT [{stream}]",
            font=self.font("Segoe UI Semibold", 9),
            fg=t.accent_cyan,
            bg=t.bg_panel,
        ).pack(anchor="w")
        self.inspector_text.insert(tk.END, f"{item_data.get('repo', 'Repository')}\n", "h1")
        self.inspector_text.insert(tk.END, json.dumps(item_data, indent=2), "code")

    def _inspect_dag_node(self, node_id: str) -> None:
        self._clear_inspector_badges()
        self.inspector_text.delete("1.0", tk.END)
        if not self.current_macro_graph or node_id not in self.current_macro_graph.nodes:
            return

        t = self.theme
        node = self.current_macro_graph.nodes[node_id]
        gut = PreContactAvoidanceGate.evaluate(node_id, self.current_macro_graph)

        badge_row = tk.Frame(self.cap_summary_frame, bg=t.bg_panel)
        badge_row.pack(fill=tk.X)
        tk.Label(
            badge_row,
            text=f"Z-Score: {node['z_score']:+.2f}σ",
            font=self.font("Consolas", 8),
            fg=t.accent_cyan,
            bg=t.bg_card,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(
            badge_row,
            text=f"State: {node['state_label']}",
            font=self.font("Consolas", 8),
            fg=t.accent_gold,
            bg=t.bg_card,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=4)

        self.inspector_text.insert(tk.END, f"EGOCENTRIC FPV: {node_id}\n", "h1")
        self.inspector_text.insert(tk.END, f"{node.get('label', '')}\n\n", "muted")
        self.inspector_text.insert(
            tk.END,
            f"Current Value:     {node['current_value']} {node.get('unit', '')}\n"
            f"All-Time Extreme:  {node['abs_extreme_ratio']}%\n"
            f"Thalamic Spikes:   {node['spikes']} (Habituated: {node['habituated']})\n"
            f"Gut Avoidance:     {gut['action']} (D_gut = {gut['gut_score']:.2f})\n\n",
            "emerald" if gut["action"] == "ENGAGE" else "crimson",
        )

        self.inspector_text.insert(tk.END, "INCOMING AXONS (UPSTREAM DRIVERS):\n", "h2")
        for edge in self.current_macro_graph.adj_in.get(node_id, []):
            self.inspector_text.insert(
                tk.END,
                f"  ← {edge['source']}  (w={edge.get('weight', 0):+.2f}, lag={edge.get('lag_days', 0)}d)\n",
                "code",
            )

        self.inspector_text.insert(tk.END, "\nOUTGOING AXONS (DOWNSTREAM RIPPLES):\n", "h2")
        for edge in self.current_macro_graph.adj_out.get(node_id, []):
            self.inspector_text.insert(
                tk.END,
                f"  → {edge['target']}  (w={edge.get('weight', 0):+.2f}, lag={edge.get('lag_days', 0)}d)\n",
                "code",
            )

    def _inspect_gene_or_allele(self, gene_id: str, allele_id: Optional[str] = None) -> None:
        self._clear_inspector_badges()
        self.inspector_text.delete("1.0", tk.END)

        gene_data = self.genes_catalog.get(gene_id)
        if not gene_data:
            return

        t = self.theme
        phylo = build_gene_phylogeny(gene_data)
        target_allele = phylo["champion"]
        if allele_id:
            for a in gene_data.get("alleles", []):
                if a.get("allele_id") == allele_id:
                    target_allele = a
                    break

        tier_col = t.tier_colors.get(phylo["tier"], t.accent_cyan)

        row1 = tk.Frame(self.cap_summary_frame, bg=t.bg_panel)
        row1.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            row1,
            text=f"T{phylo['tier']} • {phylo['category'].upper()}",
            font=self.font("Consolas", 8, "bold"),
            fg=tier_col,
            bg=t.bg_card,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 4))

        if target_allele:
            t_comp = target_allele.get("complexity_time", "O(N)")
            s_comp = target_allele.get("complexity_space", "O(N)")
            tk.Label(
                row1,
                text=f"Time: {t_comp}",
                font=self.font("Consolas", 8, "bold"),
                fg=t.accent_emerald,
                bg=t.bg_card,
                padx=6,
                pady=2,
            ).pack(side=tk.LEFT, padx=2)
            tk.Label(
                row1,
                text=f"Space: {s_comp}",
                font=self.font("Consolas", 8, "bold"),
                fg=t.accent_cyan,
                bg=t.bg_card,
                padx=6,
                pady=2,
            ).pack(side=tk.LEFT, padx=2)

        self.inspector_text.insert(tk.END, f"✦ {gene_id}\n", "h1")
        self.inspector_text.insert(tk.END, f"{phylo['description']}\n\n", "muted")

        if target_allele:
            aid = target_allele.get("allele_id", "")
            dom = target_allele.get("dominance", "PRIMARY")
            self.inspector_text.insert(tk.END, f"INSPECTING ALLELE: {aid} [{dom}]\n", "gold" if dom == "PRIMARY" else "h2")

            triggers = target_allele.get("environmental_triggers", [])
            if triggers:
                self.inspector_text.insert(tk.END, "\nENVIRONMENTAL TRIGGERS & CONSTRAINTS:\n", "h2")
                self.inspector_text.insert(tk.END, "  " + "  •  ".join(str(tg) for tg in triggers) + "\n", "purple")

            invariants = target_allele.get("invariants", [])
            if invariants:
                self.inspector_text.insert(tk.END, "\nMATHEMATICAL & ALGORITHMIC INVARIANTS:\n", "h2")
                for inv in invariants:
                    self.inspector_text.insert(tk.END, f"  ✓ {inv}\n", "emerald")

            self.inspector_text.insert(tk.END, "\nEMPIRICAL ARENA FITNESS COMPARISON:\n", "h2")
            for a in gene_data.get("alleles", []):
                a_id = a.get("allele_id", "")
                fit = a.get("empirical_fitness", {})
                rt = float(fit.get("runtime_ms", 50.0))
                ram = int(fit.get("ram_kb", 2048))
                bar_len = max(2, min(20, int(rt / 4.0)))
                bar_str = "█" * bar_len
                tag = "gold" if a.get("dominance") == "PRIMARY" else "code"
                crown = "★" if a.get("dominance") == "PRIMARY" else " "
                self.inspector_text.insert(
                    tk.END, f"{crown} {a_id[:20]:<20} {bar_str} {rt:>5.1f}ms | {ram}KB\n", tag
                )

            if phylo["edges"]:
                self.inspector_text.insert(tk.END, "\nEVOLUTIONARY MUTATION LINEAGE:\n", "h2")
                for e in phylo["edges"]:
                    self.inspector_text.insert(
                        tk.END,
                        f"  {e['source_allele']} ──(+{e['operator']})──► {e['target_allele']} ({e['speedup_pct']:+.1f}% speedup)\n",
                        "emerald",
                    )

            code = target_allele.get("code_template", "")
            if code:
                self.inspector_text.insert(tk.END, "\nSEQUENCED CODE TEMPLATE & MUTATIONS:\n", "h2")
                for line in code.splitlines():
                    is_mut_line = any(
                        m_kw in line
                        for m_kw in (
                            "#pragma GCC",
                            "sync_with_stdio",
                            "cin.tie",
                            "STATIC_FLAT",
                            "sys.stdin.readline",
                            "setrecursionlimit",
                            "popleft()",
                        )
                    )
                    self.inspector_text.insert(
                        tk.END, line + "\n", "mutation_add" if is_mut_line else "code"
                    )

    # ------------------------------------------------------------------------
    # Canvas Clicks & Actions
    # ------------------------------------------------------------------------

    def _on_canvas_press(self, event: Any) -> None:
        self.pan_start = (event.x, event.y)
        self.press_pos = (event.x, event.y)
        self.is_panning = False
        self.is_node_dragging = False
        self.dragged_node_id = None

        cw = max(self.canvas.winfo_width(), 680)
        ch = max(self.canvas.winfo_height(), 500)

        # Hit test nodes in reverse order (topmost node first)
        for nid, info in reversed(list(self.canvas_nodes.items())):
            x1, y1, x2, y2 = info["bbox"]
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.dragged_node_id = nid
                # Record initial node center in world coordinates
                w_pos = info.get("world_pos")
                if not w_pos:
                    w_pos = self.s2w((x1 + x2) / 2.0, (y1 + y2) / 2.0, cw, ch)
                self.node_drag_start_world = w_pos
                self.custom_node_positions[nid] = w_pos
                break

    def _on_canvas_motion(self, event: Any) -> None:
        if not self.pan_start:
            return
        dx = event.x - self.pan_start[0]
        dy = event.y - self.pan_start[1]
        dist = math.hypot(event.x - self.press_pos[0], event.y - self.press_pos[1])

        cw = max(self.canvas.winfo_width(), 680)
        ch = max(self.canvas.winfo_height(), 500)

        if self.dragged_node_id:
            if not self.is_node_dragging and dist > 4:
                self.is_node_dragging = True
            if self.is_node_dragging:
                # Move specific node in world coordinates
                cur_wx, cur_wy = self.custom_node_positions.get(self.dragged_node_id, (640.0, 380.0))
                new_wx = cur_wx + dx / max(0.01, self.cam_zoom)
                new_wy = cur_wy + dy / max(0.01, self.cam_zoom)
                self.custom_node_positions[self.dragged_node_id] = (new_wx, new_wy)
                self.pan_start = (event.x, event.y)
                self._redraw_active_canvas()
        else:
            if not self.is_panning and dist > 4:
                self.is_panning = True
            if self.is_panning:
                # Pan entire virtual camera
                self.cam_x -= dx / max(0.01, self.cam_zoom)
                self.cam_y -= dy / max(0.01, self.cam_zoom)
                self.pan_start = (event.x, event.y)
                self._redraw_active_canvas()

    def _on_canvas_release(self, event: Any) -> None:
        dist = math.hypot(event.x - self.press_pos[0], event.y - self.press_pos[1])
        if not self.is_panning and not self.is_node_dragging and dist <= 4:
            self._handle_node_click(event.x, event.y)
        self.pan_start = None
        self.is_panning = False
        self.is_node_dragging = False
        self.dragged_node_id = None

    def _on_canvas_double_click(self, event: Any) -> None:
        """Double clicking empty canvas resets layout and camera view to default alignment."""
        for nid, info in self.canvas_nodes.items():
            x1, y1, x2, y2 = info["bbox"]
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                # Clicked on an existing node
                return
        self.reset_layout()

    def _on_pan_start(self, event: Any) -> None:
        self.pan_start = (event.x, event.y)
        self.is_panning = True

    def _on_pan_motion(self, event: Any) -> None:
        if not self.pan_start:
            return
        dx = event.x - self.pan_start[0]
        dy = event.y - self.pan_start[1]
        self.cam_x -= dx / max(0.01, self.cam_zoom)
        self.cam_y -= dy / max(0.01, self.cam_zoom)
        self.pan_start = (event.x, event.y)
        self._redraw_active_canvas()

    def _on_pan_end(self, event: Any) -> None:
        self.pan_start = None
        self.is_panning = False

    def _on_canvas_mousewheel(self, event: Any) -> None:
        cw = max(self.canvas.winfo_width(), 680)
        ch = max(self.canvas.winfo_height(), 500)
        wx, wy = self.s2w(event.x, event.y, cw, ch)

        factor = 1.15 if event.delta > 0 else (1.0 / 1.15)
        new_zoom = max(0.4, min(3.0, round(self.cam_zoom * factor, 2)))
        self.cam_zoom = new_zoom
        self.zoom_level = new_zoom

        # Keep world position (wx, wy) invariant under cursor (event.x, event.y)
        self.cam_x = wx - (event.x - cw / 2.0) / self.cam_zoom
        self.cam_y = wy - (event.y - ch / 2.0) / self.cam_zoom

        pct_str = f"{int(self.cam_zoom * 100)}%"
        self.btn_zoom_reset.configure(text=pct_str)
        self.lbl_footer_zoom.configure(text=f"Zoom: {pct_str} (Ctrl+= / Ctrl+- / Ctrl+0)")
        self._redraw_active_canvas()

    def _handle_node_click(self, cx: float, cy: float) -> None:
        for nid, info in self.canvas_nodes.items():
            x1, y1, x2, y2 = info["bbox"]
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                self.selected_node_id = nid
                payload = info["payload"]
                ptype = payload.get("type")

                if ptype == "pipeline_stage":
                    self._inspect_pipeline_stage(payload["id"])
                elif ptype == "dag_node":
                    self._inspect_dag_node(payload["id"])
                elif ptype == "gene_root":
                    self.selected_allele_id = None
                    self._inspect_gene_or_allele(payload["gene_id"], None)
                elif ptype == "allele":
                    self.selected_allele_id = payload["allele_id"]
                    self._inspect_gene_or_allele(payload["gene_id"], payload["allele_id"])
                elif ptype == "universe_status":
                    self._inspect_dag_node(payload.get("meta", {}).get("top_chokepoint", payload["universe_id"]))
                elif ptype == "ingestion_funnel":
                    self._inspect_pipeline_stage("STAGE_ULTIMATRIX")
                elif ptype == "trigger_mutate":
                    self._trigger_mutate_selected_gene()

                self._redraw_active_canvas()
                break

    def _on_canvas_click(self, event: Any) -> None:
        """Backward-compatible click handler for unit tests."""
        self._handle_node_click(event.x, event.y)

    def _on_contextual_inspector_action(self) -> None:
        if self.active_view == "pipeline":
            self._trigger_github_scan()
        elif self.active_view == "dag":
            self._trigger_shock_simulation()
        elif self.active_view == "genes":
            self._trigger_mutate_selected_gene()

    def _on_parameter_tuned(self) -> None:
        if self.active_view == "dag":
            self._load_selected_cartridge()
        self._populate_left_panel()
        self._redraw_active_canvas()

    def _spawn_pulse_wave(self, color: str = "#06b6d4", count: int = 8) -> None:
        keys = list(self.canvas_nodes.keys())
        if len(keys) < 2:
            return
        for i in range(min(count, len(keys) - 1)):
            c1 = self.canvas_nodes[keys[i]]["center"]
            c2 = self.canvas_nodes[keys[(i + 1) % len(keys)]]["center"]
            self.pulses.append({
                "x1": c1[0],
                "y1": c1[1],
                "x2": c2[0],
                "y2": c2[1],
                "progress": (i * 0.12) % 1.0,
                "speed": 0.035,
                "color": color,
            })

    def _run_background_job(self, job_title: str, pulse_color: str, target_fn: Callable[[], None]) -> None:
        if self.is_job_running:
            return
        self.is_job_running = True
        self.active_job_label = job_title
        self.lbl_footer_job.configure(text=f"⚡ EXECUTING: {job_title}...", fg=pulse_color)
        self._spawn_pulse_wave(color=pulse_color, count=12)

        def worker():
            try:
                target_fn()
            except Exception as e:
                logger.error(f"Background job error ({job_title}): {e}")
            finally:
                self.root.after(0, self._on_background_job_complete)

        threading.Thread(target=worker, daemon=True).start()

    def _on_background_job_complete(self) -> None:
        self.is_job_running = False
        self.active_job_label = "IDLE — Monitoring Telemetry"
        self.lbl_footer_job.configure(
            text="● Status: IDLE — Work Complete & Ledgers Synchronized (60 FPS)", fg=self.theme.accent_emerald
        )
        self._reload_all_telemetry()
        self._populate_left_panel()
        self._redraw_active_canvas()
        if self.active_view == "genes" and self.selected_gene_id:
            self._inspect_gene_or_allele(self.selected_gene_id, self.selected_allele_id)

    def _trigger_github_scan(self) -> None:
        def job():
            self.gh_sensor.get_cached_telemetry(force_refresh=True)

        self._run_background_job("4-Stream GitHub Sensory Radar Scan (30-PAT Pool)", self.theme.accent_cyan, job)

    def _trigger_macro_synthesis(self) -> None:
        def job():
            self._load_selected_cartridge()
            if self.current_macro_graph:
                engine = ForesightAlphaEngine(
                    self.current_macro_graph, self.current_cartridge_raw.get("engrams", [])
                )
                brief = engine.generate_brief()
                STATE_DIR.mkdir(parents=True, exist_ok=True)
                MACRO_BRIEF_JSON.write_text(json.dumps(brief, indent=2), encoding="utf-8")

        self._run_background_job("U0-U5 Neuromorphic Causal Synthesis", self.theme.accent_blue, job)

    def _trigger_shock_simulation(self) -> None:
        if not self.current_macro_graph:
            return
        target = self.selected_node_id
        if not target or target not in self.current_macro_graph.nodes:
            target = next(iter(self.current_macro_graph.nodes.keys()), None)
        if not target:
            return

        shock_res = self.current_macro_graph.simulate_shock(target, magnitude=2.0)
        self.shock_overlay.clear()
        self.shock_overlay[target] = 2.0
        for aff in shock_res.get("affected_targets", []):
            self.shock_overlay[aff["target"]] = float(aff["impact_score"])

        self._spawn_pulse_wave(color=self.theme.accent_gold, count=14)
        self._redraw_active_canvas()
        self.inspector_text.insert(tk.END, f"\n⚡ SHOCK PROPAGATION (+2.0σ on {target}):\n", "gold")
        for aff in shock_res.get("affected_targets", []):
            self.inspector_text.insert(
                tk.END,
                f"  → {aff['target']:<18} Impact: {aff['impact_score']:+.3f} (Lag: {aff['arrival_lag_days']}d)\n",
                "emerald",
            )

    def _trigger_mutate_selected_gene(self) -> None:
        if self.active_view != "genes":
            self.switch_view("genes")
        gid = self.selected_gene_id
        if not gid:
            return

        def job():
            g_file = find_gene_file_on_disk(gid)
            if g_file:
                mutate_gene_file(g_file)
            else:
                g_data = self.genes_catalog.get(gid)
                if g_data and CODON_STREAM.exists():
                    tier = int(g_data.get("tier", 2))
                    tier_folders = {
                        0: "tier0_hardware",
                        1: "tier1_language",
                        2: "tier2_primitives",
                        3: "tier3_cubic_breakers",
                        4: "tier4_symbolic",
                        5: "tier5_super_domain",
                    }
                    t_dir = CODON_STREAM / tier_folders.get(tier, "tier2_primitives")
                    t_dir.mkdir(parents=True, exist_ok=True)
                    new_path = t_dir / f"{gid.lower()}.json"
                    new_path.write_text(json.dumps(g_data, indent=2), encoding="utf-8")
                    mutate_gene_file(new_path)

        self._run_background_job(f"Ultimatrix Mutation & Arena Race [{gid}]", self.theme.accent_purple, job)

    def _trigger_harvest_task(self) -> None:
        self._run_background_job("Harvesting CP Task", self.theme.accent_emerald, harvest_single_task)

    def _trigger_full_cycle(self) -> None:
        self._run_background_job("Full Sentinel Verification Cycle", self.theme.accent_gold, execute_cycle)

    def _trigger_colab_cloud_burst(self) -> None:
        """Launches the A100 High-RAM Cloud Hyper-Burst in background thread."""
        def job():
            import subprocess
            cmd = [sys.executable, str(ROOT / "tools" / "azmuth_colab_burst.py"), "--tier", "a100-highmem", "--sync-drive"]
            logger.info(f"Executing Cloud Hyper-Burst: {' '.join(cmd)}")
            res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
            if res.returncode != 0:
                logger.error(f"Cloud Hyper-Burst returned error: {res.stderr}")
            else:
                logger.info(f"Cloud Hyper-Burst completed successfully:\n{res.stdout[-1000:]}")

        self._run_background_job("A100-SXM4-80GB High-RAM Cloud Hyper-Burst", self.theme.accent_crimson, job)

    def _load_recent_ingestion_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """Loads latest ingestion events from azmuth_ingestion_feed.jsonl in reverse chronological order."""
        if not INGESTION_FEED.exists():
            return []
        try:
            lines = INGESTION_FEED.read_text(encoding="utf-8").splitlines()
            events = []
            for line in reversed(lines):
                if line.strip():
                    try:
                        events.append(json.loads(line))
                        if len(events) >= limit:
                            break
                    except Exception:
                        pass
            return events
        except Exception:
            return []

    def _inspect_ingestion_event(self, event_data: dict[str, Any]) -> None:
        """Renders rich details of an ingestion/activity event into the right inspector."""
        self._clear_inspector_badges()
        self.inspector_text.delete("1.0", tk.END)
        t = self.theme

        etype = event_data.get("event_type", "EVENT")
        src = event_data.get("source", "System")
        title = event_data.get("title", "")
        ts = event_data.get("timestamp", "")
        status = event_data.get("status", "SUCCESS")
        details = event_data.get("details", {})

        row1 = tk.Frame(self.cap_summary_frame, bg=t.bg_panel)
        row1.pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            row1,
            text=f"TYPE: {etype}",
            font=self.font("Consolas", 8, "bold"),
            fg=t.accent_emerald if status == "SUCCESS" else t.accent_amber,
            bg=t.bg_card,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(
            row1,
            text=f"SRC: {src}",
            font=self.font("Consolas", 8),
            fg=t.accent_cyan,
            bg=t.bg_card,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=2)

        self.inspector_text.insert(tk.END, f"ACTIVITY INGESTION EVENT\n", "h1")
        self.inspector_text.insert(tk.END, f"{title}\n\n", "h2")
        self.inspector_text.insert(
            tk.END,
            f"Timestamp:   {ts}\n"
            f"Source Engine: {src}\n"
            f"Status:      {status}\n\n",
            "gold" if status == "SUCCESS" else "crimson",
        )

        self.inspector_text.insert(tk.END, "STRUCTURED EVENT PAYLOAD & METRICS:\n", "h2")
        formatted_json = json.dumps(details, indent=2)
        self.inspector_text.insert(tk.END, f"{formatted_json}\n", "code")

    def _on_select_gear(self, gear_name: str) -> None:
        set_current_gear(gear_name, reason="Azmuth Command Center GUI")
        self._refresh_header_indicators()

    def _on_toggle_pause(self) -> None:
        set_paused(not is_paused(), reason="Azmuth Command Center GUI")
        self._refresh_header_indicators()

    # ------------------------------------------------------------------------
    # 60FPS Animation Loop
    # ------------------------------------------------------------------------

    def _draw_active_pulses(self) -> None:
        self.canvas.delete("pulse_particle")
        remaining = []
        t = self.theme
        pr = max(3, int(4 * self.zoom_level))
        for p in self.pulses:
            p["progress"] += p["speed"]
            if p["progress"] < 1.0:
                prog = p["progress"]
                px = p["x1"] + (p["x2"] - p["x1"]) * prog
                py = p["y1"] + (p["y2"] - p["y1"]) * prog
                col = p["color"]
                self.canvas.create_oval(
                    px - pr, py - pr, px + pr, py + pr, fill=col, outline=t.text_primary, width=1, tags="pulse_particle"
                )
                remaining.append(p)
            elif self.is_job_running:
                p["progress"] = 0.0
                remaining.append(p)
        self.pulses = remaining

    def _draw_oscilloscope(self) -> None:
        self.osc_canvas.delete("all")
        w = self.osc_canvas.winfo_width()
        h = self.osc_canvas.winfo_height()
        if w < 10 or h < 10:
            w, h = 170, 28
        t = self.theme

        total_gb, avail_gb, load_pct = get_memory_status_gb()
        breaker_gb = float(self.ram_circuit_limit_gb.get())
        breaker_ratio = min(max(1.0 - (breaker_gb / max(total_gb, 1.0)), 0.1), 0.95)
        by = h * (1.0 - breaker_ratio)
        self.osc_canvas.create_line(0, by, w, by, fill=t.accent_crimson, dash=(2, 2), width=1)

        pts = []
        n = len(self.ram_history)
        for i, val in enumerate(self.ram_history):
            x = (i / max(n - 1, 1)) * w
            jitter = math.sin((self.anim_tick + i) * 0.25) * (2.2 if self.is_job_running else 0.5)
            y = h - ((min(max(val + jitter, 5.0), 98.0) / 100.0) * (h - 4)) - 2
            pts.extend([x, y])

        line_col = t.accent_crimson if avail_gb < breaker_gb else (t.accent_gold if self.is_job_running else t.accent_cyan)
        if len(pts) >= 4:
            self.osc_canvas.create_line(*pts, fill=line_col, width=1.5, smooth=True)

    def _schedule_animation_frame(self) -> None:
        if not self._running:
            return
        self.anim_tick += 1
        self._draw_oscilloscope()
        if self.pulses or self.is_job_running:
            self._draw_active_pulses()
        self.root.after(16, self._schedule_animation_frame)

    def _refresh_header_indicators(self) -> None:
        gear = get_current_gear()
        paused = is_paused()
        total_gb, avail_gb, load_pct = get_memory_status_gb()
        t = self.theme

        self.ram_history.append(float(load_pct))
        self.ram_history = self.ram_history[-80:]
        self.lbl_ram_readout.configure(
            text=f"{avail_gb:.1f} GB Free ({load_pct}%)",
            fg=t.accent_crimson if avail_gb < self.ram_circuit_limit_gb.get() else t.accent_cyan,
        )

        self.status_dot.itemconfig("dot", fill=t.accent_amber if paused else t.accent_emerald)
        self.btn_pause.configure(
            text="▶ Resume" if paused else "⏸ Pause",
            bg=t.accent_amber if paused else t.bg_card,
            fg=t.bg_void if paused else t.text_secondary,
        )

        gear_colors = {"whisper": t.accent_emerald, "balanced": t.accent_blue, "turbo": t.accent_crimson}
        for g_key, btn in self.gear_buttons.items():
            if g_key == gear:
                btn.configure(bg=gear_colors.get(g_key, t.accent_blue), fg=t.text_primary)
            else:
                btn.configure(bg=t.bg_card, fg=t.text_secondary)

        ready_toks = sum(1 for tok in self.gh_sensor.pool.tokens if tok.get("status") == "READY")
        self.kpi_labels["pat_pool"].configure(text=f"{ready_toks} / {len(self.gh_sensor.pool.tokens)} Ready")
        self.kpi_labels["genes"].configure(text=f"{len(self.genes_catalog)} Loci")
        self.kpi_labels["mutations"].configure(text=f"{self.mutation_ledger_data.get('mutations_applied', 0)}")
        self.kpi_labels["arena"].configure(text=f"{self.arena_ledger_data.get('tournaments_run', 0)}")

    def _schedule_telemetry_poll(self) -> None:
        if not self._running:
            return
        try:
            check_and_enforce_gear_safety()
            self._refresh_header_indicators()
        except Exception:
            pass
        self.root.after(2000, self._schedule_telemetry_poll)

    def _on_close(self) -> None:
        self._running = False
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = AzmuthCommandCenterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
