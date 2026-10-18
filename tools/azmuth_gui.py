#!/usr/bin/env python3
"""tools/azmuth_gui.py
---------------------
Azmuth Autonomous Neuromorphic Command Center & Phylogenetic Gene Explorer.

Industry-grade, zero-browser-overhead native desktop GUI (Win32 High-DPI + 60FPS Canvas):
1. Unified Mission Control Layout:
   - Top Telemetry & Operator Tuning Bar: Live Gear switcher (Whisper / Balanced / Turbo),
     60FPS RAM Oscilloscope Sparkline with tunable Circuit-Breaker line, 30-PAT Token Ring summary,
     live Thalamic |Z|-score threshold tuner, and 1-click execution triggers.
2. Switchable 60FPS Visual Graph Canvas:
   - [1] End-to-End Pipeline Flow: 4 Sensory Streams -> 30-PAT Rotating Ring -> Thalamic Z-Score Sieve
         -> U0-U5 Cortical Brain -> Ultimatrix Gene Sequencer -> SSOT Ledgers.
   - [2] U0-U5 Neuromorphic Causal DAG: Swappable cortical cartridges (U0..U5), live Z-score node coloring,
         axonal synapse weights/lags, Egocentric First-Person View (FPV), and interactive Multi-Hop Shock propagation.
   - [3] Gene Lab & Phylogenetic Evolution Tree: Tier 0-5 taxonomy browser (349+ genes), branching
         Wild-Type -> Mutator Edge (+fast_io, +pragma_tuning, +bitwise_unrolling, +stdlib_accel) ->
         Daughter Allele -> Ultimatrix Arena PRIMARY Champion tree, plus live "Mutate & Battle Now" execution.
3. Right Interactive Node & Gene Capability Inspector:
   - Displays Time/Space Big-O complexity bounds, Environmental Triggers, Mathematical Invariants,
     Empirical Fitness (ms / KB) bars, and Code Template / Mutation Diff viewer.
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

# Hide console window immediately if launched via python.exe on Windows, and protect pythonw.exe stdio
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
RUN_LOG_JSON = STATE_DIR / "azmuth_run.json"

# --- Calibrated Linear / Oscilloscope Dark Palette ---
BG_VOID = "#090b0e"
BG_MAIN = "#0d0f14"
BG_PANEL = "#12151c"
BG_CARD = "#171b24"
BG_CARD_HOVER = "#1e2430"
BG_INPUT = "#0f1218"

BORDER_SUBTLE = "#222834"
BORDER_ACTIVE = "#384152"

TEXT_PRIMARY = "#f3f4f6"
TEXT_SECONDARY = "#cbd5e1"
TEXT_MUTED = "#64748b"

ACCENT_CYAN = "#06b6d4"
ACCENT_BLUE = "#3b82f6"
ACCENT_EMERALD = "#10b981"
ACCENT_AMBER = "#f59e0b"
ACCENT_CRIMSON = "#ef4444"
ACCENT_PURPLE = "#a855f7"
ACCENT_GOLD = "#eab308"

TIER_COLORS = {
    0: "#f43f5e",  # T0 Hardware Substrate (Rose/Crimson)
    1: "#f59e0b",  # T1 Language Runtime (Amber)
    2: "#06b6d4",  # T2 Primitives & Structures (Cyan)
    3: "#a855f7",  # T3 Cubic Breakers (Purple)
    4: "#10b981",  # T4 Symbolic & Frontier (Emerald)
    5: "#eab308",  # T5 Super-Domain Foresight (Gold)
}

TIER_NAMES = {
    0: "T0: Hardware Substrate",
    1: "T1: Language Runtime",
    2: "T2: Primitives & Structures",
    3: "T3: Dimensional / Cubic Breakers",
    4: "T4: Symbolic & CAS Frontier",
    5: "T5: Super-Domain Foresight",
}

FONT_BRAND = ("Segoe UI Semibold", 12)
FONT_TITLE = ("Segoe UI Semibold", 10)
FONT_SUBTITLE = ("Segoe UI Semibold", 9)
FONT_BODY = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO = ("Consolas", 9)
FONT_MONO_SMALL = ("Consolas", 8)
FONT_KPI = ("Segoe UI Semibold", 14)


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


def enable_win32_dpi_and_dark_bar(root: Optional[tk.Tk] = None) -> None:
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
        try:
            root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            if not hwnd:
                hwnd = root.winfo_id()
            for attr in (20, 19):
                val = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)
                )
        except Exception:
            pass


# ============================================================================
# Pure Data & Lineage Builders (Testable Headlessly)
# ============================================================================

def build_gene_phylogeny(gene_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs a structured Two-Level Phylogenetic Evolution Tree from a gene dictionary.
    Identifies:
      - Wild-type / root alleles (no '_mut_' in allele_id)
      - Mutated daughter alleles ('<parent>_mut_<operator>')
      - Operator edges (+fast_io, +pragma_tuning, +static_memory, +bitwise_unrolling, +python_stdlib_accel)
      - Dominant PRIMARY champion & fitness speedup metrics
    """
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

    # If all alleles happen to have _mut_ (edge case), treat the first as root
    if not wild_types and alleles:
        wild_types.append(alleles[0])
        mutants = alleles[1:]

    # Link mutants to their parent wild-type allele
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

    # Identify overall champion
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

    # Calculate best speedup across the gene
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
# Main GUI Application
# ============================================================================

class AzmuthCommandCenterGUI:
    """Industry-Grade Native Desktop Command Center & Visual Flow Graph for Azmuth."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Azmuth Autonomous Neuromorphic Command Center — Foresight & Ultimatrix Gene Lab")
        self.root.geometry("1480x900")
        self.root.minsize(1240, 760)
        self.root.configure(bg=BG_MAIN)

        enable_win32_dpi_and_dark_bar(self.root)

        # Runtime State & Tunable Parameters
        self.active_view: str = "pipeline"  # "pipeline" | "dag" | "genes"
        self.thalamic_z_threshold: tk.DoubleVar = tk.DoubleVar(value=0.80)
        self.ram_circuit_limit_gb: tk.DoubleVar = tk.DoubleVar(value=3.00)
        self.search_query_var: tk.StringVar = tk.StringVar(value="")
        self.selected_tier_filter: int = -1  # -1 = All Tiers

        # Live Telemetry Buffers
        self.ram_history: List[float] = [50.0] * 80
        self.avail_gb_history: List[float] = [8.0] * 80
        self.active_job_label: str = "IDLE — Monitoring Telemetry"
        self.is_job_running: bool = False

        # Animation & Particle State (60 FPS)
        self.anim_tick: int = 0
        self.pulses: List[Dict[str, Any]] = []
        self.canvas_nodes: Dict[str, Dict[str, Any]] = {}
        self.selected_node_id: Optional[str] = None

        # Cached Subsystem Data
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

        # Load initial data
        self._reload_all_telemetry()

        # Build UI Layout
        self._configure_ttk_styles()
        self._build_top_telemetry_bar()
        self._build_tuning_and_action_bar()
        self._build_main_workspace()
        self._build_status_footer()

        # Populate initial view
        self.switch_view("pipeline")

        # Start 60FPS Canvas Animation Loop & 2s Telemetry Poller
        self._running = True
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_animation_frame()
        self._schedule_telemetry_poll()

    # ------------------------------------------------------------------------
    # Data Loading & Synchronization
    # ------------------------------------------------------------------------

    def _reload_all_telemetry(self) -> None:
        """Loads latest JSON state from orchestrator-state and codon_stream."""
        # 1. GitHub Sensor Cache
        if GH_CACHE_FILE.exists():
            try:
                self.gh_cache_data = json.loads(GH_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.gh_cache_data = {}

        # 2. Ledgers
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

        # 3. Cortical Cartridge
        self._load_selected_cartridge()

        # 4. Genes Catalog
        try:
            self.genes_catalog = load_all_genes()
            if not self.selected_gene_id and self.genes_catalog:
                # Pick a gene that has multiple alleles or mutations by default for rich visual tree
                for gid, gdata in self.genes_catalog.items():
                    if any("_mut_" in a.get("allele_id", "") for a in gdata.get("alleles", [])):
                        self.selected_gene_id = gid
                        break
                if not self.selected_gene_id:
                    self.selected_gene_id = sorted(self.genes_catalog.keys())[0]
        except Exception as e:
            logger.debug(f"Error loading genes: {e}")

    def _load_selected_cartridge(self) -> None:
        """Loads and normalizes the active U0..U5 cartridge using current Thalamic threshold."""
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
    # UI Construction
    # ------------------------------------------------------------------------

    def _configure_ttk_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Vertical.TScrollbar",
            background=BG_CARD,
            troughcolor=BG_PANEL,
            bordercolor=BG_PANEL,
            arrowcolor=TEXT_MUTED,
        )

    def _build_top_telemetry_bar(self) -> None:
        """Constructs the top telemetry header with Gear switcher, RAM oscilloscope, and KPIs."""
        header = tk.Frame(self.root, bg=BG_PANEL, height=74, highlightthickness=1, highlightbackground=BORDER_SUBTLE)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        # 1. Brand & Engine Status
        brand_frame = tk.Frame(header, bg=BG_PANEL, padx=14)
        brand_frame.pack(side=tk.LEFT, fill=tk.Y)

        title_row = tk.Frame(brand_frame, bg=BG_PANEL)
        title_row.pack(anchor="w", pady=(12, 2))

        self.status_dot = tk.Canvas(title_row, width=12, height=12, bg=BG_PANEL, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 8))
        self.status_dot.create_oval(2, 2, 10, 10, fill=ACCENT_EMERALD, outline="", tags="dot")

        tk.Label(
            title_row,
            text="AZMUTH NEUROMORPHIC CORE",
            font=FONT_BRAND,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(side=tk.LEFT)

        self.lbl_engine_sub = tk.Label(
            brand_frame,
            text="U0-U5 Foresight • 30-PAT Sensory Radar • Ultimatrix Gene Lab",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL,
        )
        self.lbl_engine_sub.pack(anchor="w")

        # Divider
        tk.Frame(header, bg=BORDER_SUBTLE, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=10)

        # 2. Live Gear Selector Pills
        gear_frame = tk.Frame(header, bg=BG_PANEL, padx=12)
        gear_frame.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(gear_frame, text="DAEMON GEAR & STATE", font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_PANEL).pack(
            anchor="w", pady=(10, 4)
        )
        btn_row = tk.Frame(gear_frame, bg=BG_PANEL)
        btn_row.pack(anchor="w")

        self.gear_buttons: Dict[str, tk.Button] = {}
        for g_key, g_label in [("whisper", "🌱 Whisper"), ("balanced", "⚡ Balanced"), ("turbo", "🚀 Turbo")]:
            b = tk.Button(
                btn_row,
                text=g_label,
                font=FONT_SMALL,
                bg=BG_CARD,
                fg=TEXT_SECONDARY,
                activebackground=ACCENT_BLUE,
                activeforeground=TEXT_PRIMARY,
                relief=tk.FLAT,
                padx=8,
                pady=3,
                cursor="hand2",
                command=lambda k=g_key: self._on_select_gear(k),
            )
            b.pack(side=tk.LEFT, padx=(0, 4))
            self.gear_buttons[g_key] = b

        self.btn_pause = tk.Button(
            btn_row,
            text="⏸ Pause",
            font=FONT_SMALL,
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._on_toggle_pause,
        )
        self.btn_pause.pack(side=tk.LEFT, padx=(4, 0))

        tk.Frame(header, bg=BORDER_SUBTLE, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=10)

        # 3. 60FPS RAM Oscilloscope & Circuit Breaker Sparkline
        osc_frame = tk.Frame(header, bg=BG_PANEL, padx=12)
        osc_frame.pack(side=tk.LEFT, fill=tk.Y)

        osc_top = tk.Frame(osc_frame, bg=BG_PANEL)
        osc_top.pack(fill=tk.X, pady=(8, 2))
        tk.Label(osc_top, text="RAM OSCILLOSCOPE", font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_PANEL).pack(side=tk.LEFT)
        self.lbl_ram_readout = tk.Label(
            osc_top, text="8.0 GB Free (50%)", font=FONT_MONO_SMALL, fg=ACCENT_CYAN, bg=BG_PANEL
        )
        self.lbl_ram_readout.pack(side=tk.RIGHT, padx=(8, 0))

        self.osc_canvas = tk.Canvas(
            osc_frame, width=190, height=34, bg=BG_VOID, highlightthickness=1, highlightbackground=BORDER_SUBTLE
        )
        self.osc_canvas.pack()

        tk.Frame(header, bg=BORDER_SUBTLE, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=10)

        # 4. KPI Telemetry Cards
        kpi_container = tk.Frame(header, bg=BG_PANEL, padx=10)
        kpi_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.kpi_labels: Dict[str, tk.Label] = {}
        kpis = [
            ("pat_pool", "GITHUB PAT POOL", f"{len(self.gh_sensor.pool.tokens)} / 30 Ready", ACCENT_CYAN),
            ("genes", "GENES SEQUENCED", f"{len(self.genes_catalog)} Loci", ACCENT_PURPLE),
            ("mutations", "MUTATIONS APPLIED", f"{self.mutation_ledger_data.get('mutations_applied', 0)}", ACCENT_EMERALD),
            ("arena", "ARENA BATTLES", f"{self.arena_ledger_data.get('tournaments_run', 0)} Races", ACCENT_GOLD),
        ]
        for k_id, k_title, k_val, k_color in kpis:
            card = tk.Frame(kpi_container, bg=BG_CARD, padx=12, pady=6, highlightthickness=1, highlightbackground=BORDER_SUBTLE)
            card.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=10)
            tk.Label(card, text=k_title, font=("Segoe UI", 7), fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
            lbl = tk.Label(card, text=k_val, font=FONT_TITLE, fg=k_color, bg=BG_CARD)
            lbl.pack(anchor="w", pady=(2, 0))
            self.kpi_labels[k_id] = lbl

    def _build_tuning_and_action_bar(self) -> None:
        """Constructs the operator parameter tuning bar and view mode switcher."""
        bar = tk.Frame(self.root, bg=BG_CARD, height=46, highlightthickness=1, highlightbackground=BORDER_SUBTLE)
        bar.pack(fill=tk.X, side=tk.TOP)
        bar.pack_propagate(False)

        # View Switcher Tabs (Left)
        view_frame = tk.Frame(bar, bg=BG_CARD, padx=10)
        view_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.view_buttons: Dict[str, tk.Button] = {}
        views = [
            ("pipeline", "1 • Pipeline & PAT Flow"),
            ("dag", "2 • U0–U5 Causal DAG"),
            ("genes", "3 • Gene Lab & Evolution Tree"),
        ]
        for v_id, v_text in views:
            btn = tk.Button(
                view_frame,
                text=v_text,
                font=FONT_SUBTITLE,
                bg=BG_PANEL,
                fg=TEXT_SECONDARY,
                relief=tk.FLAT,
                padx=12,
                pady=5,
                cursor="hand2",
                command=lambda v=v_id: self.switch_view(v),
            )
            btn.pack(side=tk.LEFT, padx=3, pady=7)
            self.view_buttons[v_id] = btn

        tk.Frame(bar, bg=BORDER_SUBTLE, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8, padx=4)

        # Live Parameter Tuning Controls (Middle)
        tune_frame = tk.Frame(bar, bg=BG_CARD, padx=6)
        tune_frame.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(tune_frame, text="Thalamic |Z| Gate:", font=FONT_SMALL, fg=TEXT_SECONDARY, bg=BG_CARD).pack(
            side=tk.LEFT, padx=(4, 2)
        )
        self.spin_z = tk.Spinbox(
            tune_frame,
            from_=0.1,
            to=3.0,
            increment=0.1,
            textvariable=self.thalamic_z_threshold,
            width=5,
            font=FONT_MONO_SMALL,
            bg=BG_INPUT,
            fg=ACCENT_CYAN,
            buttonbackground=BG_PANEL,
            relief=tk.FLAT,
            command=self._on_parameter_tuned,
        )
        self.spin_z.pack(side=tk.LEFT, padx=(0, 10))
        self.spin_z.bind("<Return>", lambda e: self._on_parameter_tuned())

        tk.Label(tune_frame, text="RAM Breaker (GB):", font=FONT_SMALL, fg=TEXT_SECONDARY, bg=BG_CARD).pack(
            side=tk.LEFT, padx=(4, 2)
        )
        self.spin_ram = tk.Spinbox(
            tune_frame,
            from_=1.5,
            to=8.0,
            increment=0.5,
            textvariable=self.ram_circuit_limit_gb,
            width=5,
            font=FONT_MONO_SMALL,
            bg=BG_INPUT,
            fg=ACCENT_AMBER,
            buttonbackground=BG_PANEL,
            relief=tk.FLAT,
            command=self._on_parameter_tuned,
        )
        self.spin_ram.pack(side=tk.LEFT, padx=(0, 10))

        # Action Triggers (Right)
        act_frame = tk.Frame(bar, bg=BG_CARD, padx=10)
        act_frame.pack(side=tk.RIGHT, fill=tk.Y)

        actions = [
            ("📡 Scan GitHub", ACCENT_CYAN, self._trigger_github_scan),
            ("🧠 Synthesize DAG", ACCENT_BLUE, self._trigger_macro_synthesis),
            ("🧬 Mutate & Battle", ACCENT_PURPLE, self._trigger_mutate_selected_gene),
            ("📥 Harvest Task", ACCENT_EMERALD, self._trigger_harvest_task),
            ("🔄 Verify Cycle", ACCENT_GOLD, self._trigger_full_cycle),
        ]
        for label, color, cmd in actions:
            b = tk.Button(
                act_frame,
                text=label,
                font=FONT_SMALL,
                bg=BG_PANEL,
                fg=color,
                activebackground=color,
                activeforeground=BG_VOID,
                highlightthickness=1,
                highlightbackground=color,
                relief=tk.FLAT,
                padx=9,
                pady=4,
                cursor="hand2",
                command=cmd,
            )
            b.pack(side=tk.LEFT, padx=3, pady=8)

    def _build_main_workspace(self) -> None:
        """Constructs the 3-column Mission Control workspace: Left Browser, Central 60FPS Canvas, Right Inspector."""
        workspace = tk.Frame(self.root, bg=BG_MAIN)
        workspace.pack(fill=tk.BOTH, expand=True)

        # 1. Left Sidebar (Taxonomy / Sensory Streams / Cartridge Selector)
        self.left_panel = tk.Frame(
            workspace, bg=BG_PANEL, width=300, highlightthickness=1, highlightbackground=BORDER_SUBTLE
        )
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)

        self.left_header_lbl = tk.Label(
            self.left_panel,
            text="SENSORY & GENOMIC EXPLORER",
            font=FONT_SUBTITLE,
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            anchor="w",
            padx=12,
            pady=8,
        )
        self.left_header_lbl.pack(fill=tk.X)

        # Search & Filter Box inside Left Panel
        self.left_filter_frame = tk.Frame(self.left_panel, bg=BG_PANEL, padx=8, pady=6)
        self.left_filter_frame.pack(fill=tk.X)

        search_entry = tk.Entry(
            self.left_filter_frame,
            textvariable=self.search_query_var,
            font=FONT_BODY,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT_CYAN,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER_ACTIVE,
        )
        search_entry.pack(fill=tk.X, ipady=4)
        self.search_query_var.trace_add("write", lambda *_: self._populate_left_panel())

        # Tier filter pills row (used in Gene Lab view)
        self.tier_filter_row = tk.Frame(self.left_panel, bg=BG_PANEL, padx=6, pady=2)
        self.tier_filter_row.pack(fill=tk.X)
        self.tier_pill_btns: Dict[int, tk.Button] = {}
        for t_idx, t_short in [(-1, "ALL"), (0, "T0"), (1, "T1"), (2, "T2"), (3, "T3"), (4, "T4"), (5, "T5")]:
            tb = tk.Button(
                self.tier_filter_row,
                text=t_short,
                font=("Consolas", 8, "bold"),
                bg=BG_CARD,
                fg=TIER_COLORS.get(t_idx, TEXT_SECONDARY),
                relief=tk.FLAT,
                padx=5,
                pady=2,
                cursor="hand2",
                command=lambda ti=t_idx: self._set_tier_filter(ti),
            )
            tb.pack(side=tk.LEFT, padx=1, expand=True, fill=tk.X)
            self.tier_pill_btns[t_idx] = tb

        # Scrollable Listbox for Left Items
        list_container = tk.Frame(self.left_panel, bg=BG_PANEL, padx=6, pady=4)
        list_container.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL)
        self.left_listbox = tk.Listbox(
            list_container,
            bg=BG_VOID,
            fg=TEXT_SECONDARY,
            selectbackground=ACCENT_BLUE,
            selectforeground=TEXT_PRIMARY,
            font=FONT_MONO_SMALL,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            activestyle="none",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.left_listbox.yview)
        self.left_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.left_listbox.bind("<<ListboxSelect>>", self._on_left_list_select)
        self.left_items_meta: List[Dict[str, Any]] = []

        # 2. Right Panel (Interactive Node & Gene Capability Inspector)
        self.right_panel = tk.Frame(
            workspace, bg=BG_PANEL, width=395, highlightthickness=1, highlightbackground=BORDER_SUBTLE
        )
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)

        right_hdr = tk.Frame(self.right_panel, bg=BG_CARD)
        right_hdr.pack(fill=tk.X)
        self.right_title_lbl = tk.Label(
            right_hdr,
            text="CAPABILITY & NODE INSPECTOR",
            font=FONT_SUBTITLE,
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            anchor="w",
            padx=12,
            pady=8,
        )
        self.right_title_lbl.pack(side=tk.LEFT)

        self.btn_contextual_action = tk.Button(
            right_hdr,
            text="⚡ Action",
            font=FONT_SMALL,
            bg=ACCENT_PURPLE,
            fg=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._on_contextual_inspector_action,
        )
        self.btn_contextual_action.pack(side=tk.RIGHT, padx=8, pady=6)

        # Structured Capability Badges Area
        self.cap_summary_frame = tk.Frame(self.right_panel, bg=BG_PANEL, padx=10, pady=8)
        self.cap_summary_frame.pack(fill=tk.X)

        # Syntax-styled Inspector Text / Code Template / Telemetry View
        insp_text_frame = tk.Frame(self.right_panel, bg=BG_PANEL, padx=10, pady=4)
        insp_text_frame.pack(fill=tk.BOTH, expand=True)

        insp_scroll = ttk.Scrollbar(insp_text_frame, orient=tk.VERTICAL)
        self.inspector_text = tk.Text(
            insp_text_frame,
            bg=BG_VOID,
            fg=TEXT_SECONDARY,
            font=FONT_MONO_SMALL,
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=10,
            pady=8,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            yscrollcommand=insp_scroll.set,
        )
        insp_scroll.config(command=self.inspector_text.yview)
        self.inspector_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        insp_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure text highlight tags for code, diffs, and capabilities
        self.inspector_text.tag_configure("h1", font=("Segoe UI Semibold", 10), foreground=TEXT_PRIMARY)
        self.inspector_text.tag_configure("h2", font=("Segoe UI Semibold", 9), foreground=ACCENT_CYAN)
        self.inspector_text.tag_configure("gold", foreground=ACCENT_GOLD, font=("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("emerald", foreground=ACCENT_EMERALD, font=("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("crimson", foreground=ACCENT_CRIMSON, font=("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("purple", foreground=ACCENT_PURPLE, font=("Consolas", 8, "bold"))
        self.inspector_text.tag_configure("muted", foreground=TEXT_MUTED)
        self.inspector_text.tag_configure("mutation_add", foreground="#4ade80", background="#062e1e")
        self.inspector_text.tag_configure("code", foreground="#e2e8f0", background="#0b0e14")

        # 3. Central 60FPS Interactive Graph Canvas
        center_frame = tk.Frame(workspace, bg=BG_VOID)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Canvas Top Overlay Bar
        canvas_bar = tk.Frame(center_frame, bg=BG_MAIN, height=32, padx=12)
        canvas_bar.pack(fill=tk.X, side=tk.TOP)
        self.lbl_canvas_mode = tk.Label(
            canvas_bar,
            text="LIVE SCHEMATIC: END-TO-END SENSORY & GENOMIC PIPELINE",
            font=FONT_SUBTITLE,
            fg=ACCENT_CYAN,
            bg=BG_MAIN,
        )
        self.lbl_canvas_mode.pack(side=tk.LEFT, pady=4)

        self.lbl_canvas_hint = tk.Label(
            canvas_bar,
            text="Click any node, synapse, or allele branch to inspect real telemetry & capabilities",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_MAIN,
        )
        self.lbl_canvas_hint.pack(side=tk.RIGHT, pady=4)

        self.canvas = tk.Canvas(center_frame, bg=BG_VOID, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Configure>", lambda e: self._redraw_active_canvas())

    def _build_status_footer(self) -> None:
        footer = tk.Frame(self.root, bg=BG_PANEL, height=28, highlightthickness=1, highlightbackground=BORDER_SUBTLE)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        self.lbl_footer_job = tk.Label(
            footer,
            text="● Status: IDLE — Event-Driven Telemetry Heartbeat Active (60 FPS)",
            font=FONT_MONO_SMALL,
            fg=ACCENT_EMERALD,
            bg=BG_PANEL,
            padx=12,
        )
        self.lbl_footer_job.pack(side=tk.LEFT)

        self.lbl_footer_right = tk.Label(
            footer,
            text="Subsystem: IMAGE_SUBSYSTEM_WINDOWS_GUI (Zero-Console) | Close window to return to System Tray",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL,
            padx=12,
        )
        self.lbl_footer_right.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------------
    # View Switching & Left Panel Population
    # ------------------------------------------------------------------------

    def switch_view(self, view_name: str) -> None:
        self.active_view = view_name
        self.selected_node_id = None
        self.shock_overlay.clear()

        for v_id, btn in self.view_buttons.items():
            if v_id == view_name:
                btn.configure(bg=ACCENT_BLUE, fg=TEXT_PRIMARY)
            else:
                btn.configure(bg=BG_PANEL, fg=TEXT_SECONDARY)

        if view_name == "pipeline":
            self.left_header_lbl.configure(text="4-STREAM RADAR & 30-PAT POOL")
            self.lbl_canvas_mode.configure(
                text="VIEW [1] — END-TO-END SENSORY, THALAMIC & GENOMIC PIPELINE FLOW", fg=ACCENT_CYAN
            )
            self.btn_contextual_action.configure(text="📡 Scan Radar", bg=ACCENT_CYAN, fg=BG_VOID)
        elif view_name == "dag":
            self.left_header_lbl.configure(text="CORTICAL CARTRIDGES (U0–U5)")
            self.lbl_canvas_mode.configure(
                text="VIEW [2] — U0–U5 NEUROMORPHIC CAUSAL DAG & SHOCK PROPAGATION", fg=ACCENT_BLUE
            )
            self.btn_contextual_action.configure(text="⚡ Shock (+2.0σ)", bg=ACCENT_CRIMSON, fg=TEXT_PRIMARY)
        elif view_name == "genes":
            self.left_header_lbl.configure(text=f"GENOMIC TAXONOMY ({len(self.genes_catalog)} GENES)")
            self.lbl_canvas_mode.configure(
                text="VIEW [3] — PHYLOGENETIC GENE EVOLUTION TREE & ALLELE ARENA", fg=ACCENT_PURPLE
            )
            self.btn_contextual_action.configure(text="🧬 Mutate & Race", bg=ACCENT_PURPLE, fg=TEXT_PRIMARY)

        self._populate_left_panel()
        self._redraw_active_canvas()

    def _set_tier_filter(self, tier_idx: int) -> None:
        self.selected_tier_filter = tier_idx
        for ti, btn in self.tier_pill_btns.items():
            if ti == tier_idx:
                btn.configure(bg=ACCENT_BLUE, fg=TEXT_PRIMARY)
            else:
                btn.configure(bg=BG_CARD, fg=TIER_COLORS.get(ti, TEXT_SECONDARY))
        if self.active_view != "genes":
            self.switch_view("genes")
        else:
            self._populate_left_panel()

    def _populate_left_panel(self) -> None:
        self.left_listbox.delete(0, tk.END)
        self.left_items_meta.clear()
        q = self.search_query_var.get().strip().lower()

        if self.active_view == "pipeline":
            # List 4 GitHub streams + Token Pool summary
            t = self.gh_cache_data.get("telemetry", {})
            streams = [
                ("STREAM_U3_LABS", f"📡 [U3] Lab Alpha ({len(t.get('opportunities', []))} hits)"),
                ("STREAM_U1_RELEASES", f"🚀 [U1/U2] SOTA Releases ({len(t.get('releases', []))} tags)"),
                ("STREAM_CODON_CP", f"🧬 [Codon] CP Archives ({len(t.get('cp_archives', []))} repos)"),
                ("STREAM_U0_ECO", f"🛡️ [U0] Ecosystem Health ({len(t.get('ecosystem', []))} repos)"),
                ("STAGE_PAT_RING", f"🔑 30-PAT Token Pool ({len(self.gh_sensor.pool.tokens)} tokens)"),
                ("STAGE_THALAMIC", f"⚡ Thalamic Sieve (|Z| >= {self.thalamic_z_threshold.get():.1f}σ)"),
                ("STAGE_ULTIMATRIX", f"🏆 Ultimatrix Arena ({self.arena_ledger_data.get('tournaments_run', 0)} races)"),
            ]
            for s_id, s_label in streams:
                if not q or q in s_label.lower():
                    self.left_listbox.insert(tk.END, f" {s_label}")
                    self.left_items_meta.append({"type": "pipeline_stage", "id": s_id})

            # Also append individual discovered GitHub items
            for opp in t.get("opportunities", []):
                lbl = f"   • [U3] {opp.get('repo', '')}: {opp.get('title', '')[:32]}"
                if not q or q in lbl.lower():
                    self.left_listbox.insert(tk.END, lbl)
                    self.left_items_meta.append({"type": "gh_item", "stream": "U3", "data": opp})

            for rel in t.get("releases", []):
                lbl = f"   • [Rel] {rel.get('repo', '')} ({rel.get('tag', '')})"
                if not q or q in lbl.lower():
                    self.left_listbox.insert(tk.END, lbl)
                    self.left_items_meta.append({"type": "gh_item", "stream": "U1/U2", "data": rel})

        elif self.active_view == "dag":
            # List U0..U5 Cartridges + Nodes in active cartridge
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
            # List genes filtered by Tier and Search Query, prioritizing mutated multi-allele genes first
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
                tag = "🧬" if has_mut else "🔹"
                lbl = f" {tag} [T{tier}] {gid} ({allele_cnt}A)"
                if not q or q in gid.lower() or q in desc.lower() or q in g.get("category", "").lower():
                    self.left_listbox.insert(tk.END, lbl)
                    self.left_items_meta.append({"type": "gene", "gene_id": gid})

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

    # ------------------------------------------------------------------------
    # Central 60FPS Graph Canvas Rendering
    # ------------------------------------------------------------------------

    def _redraw_active_canvas(self) -> None:
        self.canvas.delete("all")
        self.canvas_nodes.clear()
        w = max(self.canvas.winfo_width(), 680)
        h = max(self.canvas.winfo_height(), 520)

        # Draw subtle technical oscilloscope background grid
        grid_step = 40
        for gx in range(0, w, grid_step):
            self.canvas.create_line(gx, 0, gx, h, fill="#0e1218", width=1)
        for gy in range(0, h, grid_step):
            self.canvas.create_line(0, gy, w, gy, fill="#0e1218", width=1)

        if self.active_view == "pipeline":
            self._draw_pipeline_flow_view(w, h)
        elif self.active_view == "dag":
            self._draw_causal_dag_view(w, h)
        elif self.active_view == "genes":
            self._draw_gene_phylogeny_view(w, h)

        # Render active telemetry pulses on top
        self._draw_active_pulses()

    def _register_clickable_node(
        self, node_id: str, x1: float, y1: float, x2: float, y2: float, payload: Dict[str, Any]
    ) -> None:
        self.canvas_nodes[node_id] = {
            "bbox": (x1, y1, x2, y2),
            "center": ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
            "payload": payload,
        }

    def _draw_node_box(
        self,
        node_id: str,
        cx: float,
        cy: float,
        w: float,
        h: float,
        title: str,
        subtitle: str,
        accent: str,
        badge: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        x1, y1 = cx - w / 2, cy - h / 2
        x2, y2 = cx + w / 2, cy + h / 2
        is_sel = self.selected_node_id == node_id

        border_col = accent if is_sel else BORDER_ACTIVE
        border_w = 2 if is_sel else 1
        bg_col = BG_CARD_HOVER if is_sel else BG_CARD

        # Subtle outer glow if selected
        if is_sel:
            self.canvas.create_rectangle(
                x1 - 3, y1 - 3, x2 + 3, y2 + 3, outline=accent, width=1, dash=(3, 3)
            )

        self.canvas.create_rectangle(x1, y1, x2, y2, fill=bg_col, outline=border_col, width=border_w)
        # Left accent bar
        self.canvas.create_rectangle(x1, y1, x1 + 5, y2, fill=accent, outline="")

        self.canvas.create_text(
            x1 + 14, y1 + 16, text=title, fill=TEXT_PRIMARY, font=FONT_SUBTITLE, anchor="w"
        )
        self.canvas.create_text(
            x1 + 14, y1 + 36, text=subtitle, fill=TEXT_MUTED, font=FONT_MONO_SMALL, anchor="w"
        )
        if badge:
            self.canvas.create_text(
                x2 - 8, y1 + 15, text=badge, fill=accent, font=FONT_MONO_SMALL, anchor="e"
            )

        self._register_clickable_node(node_id, x1, y1, x2, y2, payload or {"id": node_id, "title": title})

    def _draw_directed_edge(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str = BORDER_ACTIVE,
        label: str = "",
        dashed: bool = False,
        width: int = 2,
    ) -> None:
        dash_pat = (4, 4) if dashed else None
        self.canvas.create_line(
            x1, y1, x2, y2, fill=color, width=width, arrow=tk.LAST, arrowshape=(8, 10, 4), dash=dash_pat
        )
        if label:
            mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            self.canvas.create_rectangle(mx - 42, my - 9, mx + 42, my + 9, fill=BG_VOID, outline=BORDER_SUBTLE)
            self.canvas.create_text(mx, my, text=label, fill=color, font=("Consolas", 7))

    # --- VIEW 1: Pipeline & 30-PAT Ring Schematic ---

    def _draw_pipeline_flow_view(self, w: float, h: float) -> None:
        t = self.gh_cache_data.get("telemetry", {})
        opp_cnt = len(t.get("opportunities", []))
        rel_cnt = len(t.get("releases", []))
        cp_cnt = len(t.get("cp_archives", []))
        eco_cnt = len(t.get("ecosystem", []))

        col1_x = w * 0.14
        col2_x = w * 0.37
        col3_x = w * 0.62
        col4_x = w * 0.86

        # Column 1: 4 Sensory Streams
        streams = [
            ("STREAM_U3_LABS", "U3 Lab Opportunity Alpha", f"{opp_cnt} Actionable Issues", ACCENT_CYAN, h * 0.18),
            ("STREAM_U1_RELEASES", "U1/U2 SOTA AI Releases", f"{rel_cnt} Upstream Tags", ACCENT_BLUE, h * 0.38),
            ("STREAM_CODON_CP", "Codon Stream CP Archives", f"{cp_cnt} Algorithmic Repos", ACCENT_PURPLE, h * 0.58),
            ("STREAM_U0_ECO", "U0 Public Ecosystem", f"{eco_cnt} Monitored Repos", ACCENT_EMERALD, h * 0.78),
        ]

        pat_cx, pat_cy = col2_x, h * 0.34
        thal_cx, thal_cy = col2_x, h * 0.72
        cortex_cx, cortex_cy = col3_x, h * 0.34
        gene_cx, gene_cy = col3_x, h * 0.72
        arena_cx, arena_cy = col4_x, h * 0.53

        # Edges from Streams -> PAT Ring & Thalamic Sieve
        for s_id, s_title, s_sub, s_col, sy in streams:
            self._draw_directed_edge(col1_x + 95, sy, pat_cx - 72, pat_cy, color=s_col, width=1)
            self._draw_node_box(
                s_id, col1_x, sy, 190, 54, s_title, s_sub, s_col, payload={"type": "pipeline_stage", "id": s_id}
            )

        # Stage 2A: 30-PAT Circular Token Ring (Visual Orbital Radar)
        ring_r = 58
        self.canvas.create_oval(
            pat_cx - ring_r - 12,
            pat_cy - ring_r - 12,
            pat_cx + ring_r + 12,
            pat_cy + ring_r + 12,
            fill=BG_CARD,
            outline=BORDER_ACTIVE,
            width=1,
        )
        tokens = self.gh_sensor.pool.tokens
        n_tok = max(len(tokens), 30)
        ptr = self.gh_sensor.pool._pointer % max(len(tokens), 1)
        for i in range(n_tok):
            angle = (2 * math.pi * i / n_tok) - math.pi / 2
            tx = pat_cx + ring_r * math.cos(angle)
            ty = pat_cy + ring_r * math.sin(angle)
            is_active_slot = (i == ptr) or (self.is_job_running and (i == (self.anim_tick // 4) % n_tok))
            dot_col = ACCENT_GOLD if is_active_slot else (ACCENT_CYAN if i < len(tokens) else BORDER_SUBTLE)
            r_dot = 5 if is_active_slot else 3
            self.canvas.create_oval(tx - r_dot, ty - r_dot, tx + r_dot, ty + r_dot, fill=dot_col, outline="")

        self.canvas.create_text(pat_cx, pat_cy - 8, text="30-PAT RING", fill=TEXT_PRIMARY, font=FONT_SUBTITLE)
        self.canvas.create_text(
            pat_cx, pat_cy + 10, text=f"{len(tokens)} Pooled Keys", fill=ACCENT_CYAN, font=FONT_MONO_SMALL
        )
        self._register_clickable_node(
            "STAGE_PAT_RING",
            pat_cx - 70,
            pat_cy - 70,
            pat_cx + 70,
            pat_cy + 70,
            {"type": "pipeline_stage", "id": "STAGE_PAT_RING"},
        )

        # Edge PAT Ring -> Thalamic Filter
        self._draw_directed_edge(pat_cx, pat_cy + 72, thal_cx, thal_cy - 40, color=ACCENT_CYAN, label="150k req/hr")

        # Stage 2B: Thalamic Z-Score Sieve
        z_gate = self.thalamic_z_threshold.get()
        self._draw_node_box(
            "STAGE_THALAMIC",
            thal_cx,
            thal_cy,
            205,
            68,
            "Thalamic Salience Gate",
            f"Prunes Noise |Z| < {z_gate:.2f}σ",
            ACCENT_AMBER,
            badge="SIEVE",
            payload={"type": "pipeline_stage", "id": "STAGE_THALAMIC"},
        )

        # Edges Thalamic -> Cortex & Gene Sequencer
        self._draw_directed_edge(
            thal_cx + 102, thal_cy - 10, cortex_cx - 105, cortex_cy + 10, color=ACCENT_BLUE, label="Salient Spikes"
        )
        self._draw_directed_edge(
            thal_cx + 102, thal_cy + 10, gene_cx - 105, gene_cy, color=ACCENT_PURPLE, label="Codon Feed"
        )

        # Stage 3A: U0-U5 Cortical Brain
        self._draw_node_box(
            "STAGE_CORTEX",
            cortex_cx,
            cortex_cy,
            210,
            68,
            "U0–U5 Cortical Foresight",
            f"6 Mounted Universes • {len(self.cartridges)} Lobes",
            ACCENT_BLUE,
            badge="DAG",
            payload={"type": "pipeline_stage", "id": "STAGE_CORTEX"},
        )

        # Stage 3B: Ultimatrix Gene Sequencer & Mutator
        mut_cnt = self.mutation_ledger_data.get("mutations_applied", 0)
        self._draw_node_box(
            "STAGE_ULTIMATRIX",
            gene_cx,
            gene_cy,
            210,
            68,
            "Ultimatrix Gene Sequencer",
            f"{len(self.genes_catalog)} Genes • {mut_cnt} Mutations",
            ACCENT_PURPLE,
            badge="T0-T5",
            payload={"type": "pipeline_stage", "id": "STAGE_ULTIMATRIX"},
        )

        # Edges to Stage 4: Arena & SSOT Ledgers
        self._draw_directed_edge(cortex_cx + 105, cortex_cy, arena_cx - 100, arena_cy - 18, color=ACCENT_BLUE)
        self._draw_directed_edge(gene_cx + 105, gene_cy, arena_cx - 100, arena_cy + 18, color=ACCENT_PURPLE)

        races = self.arena_ledger_data.get("tournaments_run", 0)
        promos = self.arena_ledger_data.get("promotions", 0)
        self._draw_node_box(
            "STAGE_ARENA_SSOT",
            arena_cx,
            arena_cy,
            200,
            76,
            "Arena & SSOT Ledgers",
            f"{races} Tournaments • {promos} Promoted",
            ACCENT_GOLD,
            badge="VERIFIED",
            payload={"type": "pipeline_stage", "id": "STAGE_ARENA_SSOT"},
        )

        if not self.selected_node_id:
            self.selected_node_id = "STAGE_THALAMIC"
            self._inspect_pipeline_stage("STAGE_THALAMIC")

    # --- VIEW 2: U0-U5 Neuromorphic Causal DAG ---

    def _draw_causal_dag_view(self, w: float, h: float) -> None:
        if not self.current_macro_graph:
            self._load_selected_cartridge()
        if not self.current_macro_graph or not self.current_macro_graph.nodes:
            self.canvas.create_text(w / 2, h / 2, text="No Cortical Cartridge Loaded", fill=TEXT_MUTED, font=FONT_TITLE)
            return

        nodes = list(self.current_macro_graph.nodes.values())
        synapses = self.current_macro_graph.synapses
        n_cnt = len(nodes)

        # Compute deterministic layered/topological radial positions
        positions: Dict[str, Tuple[float, float]] = {}
        in_deg: Dict[str, int] = {n["id"]: 0 for n in nodes}
        for s in synapses:
            if s["target"] in in_deg:
                in_deg[s["target"]] += 1

        # Group into 3 columns: Roots (in_deg == 0), Mid-layer, Downstream sinks
        roots = [n for n in nodes if in_deg.get(n["id"], 0) == 0]
        others = [n for n in nodes if in_deg.get(n["id"], 0) > 0]
        mid_split = max(1, len(others) // 2)
        mids = others[:mid_split]
        sinks = others[mid_split:]

        layers = [l for l in [roots, mids, sinks] if l]
        for l_idx, layer in enumerate(layers):
            lx = w * (0.18 + 0.64 * (l_idx / max(len(layers) - 1, 1)))
            for r_idx, n in enumerate(layer):
                ly = h * ((r_idx + 1) / (len(layer) + 1))
                positions[n["id"]] = (lx, ly)

        # Draw Directed Axonal Synapses First
        for s in synapses:
            src, tgt = s["source"], s["target"]
            if src in positions and tgt in positions:
                x1, y1 = positions[src]
                x2, y2 = positions[tgt]
                weight = float(s.get("weight", 0.0))
                lag = int(s.get("lag_days", 0))
                edge_col = ACCENT_EMERALD if weight >= 0 else ACCENT_CRIMSON
                if tgt in self.shock_overlay:
                    edge_col = ACCENT_GOLD
                self._draw_directed_edge(
                    x1 + 88,
                    y1,
                    x2 - 88,
                    y2,
                    color=edge_col,
                    label=f"w={weight:+.2f} ({lag}d)",
                    width=2 if abs(weight) >= 0.5 else 1,
                )

        # Draw Cortical Nodes
        z_thresh = self.thalamic_z_threshold.get()
        for n in nodes:
            nid = n["id"]
            cx, cy = positions.get(nid, (w / 2, h / 2))
            z = float(n.get("z_score", 0.0))
            shock_delta = self.shock_overlay.get(nid, 0.0)
            eff_z = z + shock_delta

            if abs(eff_z) < z_thresh:
                col = TEXT_MUTED
                badge = "HABITUATED"
            elif abs(eff_z) < 2.0:
                col = ACCENT_CYAN
                badge = f"Z={eff_z:+.2f}σ"
            elif abs(eff_z) < 3.0:
                col = ACCENT_AMBER
                badge = f"WARN {eff_z:+.1f}σ"
            else:
                col = ACCENT_CRIMSON
                badge = f"SPIKE {eff_z:+.1f}σ"

            if shock_delta != 0.0:
                badge = f"⚡ Δ{shock_delta:+.2f}"
                col = ACCENT_GOLD

            self._draw_node_box(
                nid,
                cx,
                cy,
                176,
                56,
                nid[:18],
                f"{n.get('label', '')[:24]}",
                col,
                badge=badge,
                payload={"type": "dag_node", "id": nid},
            )

        if not self.selected_node_id and nodes:
            self.selected_node_id = nodes[0]["id"]
            self._inspect_dag_node(self.selected_node_id)

    # --- VIEW 3: Phylogenetic Gene Evolution Tree & Capabilities ---

    def _draw_gene_phylogeny_view(self, w: float, h: float) -> None:
        if not self.selected_gene_id or self.selected_gene_id not in self.genes_catalog:
            if self.genes_catalog:
                self.selected_gene_id = next(iter(self.genes_catalog.keys()))
            else:
                self.canvas.create_text(w / 2, h / 2, text="No Sequenced Genes Found", fill=TEXT_MUTED, font=FONT_TITLE)
                return

        gene_data = self.genes_catalog[self.selected_gene_id]
        phylo = build_gene_phylogeny(gene_data)
        tier_col = TIER_COLORS.get(phylo["tier"], ACCENT_CYAN)

        # Layout Columns:
        # Col 1 (x=0.14): Root Gene Locus Card
        # Col 2 (x=0.42): Wild-Type / Base Submission Alleles (Gen 1)
        # Col 3 (x=0.72): Mutated Daughter Alleles via Genetic Operators (Gen 2)
        # Col 4 (x=0.90): Ultimatrix Arena Trophy / Primary Dominance Summary
        root_x, root_y = w * 0.14, h * 0.50
        wt_x = w * 0.44
        mut_x = w * 0.78

        # Top Banner inside Canvas showing Gene Evolution Summary
        self.canvas.create_rectangle(16, 12, w - 16, 54, fill=BG_CARD, outline=BORDER_SUBTLE)
        self.canvas.create_text(
            30,
            33,
            text=f"GENE LOCUS: {phylo['gene_id']}  |  {phylo['tier_label']}  |  Category: {phylo['category'].upper()}",
            fill=tier_col,
            font=FONT_SUBTITLE,
            anchor="w",
        )
        speedup_txt = (
            f"🏆 Net Evolutionary Fitness Gain: +{phylo['net_speedup_pct']:.1f}% Speedup  ({phylo['total_alleles']} Alleles)"
        )
        self.canvas.create_text(w - 30, 33, text=speedup_txt, fill=ACCENT_GOLD, font=FONT_SUBTITLE, anchor="e")

        # 1. Draw Gene Root Node
        self._draw_node_box(
            f"GENE_ROOT::{phylo['gene_id']}",
            root_x,
            root_y,
            195,
            72,
            phylo["gene_id"][:20],
            f"{phylo['tier_label'][:25]}",
            tier_col,
            badge=f"T{phylo['tier']}",
            payload={"type": "gene_root", "gene_id": phylo["gene_id"]},
        )

        # 2. Draw Wild-Type Base Alleles (Generation 1)
        wild_types = phylo["wild_types"]
        wt_positions: Dict[str, Tuple[float, float]] = {}
        for idx, wt in enumerate(wild_types):
            aid = wt.get("allele_id", f"wt_{idx}")
            wy = 70 + (h - 110) * ((idx + 1) / (len(wild_types) + 1))
            wt_positions[aid] = (wt_x, wy)

            is_prim = wt.get("dominance") == "PRIMARY"
            col = ACCENT_GOLD if is_prim else ACCENT_CYAN
            fit = wt.get("empirical_fitness", {})
            rt = fit.get("runtime_ms", "?")
            ram = fit.get("ram_kb", "?")
            comp = wt.get("complexity_time", "O(N)")

            self._draw_directed_edge(root_x + 98, root_y, wt_x - 105, wy, color=tier_col, label="Wild-Type")
            self._draw_node_box(
                f"ALLELE::{aid}",
                wt_x,
                wy,
                210,
                64,
                aid[:22],
                f"{comp} • {rt} ms • {ram} KB",
                col,
                badge="👑 PRIMARY" if is_prim else "BASE",
                payload={"type": "allele", "gene_id": phylo["gene_id"], "allele_id": aid},
            )

        # 3. Draw Mutated Daughter Alleles (Generation 2) & Mutation Operator Labels
        mutants = phylo["mutants"]
        edge_lookup = {e["target_allele"]: e for e in phylo["edges"]}

        if mutants:
            for idx, mut in enumerate(mutants):
                mid = mut.get("allele_id", f"mut_{idx}")
                my = 70 + (h - 110) * ((idx + 1) / (len(mutants) + 1))
                e_info = edge_lookup.get(mid, {})
                parent_id = e_info.get("source_allele", "")
                op_name = e_info.get("operator", "mutation")
                speedup = e_info.get("speedup_pct", 0.0)

                px, py = wt_positions.get(parent_id, (wt_x, root_y))
                is_prim = mut.get("dominance") == "PRIMARY"
                col = ACCENT_GOLD if is_prim else ACCENT_EMERALD

                fit = mut.get("empirical_fitness", {})
                rt = fit.get("runtime_ms", "?")
                ram = fit.get("ram_kb", "?")

                self._draw_directed_edge(
                    px + 105,
                    py,
                    mut_x - 110,
                    my,
                    color=col,
                    label=f"+{op_name} ({speedup:+.0f}%)",
                    width=2,
                )
                self._draw_node_box(
                    f"ALLELE::{mid}",
                    mut_x,
                    my,
                    220,
                    66,
                    mid[-24:],
                    f"Mutant • {rt} ms • {ram} KB",
                    col,
                    badge="👑 CHAMPION" if is_prim else "MUTANT",
                    payload={"type": "allele", "gene_id": phylo["gene_id"], "allele_id": mid},
                )
        else:
            # Show unmutated potential branch placeholder
            self._draw_directed_edge(
                wt_x + 105,
                root_y,
                mut_x - 105,
                root_y,
                color=BORDER_ACTIVE,
                label="Click 'Mutate & Race'",
                dashed=True,
            )
            self._draw_node_box(
                "MUTATE_CTA",
                mut_x,
                root_y,
                210,
                64,
                "⚡ Evolve Daughter Allele",
                "Inject +fast_io / +pragma / +bitwise",
                ACCENT_PURPLE,
                badge="READY",
                payload={"type": "trigger_mutate", "gene_id": phylo["gene_id"]},
            )

        if not self.selected_node_id:
            self.selected_node_id = f"GENE_ROOT::{phylo['gene_id']}"
            self._inspect_gene_or_allele(phylo["gene_id"], self.selected_allele_id)

    # ------------------------------------------------------------------------
    # Right Panel: Capability & Telemetry Inspector
    # ------------------------------------------------------------------------

    def _clear_inspector_badges(self) -> None:
        for child in self.cap_summary_frame.winfo_children():
            child.destroy()

    def _inspect_pipeline_stage(self, stage_id: str) -> None:
        self._clear_inspector_badges()
        self.inspector_text.delete("1.0", tk.END)
        t = self.gh_cache_data.get("telemetry", {})

        tk.Label(
            self.cap_summary_frame,
            text=f"STAGE: {stage_id}",
            font=FONT_SUBTITLE,
            fg=ACCENT_CYAN,
            bg=BG_PANEL,
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
            for opp in t.get("opportunities", []):
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
        tk.Label(
            self.cap_summary_frame,
            text=f"GITHUB RADAR HIT [{stream}]",
            font=FONT_SUBTITLE,
            fg=ACCENT_CYAN,
            bg=BG_PANEL,
        ).pack(anchor="w")
        self.inspector_text.insert(tk.END, f"{item_data.get('repo', 'Repository')}\n", "h1")
        self.inspector_text.insert(tk.END, json.dumps(item_data, indent=2), "code")

    def _inspect_dag_node(self, node_id: str) -> None:
        self._clear_inspector_badges()
        self.inspector_text.delete("1.0", tk.END)
        if not self.current_macro_graph or node_id not in self.current_macro_graph.nodes:
            return

        node = self.current_macro_graph.nodes[node_id]
        gut = PreContactAvoidanceGate.evaluate(node_id, self.current_macro_graph)

        # Badges
        badge_row = tk.Frame(self.cap_summary_frame, bg=BG_PANEL)
        badge_row.pack(fill=tk.X)
        tk.Label(
            badge_row,
            text=f"Z-Score: {node['z_score']:+.2f}σ",
            font=FONT_MONO_SMALL,
            fg=ACCENT_CYAN,
            bg=BG_CARD,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(
            badge_row,
            text=f"State: {node['state_label']}",
            font=FONT_MONO_SMALL,
            fg=ACCENT_GOLD,
            bg=BG_CARD,
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

        phylo = build_gene_phylogeny(gene_data)
        target_allele = phylo["champion"]
        if allele_id:
            for a in gene_data.get("alleles", []):
                if a.get("allele_id") == allele_id:
                    target_allele = a
                    break

        tier_col = TIER_COLORS.get(phylo["tier"], ACCENT_CYAN)

        # Top Capability Pills in Summary Frame
        row1 = tk.Frame(self.cap_summary_frame, bg=BG_PANEL)
        row1.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            row1,
            text=f"T{phylo['tier']} • {phylo['category'].upper()}",
            font=("Consolas", 8, "bold"),
            fg=tier_col,
            bg=BG_CARD,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 4))

        if target_allele:
            t_comp = target_allele.get("complexity_time", "O(N)")
            s_comp = target_allele.get("complexity_space", "O(N)")
            tk.Label(
                row1,
                text=f"Time: {t_comp}",
                font=("Consolas", 8, "bold"),
                fg=ACCENT_EMERALD,
                bg=BG_CARD,
                padx=6,
                pady=2,
            ).pack(side=tk.LEFT, padx=2)
            tk.Label(
                row1,
                text=f"Space: {s_comp}",
                font=("Consolas", 8, "bold"),
                fg=ACCENT_CYAN,
                bg=BG_CARD,
                padx=6,
                pady=2,
            ).pack(side=tk.LEFT, padx=2)

        # Detailed Capability Card in Inspector Text
        self.inspector_text.insert(tk.END, f"🧬 {gene_id}\n", "h1")
        self.inspector_text.insert(tk.END, f"{phylo['description']}\n\n", "muted")

        if target_allele:
            aid = target_allele.get("allele_id", "")
            dom = target_allele.get("dominance", "PRIMARY")
            self.inspector_text.insert(tk.END, f"INSPECTING ALLELE: {aid} [{dom}]\n", "gold" if dom == "PRIMARY" else "h2")

            # 1. Environmental Triggers
            triggers = target_allele.get("environmental_triggers", [])
            if triggers:
                self.inspector_text.insert(tk.END, "\nENVIRONMENTAL TRIGGERS & CONSTRAINTS:\n", "h2")
                self.inspector_text.insert(tk.END, "  " + "  •  ".join(str(t) for t in triggers) + "\n", "purple")

            # 2. Mathematical Invariants
            invariants = target_allele.get("invariants", [])
            if invariants:
                self.inspector_text.insert(tk.END, "\nMATHEMATICAL & ALGORITHMIC INVARIANTS:\n", "h2")
                for inv in invariants:
                    self.inspector_text.insert(tk.END, f"  ✓ {inv}\n", "emerald")

            # 3. Empirical Fitness Comparison Bars across all alleles
            self.inspector_text.insert(tk.END, "\nEMPIRICAL ARENA FITNESS COMPARISON:\n", "h2")
            for a in gene_data.get("alleles", []):
                a_id = a.get("allele_id", "")
                fit = a.get("empirical_fitness", {})
                rt = float(fit.get("runtime_ms", 50.0))
                ram = int(fit.get("ram_kb", 2048))
                bar_len = max(2, min(20, int(rt / 4.0)))
                bar_str = "█" * bar_len
                tag = "gold" if a.get("dominance") == "PRIMARY" else "code"
                crown = "👑" if a.get("dominance") == "PRIMARY" else "  "
                self.inspector_text.insert(
                    tk.END, f"{crown} {a_id[:20]:<20} {bar_str} {rt:>5.1f}ms | {ram}KB\n", tag
                )

            # 4. Evolutionary Lineage Edges
            if phylo["edges"]:
                self.inspector_text.insert(tk.END, "\nEVOLUTIONARY MUTATION LINEAGE:\n", "h2")
                for e in phylo["edges"]:
                    self.inspector_text.insert(
                        tk.END,
                        f"  {e['source_allele']} ──(+{e['operator']})──► {e['target_allele']} ({e['speedup_pct']:+.1f}% speedup)\n",
                        "emerald",
                    )

            # 5. Code Template with Mutation Highlighting
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
    # Canvas Interaction & Live Action Triggers
    # ------------------------------------------------------------------------

    def _on_canvas_click(self, event: Any) -> None:
        cx, cy = event.x, event.y
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
                elif ptype == "trigger_mutate":
                    self._trigger_mutate_selected_gene()

                self._redraw_active_canvas()
                break

    def _on_contextual_inspector_action(self) -> None:
        if self.active_view == "pipeline":
            self._trigger_github_scan()
        elif self.active_view == "dag":
            self._trigger_shock_simulation()
        elif self.active_view == "genes":
            self._trigger_mutate_selected_gene()

    def _on_parameter_tuned(self) -> None:
        """Called when the user adjusts Thalamic Z-Score threshold or RAM Circuit-Breaker limit."""
        if self.active_view == "dag":
            self._load_selected_cartridge()
        self._populate_left_panel()
        self._redraw_active_canvas()

    def _spawn_pulse_wave(self, color: str = ACCENT_CYAN, count: int = 8) -> None:
        """Emits animated signal packets along active canvas nodes."""
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
            text="● Status: IDLE — Work Complete & Ledgers Synchronized (60 FPS)", fg=ACCENT_EMERALD
        )
        self._reload_all_telemetry()
        self._populate_left_panel()
        self._redraw_active_canvas()
        if self.active_view == "genes" and self.selected_gene_id:
            self._inspect_gene_or_allele(self.selected_gene_id, self.selected_allele_id)

    def _trigger_github_scan(self) -> None:
        def job():
            self.gh_sensor.get_cached_telemetry(force_refresh=True)

        self._run_background_job("4-Stream GitHub Sensory Radar Scan (30-PAT Pool)", ACCENT_CYAN, job)

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

        self._run_background_job("U0-U5 Neuromorphic Causal Synthesis", ACCENT_BLUE, job)

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

        self._spawn_pulse_wave(color=ACCENT_GOLD, count=14)
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
                # Materialize baseline gene into codon_stream so it can evolve on disk
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

        self._run_background_job(f"Ultimatrix Genetic Mutation & Arena Race [{gid}]", ACCENT_PURPLE, job)

    def _trigger_harvest_task(self) -> None:
        self._run_background_job("Harvesting & Sequencing Competitive Programming Task", ACCENT_EMERALD, harvest_single_task)

    def _trigger_full_cycle(self) -> None:
        self._run_background_job("Full Azmuth Sentinel Verification Cycle", ACCENT_GOLD, execute_cycle)

    def _on_select_gear(self, gear_name: str) -> None:
        set_current_gear(gear_name, reason="Azmuth Command Center GUI")
        self._refresh_header_indicators()

    def _on_toggle_pause(self) -> None:
        set_paused(not is_paused(), reason="Azmuth Command Center GUI")
        self._refresh_header_indicators()

    # ------------------------------------------------------------------------
    # 60FPS Animation & Telemetry Loop
    # ------------------------------------------------------------------------

    def _draw_active_pulses(self) -> None:
        self.canvas.delete("pulse_particle")
        remaining = []
        for p in self.pulses:
            p["progress"] += p["speed"]
            if p["progress"] < 1.0:
                t = p["progress"]
                px = p["x1"] + (p["x2"] - p["x1"]) * t
                py = p["y1"] + (p["y2"] - p["y1"]) * t
                col = p["color"]
                self.canvas.create_oval(
                    px - 5, py - 5, px + 5, py + 5, fill=col, outline=TEXT_PRIMARY, width=1, tags="pulse_particle"
                )
                remaining.append(p)
            elif self.is_job_running:
                p["progress"] = 0.0
                remaining.append(p)
        self.pulses = remaining

    def _draw_oscilloscope(self) -> None:
        self.osc_canvas.delete("all")
        w, h = 190, 34

        # Draw RAM circuit breaker safety line
        total_gb, avail_gb, load_pct = get_memory_status_gb()
        breaker_gb = float(self.ram_circuit_limit_gb.get())
        breaker_ratio = min(max(1.0 - (breaker_gb / max(total_gb, 1.0)), 0.1), 0.95)
        by = h * (1.0 - breaker_ratio)
        self.osc_canvas.create_line(0, by, w, by, fill=ACCENT_CRIMSON, dash=(2, 2), width=1)

        # Draw 60FPS RAM load waveform
        pts = []
        n = len(self.ram_history)
        for i, val in enumerate(self.ram_history):
            x = (i / max(n - 1, 1)) * w
            # Add subtle 60fps micro-harmonic when active job is running
            jitter = math.sin((self.anim_tick + i) * 0.25) * (2.2 if self.is_job_running else 0.5)
            y = h - ((min(max(val + jitter, 5.0), 98.0) / 100.0) * (h - 6)) - 3
            pts.extend([x, y])

        line_col = ACCENT_CRIMSON if avail_gb < breaker_gb else (ACCENT_GOLD if self.is_job_running else ACCENT_CYAN)
        if len(pts) >= 4:
            self.osc_canvas.create_line(*pts, fill=line_col, width=1.5, smooth=True)

    def _schedule_animation_frame(self) -> None:
        if not self._running:
            return
        self.anim_tick += 1
        self._draw_oscilloscope()
        if self.pulses or self.is_job_running:
            self._draw_active_pulses()
        self.root.after(16, self._schedule_animation_frame)  # ~60 FPS

    def _refresh_header_indicators(self) -> None:
        gear = get_current_gear()
        paused = is_paused()
        total_gb, avail_gb, load_pct = get_memory_status_gb()

        self.ram_history.append(float(load_pct))
        self.ram_history = self.ram_history[-80:]
        self.lbl_ram_readout.configure(
            text=f"{avail_gb:.1f} GB Free ({load_pct}%)",
            fg=ACCENT_CRIMSON if avail_gb < self.ram_circuit_limit_gb.get() else ACCENT_CYAN,
        )

        # Update status dot & pause button
        self.status_dot.itemconfig("dot", fill=ACCENT_AMBER if paused else ACCENT_EMERALD)
        self.btn_pause.configure(
            text="▶ Resume" if paused else "⏸ Pause",
            bg=ACCENT_AMBER if paused else BG_CARD,
            fg=BG_VOID if paused else TEXT_SECONDARY,
        )

        # Highlight active gear pill
        gear_colors = {"whisper": ACCENT_EMERALD, "balanced": ACCENT_BLUE, "turbo": ACCENT_CRIMSON}
        for g_key, btn in self.gear_buttons.items():
            if g_key == gear:
                btn.configure(bg=gear_colors.get(g_key, ACCENT_BLUE), fg=TEXT_PRIMARY)
            else:
                btn.configure(bg=BG_CARD, fg=TEXT_SECONDARY)

        # Update KPI labels
        ready_toks = sum(1 for t in self.gh_sensor.pool.tokens if t.get("status") == "READY")
        self.kpi_labels["pat_pool"].configure(text=f"{ready_toks} / {len(self.gh_sensor.pool.tokens)} Ready")
        self.kpi_labels["genes"].configure(text=f"{len(self.genes_catalog)} Loci")
        self.kpi_labels["mutations"].configure(text=f"{self.mutation_ledger_data.get('mutations_applied', 0)}")
        self.kpi_labels["arena"].configure(text=f"{self.arena_ledger_data.get('tournaments_run', 0)} Races")

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
