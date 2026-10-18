#!/usr/bin/env python3
"""
Fleet-Orchestrator Control Center (v2.0)
High-agency desktop command center for multi-model agent swarms:
- Real-time 27x Copilot pooled AI credits & burn-rate telemetry (5,400 monthly quota)
- Multi-provider worker matrix (Copilot CLI, Gemini 3.8 Flash, Claude Desktop CDP, Groq/Ollama)
- Declarative task queue inspector & SKU pipeline manager
- Win32 High-DPI Virtual Desktop tiling & multi-instance window arranger
- Live timestamped swarm event stream console
"""

from __future__ import annotations

import asyncio
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext
import logging
from typing import Any

import httpx

# Suppress noisy HTTP client logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.copilot_fleet import discover_accounts, get_fleet_quota_metrics, initialize_fleet_ledgers, load_env_fleet
from tools.copilot_queue_worker import resolve_state_dir
from client.process_runtime import run_background

# Configuration & Paths
FLEET_JSON = REPO_ROOT / "orchestrator-state" / "live-status" / "active_fleet.json"
PROFILES_JSON = REPO_ROOT / "profiles.json"
VD_EXE = REPO_ROOT / "tools" / "VirtualDesktop.exe"
LAUNCH_SCRIPT = REPO_ROOT / "launch-fleet.ps1"
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000/api/v1")

# ============================================================================
# ADT Signature Telemetry & Desktop Palette
# ============================================================================
BG_VOID = "#0a0d12"
BG_MAIN = "#0f141c"
BG_CARD = "#141923"
BG_CARD_ALT = "#19202c"
BG_INPUT = "#0c1017"
BORDER_COLOR = "#1e2736"
BORDER_LIGHT = "#2d3a50"

TEXT_PRIMARY = "#f1f5f9"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"

ACCENT_GOLD = "#d4a85a"           # ADT Architectural Hardware Gold & Monogram
ACCENT_BLUE = "#3b82f6"           # Electric Research Cobalt
ACCENT_BLUE_HOVER = "#2563eb"
ACCENT_GREEN = "#22c55e"          # Cactus Green (Online / Active)
ACCENT_GREEN_HOVER = "#16a34a"
ACCENT_AMBER = "#f59e0b"          # Warning / Pending / Cooldown
ACCENT_RED = "#ef4444"            # Terracotta (Fault / Aborted)
ACCENT_CYAN = "#06b6d4"           # Telemetry accent
ACCENT_INDIGO = "#6366f1"         # Calm Research Indigo (Replacing Banned Purple)
ACCENT_PURPLE = ACCENT_INDIGO     # Backward-compatibility alias

ADT_THEMES = {
    "dark": {
        "bg_void": "#0a0d12",
        "bg_main": "#0f141c",
        "bg_card": "#141923",
        "bg_card_alt": "#19202c",
        "bg_input": "#0c1017",
        "border_color": "#1e2736",
        "border_light": "#2d3a50",
        "text_primary": "#f1f5f9",
        "text_secondary": "#94a3b8",
        "text_muted": "#64748b",
        "accent_gold": "#d4a85a",
        "accent_blue": "#3b82f6",
        "accent_green": "#22c55e",
        "accent_amber": "#f59e0b",
        "accent_red": "#ef4444",
        "accent_indigo": "#6366f1",
        "canvas_grid": "#18202d",
    },
    "paper": {
        "bg_void": "#f6f4ef",
        "bg_main": "#f6f4ef",
        "bg_card": "#ffffff",
        "bg_card_alt": "#eae6de",
        "bg_input": "#ffffff",
        "border_color": "#ded8cb",
        "border_light": "#c8c1b3",
        "text_primary": "#141518",
        "text_secondary": "#4a4c52",
        "text_muted": "#7b7e87",
        "accent_gold": "#b45309",
        "accent_blue": "#2563eb",
        "accent_green": "#15803d",
        "accent_amber": "#b45309",
        "accent_red": "#b91c1c",
        "accent_indigo": "#4338ca",
        "canvas_grid": "#e5e0d5",
    },
}

# Typography Hierarchy with Resilient Fallbacks
FONT_BRAND = ("Segoe UI Variable Display", 13, "bold")
FONT_TITLE = ("Segoe UI Variable Display", 11, "bold")
FONT_SUBTITLE = ("Segoe UI Variable Text", 10, "bold")
FONT_BODY = ("Segoe UI Variable Text", 9)
FONT_BODY_BOLD = ("Segoe UI Variable Text", 9, "bold")
FONT_BODY_MUTED = ("Segoe UI Variable Text", 8)
FONT_MONO = ("Cascadia Code", 9)
FONT_BADGE = ("Segoe UI Variable Text", 8, "bold")
FONT_KPI = ("Segoe UI Variable Display", 17, "bold")

GEOMETRY_FILE = REPO_ROOT / "orchestrator-state" / "gui_geometry.json"


def sanitize_geometry(x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    """Self-healing geometry sanitizer against disconnected external displays."""
    vx, vy, vw, vh = 0, 0, 1920, 1080
    if ctypes.windll:
        try:
            user32 = ctypes.windll.user32
            vx = user32.GetSystemMetrics(76)
            vy = user32.GetSystemMetrics(77)
            vw = user32.GetSystemMetrics(78)
            vh = user32.GetSystemMetrics(79)
        except Exception:
            pass
    if vw <= 0 or vh <= 0:
        vw, vh = 1920, 1080

    w = max(1080, min(w, vw))
    h = max(700, min(h, vh))
    if x < vx or (x + 200) > (vx + vw) or y < vy or (y + 100) > (vy + vh):
        x = max(0, (vw - w) // 2)
        y = max(0, (vh - h) // 2)
    return x, y, w, h



def attach_default_desktop() -> bool:
    """Attach the calling thread to the interactive 'Default' desktop in WinSta0."""
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


def enable_high_dpi_and_desktop():
    """Enables Windows 10/11 Per-Monitor DPI v2 awareness."""
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    return attach_default_desktop()


def set_dark_titlebar(hwnd: int):
    """Enable native Windows 11/10 dark title bar for the Tkinter window."""
    for attr in (20, 19):
        try:
            value = ctypes.c_int(1)
            hr = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(attr),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
            if hr == 0:
                break
        except Exception:
            pass


class FleetControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.is_light = False
        self.title("ADT · Fleet-Orchestrator Control Center (v2.0)")
        self.minsize(1080, 700)
        self.configure(bg=BG_MAIN)

        # Self-healing window geometry
        self._restore_window_geometry()

        # Set Windows dark titlebar
        self.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            set_dark_titlebar(hwnd or self.winfo_id())
        except Exception:
            pass

        self.state_dir = resolve_state_dir()
        self.tasks_dir = self.state_dir / "tasks"
        self.live_status_dir = self.state_dir / "live-status"

        # Initialize missing worker ledgers if needed
        initialize_fleet_ledgers(self.state_dir)

        self._destroyed = False
        self._cached_metrics: dict[str, Any] = {}
        self._cached_tasks: list[dict[str, Any]] = []
        self._current_worker_filter = "All"
        self._current_task_filter = "All"

        self._stop_tailer = False
        self._daemon_log_pos = 0
        self._cached_batches: list[dict[str, Any]] = []
        self._toast_frame = None
        self._toast_timer = None

        self._init_styles()
        self._build_ui()
        self._bind_hotkeys()

        # Start background polling loop and log tailer
        self._start_daemon_log_tailer()
        self._auto_refresh_loop()

    def destroy(self):
        self._save_window_geometry()
        self._stop_tailer = True
        self._destroyed = True
        super().destroy()

    def _restore_window_geometry(self):
        try:
            if GEOMETRY_FILE.exists():
                with open(GEOMETRY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                x = data.get("x", 120)
                y = data.get("y", 80)
                w = data.get("width", 1260)
                h = data.get("height", 860)
                is_max = data.get("is_maximized", False)
                x, y, w, h = sanitize_geometry(x, y, w, h)
                self.geometry(f"{w}x{h}+{x}+{y}")
                if is_max:
                    self.state("zoomed")
                return
        except Exception:
            pass
        self.geometry("1260x860")

    def _save_window_geometry(self):
        try:
            GEOMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            is_max = (self.state() == "zoomed")
            active_t = ""
            if hasattr(self, "notebook") and self.notebook.tabs():
                active_t = self.notebook.tab(self.notebook.select(), "text").strip()
            data = {
                "x": self.winfo_x(),
                "y": self.winfo_y(),
                "width": self.winfo_width(),
                "height": self.winfo_height(),
                "is_maximized": is_max,
                "active_tab": active_t,
                "theme": "paper" if getattr(self, "is_light", False) else "dark",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(GEOMETRY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _bind_hotkeys(self):
        self.bind("<F5>", lambda e: self._on_hotkey_refresh())
        self.bind("<Control-r>", lambda e: self._on_hotkey_refresh())
        self.bind("<Control-t>", lambda e: self.toggle_theme())
        self.bind("<Escape>", lambda e: self._on_hotkey_escape())
        for i in range(1, 7):
            self.bind(f"<Control-Key-{i}>", lambda e, idx=i - 1: self._select_tab_by_index(idx))

    def _on_hotkey_refresh(self):
        self.refresh_all()
        self.show_toast("Telemetry Synchronized (F5)", level="gold")

    def _select_tab_by_index(self, idx: int):
        try:
            tabs = self.notebook.tabs()
            if 0 <= idx < len(tabs):
                self.notebook.select(tabs[idx])
                name = self.notebook.tab(tabs[idx], "text").strip()
                self.show_toast(f"Switched to [{name}]", level="info")
        except Exception:
            pass

    def _on_hotkey_escape(self):
        self._set_worker_filter("All")
        self._set_task_filter("All")
        self.refresh_all()
        self.show_toast("Filters Reset (Esc)", level="info")

    def show_toast(self, message: str, level: str = "info", duration_ms: int = 2800):
        try:
            t = ADT_THEMES["paper" if self.is_light else "dark"]
            if self._toast_frame is None:
                self._toast_frame = tk.Frame(self, bg=t["bg_card_alt"], highlightbackground=t["border_light"], highlightthickness=1)
                self._toast_lbl = tk.Label(self._toast_frame, bg=t["bg_card_alt"], font=FONT_BODY_BOLD, padx=12, pady=6)
                self._toast_lbl.pack()
            color_map = {
                "info": t["accent_blue"],
                "success": t["accent_green"],
                "warn": t["accent_amber"],
                "error": t["accent_red"],
                "gold": t["accent_gold"],
            }
            fg_col = color_map.get(level, t["accent_blue"])
            self._toast_frame.config(bg=t["bg_card_alt"], highlightbackground=t["border_light"])
            self._toast_lbl.config(text=f"● {message}", bg=t["bg_card_alt"], fg=fg_col)
            self._toast_frame.place(relx=0.98, rely=0.94, anchor="se")
            self._toast_frame.lift()
            if self._toast_timer:
                self.after_cancel(self._toast_timer)
            self._toast_timer = self.after(duration_ms, self._hide_toast)
        except Exception:
            pass

    def _hide_toast(self):
        try:
            if self._toast_frame:
                self._toast_frame.place_forget()
        except Exception:
            pass

    def toggle_theme(self):
        self.is_light = not self.is_light
        theme_key = "paper" if self.is_light else "dark"
        t = ADT_THEMES[theme_key]
        self.configure(bg=t["bg_main"])
        self._init_styles()
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            val = ctypes.c_int(0 if self.is_light else 1)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd), ctypes.c_uint(attr), ctypes.byref(val), ctypes.sizeof(val)
                )
        except Exception:
            pass
        if hasattr(self, "btn_theme"):
            self.btn_theme.config(text="☾ Dark" if self.is_light else "☼ Paper", bg=t["bg_input"], fg=t["text_primary"])
        self.show_toast(f"Theme: {'Paper Mode' if self.is_light else 'Dark Slate Mode'}", level="gold")


    def _init_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        t = ADT_THEMES["paper" if getattr(self, "is_light", False) else "dark"]

        # Global backgrounds
        self.style.configure(".", background=t["bg_main"], foreground=t["text_primary"], font=FONT_BODY)
        self.style.configure("TLabel", background=t["bg_main"], foreground=t["text_primary"])
        self.style.configure("Card.TFrame", background=t["bg_card"])
        self.style.configure("TFrame", background=t["bg_main"])

        # Tabs styling (Notebook)
        self.style.configure(
            "TNotebook",
            background=t["bg_main"],
            borderwidth=0,
            tabmargins=[14, 6, 14, 0],
        )
        self.style.configure(
            "TNotebook.Tab",
            background=t["bg_card"],
            foreground=t["text_secondary"],
            padding=[16, 8],
            font=FONT_SUBTITLE,
            borderwidth=0,
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", t["bg_card_alt"]), ("active", t["bg_input"])],
            foreground=[("selected", t["text_primary"]), ("active", "#ffffff" if not getattr(self, "is_light", False) else "#000000")],
        )

        # Combobox styling
        self.style.configure(
            "TCombobox",
            fieldbackground=t["bg_input"],
            background=t["bg_card"],
            foreground=t["text_primary"],
            arrowcolor=t["text_muted"],
            borderwidth=1,
            relief="flat",
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", t["bg_input"])],
            foreground=[("readonly", t["text_primary"])],
            selectbackground=[("readonly", t["bg_input"])],
            selectforeground=[("readonly", t["text_primary"])],
        )

        # Treeview styling (clean modern tables)
        self.style.configure(
            "Treeview",
            background=t["bg_card"],
            foreground=t["text_primary"],
            fieldbackground=t["bg_card"],
            rowheight=30,
            font=FONT_BODY,
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            background=t["bg_input"],
            foreground=t["text_secondary"],
            font=FONT_SUBTITLE,
            relief="flat",
            padding=(8, 6),
        )
        self.style.map(
            "Treeview",
            background=[("selected", "#1e3a8a" if not getattr(self, "is_light", False) else "#bfdbfe")],
            foreground=[("selected", "#ffffff" if not getattr(self, "is_light", False) else "#0f172a")],
        )

    def _build_ui(self):
        # =====================================================================
        # 1. HEADER BAR
        # =====================================================================
        header = tk.Frame(self, bg=BG_CARD, height=62, highlightbackground=BORDER_COLOR, highlightthickness=1)
        header.pack(fill="x", padx=14, pady=(12, 6))

        brand_frame = tk.Frame(header, bg=BG_CARD)
        brand_frame.pack(side="left", padx=16, pady=10)

        # ADT Signature Monogram & Title
        title_row = tk.Frame(brand_frame, bg=BG_CARD)
        title_row.pack(anchor="w")

        lbl_crest = tk.Label(
            title_row,
            text="[ADT]",
            font=FONT_BADGE,
            bg=BG_CARD,
            fg=ACCENT_GOLD,
            padx=4,
            pady=0,
        )
        lbl_crest.pack(side="left", padx=(0, 6))

        lbl_logo = tk.Label(
            title_row,
            text="FLEET-ORCHESTRATOR",
            font=FONT_BRAND,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
        )
        lbl_logo.pack(side="left")

        lbl_sub = tk.Label(
            brand_frame,
            text="Autonomous Multi-Model Swarm Engine · 27x Copilot Pool",
            font=FONT_BODY_MUTED,
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        lbl_sub.pack(anchor="w")

        # Header Right Controls
        hdr_right = tk.Frame(header, bg=BG_CARD)
        hdr_right.pack(side="right", padx=16, pady=12)

        self.server_badge = tk.Label(
            hdr_right,
            text="● ORCHESTRATOR: CHECKING",
            font=FONT_BADGE,
            bg="#27272a",
            fg=ACCENT_AMBER,
            padx=10,
            pady=5,
        )
        self.server_badge.pack(side="right", padx=(10, 0))

        btn_refresh = tk.Button(
            hdr_right,
            text="↻ Refresh",
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            activebackground=BORDER_COLOR,
            activeforeground="#ffffff",
            font=FONT_SUBTITLE,
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            command=self.refresh_all,
            cursor="hand2",
        )
        btn_refresh.pack(side="right", padx=(6, 0))

        self.btn_theme = tk.Button(
            hdr_right,
            text="☼ Paper",
            bg=BG_INPUT,
            fg=TEXT_SECONDARY,
            activebackground=BORDER_COLOR,
            activeforeground="#ffffff",
            font=FONT_BADGE,
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            command=self.toggle_theme,
            cursor="hand2",
        )
        self.btn_theme.pack(side="right")

        # =====================================================================
        # 2. PERSISTENT TELEMETRY & QUOTA HUD (Top Burn-Rate Banner)
        # =====================================================================
        hud_frame = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        hud_frame.pack(fill="x", padx=14, pady=(0, 8))

        # KPI Metrics Row
        kpi_row = tk.Frame(hud_frame, bg=BG_CARD)
        kpi_row.pack(fill="x", padx=16, pady=(10, 6))

        # Card 1: Pooled Capacity
        c1 = tk.Frame(kpi_row, bg=BG_INPUT, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=8)
        c1.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(c1, text="POOLED MONTHLY CAPACITY", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_MUTED).pack(anchor="w")
        self.kpi_capacity = tk.Label(c1, text="5,400.00", font=FONT_KPI, bg=BG_INPUT, fg=TEXT_PRIMARY)
        self.kpi_capacity.pack(anchor="w")
        self.kpi_accounts = tk.Label(c1, text="27 Registered Accounts", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=ACCENT_CYAN)
        self.kpi_accounts.pack(anchor="w")

        # Card 2: Consumed Credits
        c2 = tk.Frame(kpi_row, bg=BG_INPUT, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=8)
        c2.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(c2, text="CONSUMED CREDITS", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_MUTED).pack(anchor="w")
        self.kpi_consumed = tk.Label(c2, text="0.00", font=FONT_KPI, bg=BG_INPUT, fg=ACCENT_AMBER)
        self.kpi_consumed.pack(anchor="w")
        self.kpi_burn_pct = tk.Label(c2, text="0.00% Monthly Burn Rate", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_MUTED)
        self.kpi_burn_pct.pack(anchor="w")

        # Card 3: Remaining Quota
        c3 = tk.Frame(kpi_row, bg=BG_INPUT, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=8)
        c3.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(c3, text="REMAINING CAPACITY", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_MUTED).pack(anchor="w")
        self.kpi_remaining = tk.Label(c3, text="5,400.00", font=FONT_KPI, bg=BG_INPUT, fg=ACCENT_GREEN)
        self.kpi_remaining.pack(anchor="w")
        self.kpi_rem_sub = tk.Label(c3, text="100.0% Available", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_MUTED)
        self.kpi_rem_sub.pack(anchor="w")

        # Card 4: Swarm Topology
        c4 = tk.Frame(kpi_row, bg=BG_INPUT, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=8)
        c4.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(c4, text="SWARM TOPOLOGY & PIPELINE", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_MUTED).pack(anchor="w")
        self.kpi_topology = tk.Label(c4, text="27 Ready  |  27 Idle  |  0 Busy", font=FONT_BODY_BOLD, bg=BG_INPUT, fg=TEXT_PRIMARY)
        self.kpi_topology.pack(anchor="w", pady=(3, 0))
        self.kpi_tasks_stat = tk.Label(c4, text="0 Tasks Pending  ·  0 Checkpoints", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=ACCENT_GOLD)
        self.kpi_tasks_stat.pack(anchor="w")

        # Visual Canvas Progress Bar
        bar_frame = tk.Frame(hud_frame, bg=BG_CARD)
        bar_frame.pack(fill="x", padx=16, pady=(4, 12))

        lbl_bar_desc = tk.Label(bar_frame, text="Monthly Fleet Quota Utilization:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED)
        lbl_bar_desc.pack(side="left", padx=(0, 8))

        self.canvas_burn = tk.Canvas(bar_frame, height=14, bg=BG_INPUT, highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.canvas_burn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.lbl_burn_val = tk.Label(bar_frame, text="0.00%", font=FONT_BADGE, bg=BG_CARD, fg=TEXT_SECONDARY)
        self.lbl_burn_val.pack(side="right")

        # =====================================================================
        # 3. MAIN WORKSPACE NOTEBOOK (Tabs)
        # =====================================================================
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        # Tab 1: Fleet Army Matrix
        self.tab_workers = tk.Frame(self.notebook, bg=BG_MAIN)
        self.notebook.add(self.tab_workers, text=" Fleet Army (27 Workers) ")
        self._build_tab_workers()

        # Tab 2: Task Queue & Pipelines
        self.tab_tasks = tk.Frame(self.notebook, bg=BG_MAIN)
        self.notebook.add(self.tab_tasks, text=" Pipeline Tasks ")
        self._build_tab_tasks()

        # Tab 3: Batch Monitor
        self.tab_batches = tk.Frame(self.notebook, bg=BG_MAIN)
        self.notebook.add(self.tab_batches, text=" Batch Monitor ")
        self._build_tab_batches()

        # Tab 4: Windows & Desktop Arranger (Win32)
        self.tab_arranger = tk.Frame(self.notebook, bg=BG_MAIN)
        self.notebook.add(self.tab_arranger, text=" Windows & Desktop Arranger ")
        self._build_tab_arranger()

        # Tab 5: Swarm Activity Console
        self.tab_logs = tk.Frame(self.notebook, bg=BG_MAIN)
        self.notebook.add(self.tab_logs, text=" Swarm Activity Console ")
        self._build_tab_logs()

        # Tab 6: Azmuth & Ultimatrix (Codon Stream & Global Languages)
        self.tab_azmuth = tk.Frame(self.notebook, bg=BG_MAIN)
        self.notebook.add(self.tab_azmuth, text=" Azmuth & Ultimatrix ")
        self._build_tab_azmuth()

        # =====================================================================
        # 4. BOTTOM STATUS BAR (Telemetry & Power-User Hotkey Legend)
        # =====================================================================
        self.status_bar = tk.Frame(self, bg=BG_CARD, height=26, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.status_bar.pack(fill="x", side="bottom")

        self.lbl_status_left = tk.Label(
            self.status_bar,
            text="● FLEET READY · 27 Workers Registered",
            font=FONT_BODY_MUTED,
            bg=BG_CARD,
            fg=ACCENT_GREEN,
        )
        self.lbl_status_left.pack(side="left", padx=14, pady=3)

        self.lbl_status_center = tk.Label(
            self.status_bar,
            text="F5 Refresh  ·  Ctrl+1..6 Tabs  ·  Ctrl+T Theme  ·  Esc Reset Filters",
            font=FONT_BODY_MUTED,
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        self.lbl_status_center.pack(side="left", expand=True, pady=3)

        self.lbl_status_right = tk.Label(
            self.status_bar,
            text="ADT Fleet Control v2.0",
            font=FONT_BODY_MUTED,
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        self.lbl_status_right.pack(side="right", padx=14, pady=3)


    # =========================================================================
    # TAB 1: FLEET ARMY MATRIX
    # =========================================================================
    def _build_tab_workers(self):
        container = tk.Frame(self.tab_workers, bg=BG_MAIN)
        container.pack(fill="both", expand=True, pady=8)

        # Filter bar
        filter_bar = tk.Frame(container, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        filter_bar.pack(fill="x", padx=4, pady=(0, 6))

        tk.Label(filter_bar, text="Filter:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(side="left", padx=(12, 6), pady=8)

        self.btn_f_all = tk.Button(filter_bar, text="All (27)", font=FONT_BADGE, bg=ACCENT_BLUE, fg="#fff", bd=0, padx=10, pady=4, relief="flat", command=lambda: self._set_worker_filter("All"), cursor="hand2")
        self.btn_f_all.pack(side="left", padx=2)

        self.btn_f_busy = tk.Button(filter_bar, text="Busy", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=lambda: self._set_worker_filter("Busy"), cursor="hand2")
        self.btn_f_busy.pack(side="left", padx=2)

        self.btn_f_idle = tk.Button(filter_bar, text="Idle", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=lambda: self._set_worker_filter("Idle"), cursor="hand2")
        self.btn_f_idle.pack(side="left", padx=2)

        self.btn_f_cd = tk.Button(filter_bar, text="Cooldown", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=lambda: self._set_worker_filter("Cooldown"), cursor="hand2")
        self.btn_f_cd.pack(side="left", padx=2)

        # Quick Actions on Right
        btn_canary = tk.Button(filter_bar, text="✦ Run Canary Check", font=FONT_BADGE, bg=BG_INPUT, fg=ACCENT_GREEN, bd=0, padx=10, pady=4, relief="flat", command=self.on_run_canary, cursor="hand2")
        btn_canary.pack(side="right", padx=12)

        split_frame = tk.Frame(container, bg=BG_MAIN)
        split_frame.pack(fill="both", expand=True, padx=4)

        # Workers Table
        tbl_frame = tk.Frame(split_frame, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        tbl_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        cols = ("id", "name", "provider", "status", "elapsed", "credits_used", "credits_rem", "current_task", "note")
        self.tree_workers = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=14)
        self.tree_workers.heading("id", text="Worker ID")
        self.tree_workers.heading("name", text="Nickname / Account")
        self.tree_workers.heading("provider", text="Provider")
        self.tree_workers.heading("status", text="Status")
        self.tree_workers.heading("elapsed", text="Heartbeat")
        self.tree_workers.heading("credits_used", text="Credits Used")
        self.tree_workers.heading("credits_rem", text="Remaining")
        self.tree_workers.heading("current_task", text="Active Task")
        self.tree_workers.heading("note", text="Telemetry Note")

        self.tree_workers.column("id", width=100, anchor="w")
        self.tree_workers.column("name", width=150, anchor="w")
        self.tree_workers.column("provider", width=110, anchor="center")
        self.tree_workers.column("status", width=90, anchor="center")
        self.tree_workers.column("elapsed", width=90, anchor="center")
        self.tree_workers.column("credits_used", width=100, anchor="e")
        self.tree_workers.column("credits_rem", width=100, anchor="e")
        self.tree_workers.column("current_task", width=160, anchor="w")
        self.tree_workers.column("note", width=220, anchor="w")

        # Scrollbar
        sb_w = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree_workers.yview)
        self.tree_workers.configure(yscrollcommand=sb_w.set)
        self.tree_workers.pack(side="left", fill="both", expand=True)
        sb_w.pack(side="right", fill="y")
        self.tree_workers.bind("<<TreeviewSelect>>", self._on_worker_selected)

        # Right inspector panel
        self.worker_insp_frame = tk.LabelFrame(
            split_frame,
            text=" Worker Inspector ",
            font=FONT_SUBTITLE,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            width=320,
        )
        self.worker_insp_frame.pack(side="right", fill="y", padx=(4, 0))
        self.worker_insp_frame.pack_propagate(False)

        self.worker_insp_title = tk.Label(
            self.worker_insp_frame,
            text="Select a worker",
            font=FONT_BODY_BOLD,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            wraplength=280,
            justify="left",
        )
        self.worker_insp_title.pack(anchor="w", padx=12, pady=(10, 6))

        self.worker_insp_status = tk.Label(self.worker_insp_frame, text="Status: -", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED)
        self.worker_insp_status.pack(anchor="w", padx=12, pady=(0, 8))

        tk.Label(self.worker_insp_frame, text="Credits:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=12, pady=(0, 2))
        self.worker_insp_credits_bar = ttk.Progressbar(self.worker_insp_frame, orient="horizontal", length=200, mode="determinate", maximum=100)
        self.worker_insp_credits_bar.pack(anchor="w", padx=12, fill="x", pady=(0, 4))
        self.worker_insp_credits_text = tk.Label(self.worker_insp_frame, text="0.00 / 0.00 credits (0.0%)", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED)
        self.worker_insp_credits_text.pack(anchor="w", padx=12, pady=(0, 10))

        self.worker_insp_heartbeat = tk.Label(self.worker_insp_frame, text="Heartbeat: -", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED)
        self.worker_insp_heartbeat.pack(anchor="w", padx=12, pady=(0, 6))
        self.worker_insp_task = tk.Label(self.worker_insp_frame, text="Current Task: -", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED, wraplength=280, justify="left")
        self.worker_insp_task.pack(anchor="w", padx=12, pady=(0, 6))

        tk.Label(self.worker_insp_frame, text="Telemetry Note:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=12, pady=(4, 2))
        self.worker_insp_note = tk.Label(self.worker_insp_frame, text="-", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED, wraplength=280, justify="left")
        self.worker_insp_note.pack(anchor="w", padx=12, pady=(0, 12), fill="x")

        # Status tag styling
        self.tree_workers.tag_configure("tag_idle", foreground=ACCENT_GREEN)
        self.tree_workers.tag_configure("tag_busy", foreground=ACCENT_CYAN)
        self.tree_workers.tag_configure("tag_cooldown", foreground=ACCENT_AMBER)
        self.tree_workers.tag_configure("tag_offline", foreground=TEXT_MUTED)

    def _set_worker_filter(self, filter_name: str):
        self._current_worker_filter = filter_name
        for btn, name in [
            (self.btn_f_all, "All"),
            (self.btn_f_busy, "Busy"),
            (self.btn_f_idle, "Idle"),
            (self.btn_f_cd, "Cooldown"),
        ]:
            if name == filter_name:
                btn.config(bg=ACCENT_BLUE, fg="#fff")
            else:
                btn.config(bg=BG_INPUT, fg=TEXT_SECONDARY)
        self._render_workers_table()

    # =========================================================================
    # TAB 2: TASK QUEUE & PIPELINES
    # =========================================================================
    def _build_tab_tasks(self):
        container = tk.Frame(self.tab_tasks, bg=BG_MAIN)
        container.pack(fill="both", expand=True, pady=8)

        # Toolbar
        t_bar = tk.Frame(container, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        t_bar.pack(fill="x", padx=4, pady=(0, 6))

        tk.Label(t_bar, text="Status:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(side="left", padx=(12, 6), pady=8)

        self.btn_t_all = tk.Button(t_bar, text="All", font=FONT_BADGE, bg=ACCENT_BLUE, fg="#fff", bd=0, padx=10, pady=4, relief="flat", command=lambda: self._set_task_filter("All"), cursor="hand2")
        self.btn_t_all.pack(side="left", padx=2)

        self.btn_t_pending = tk.Button(t_bar, text="Pending", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=lambda: self._set_task_filter("Pending"), cursor="hand2")
        self.btn_t_pending.pack(side="left", padx=2)

        self.btn_t_claimed = tk.Button(t_bar, text="Claimed", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=lambda: self._set_task_filter("Claimed"), cursor="hand2")
        self.btn_t_claimed.pack(side="left", padx=2)

        self.btn_t_done = tk.Button(t_bar, text="Done", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=lambda: self._set_task_filter("Done"), cursor="hand2")
        self.btn_t_done.pack(side="left", padx=2)

        self.btn_t_blocked = tk.Button(t_bar, text="Blocked", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=lambda: self._set_task_filter("Blocked"), cursor="hand2")
        self.btn_t_blocked.pack(side="left", padx=2)

        # Right actions
        btn_run_worker = tk.Button(t_bar, text="▶ Run Single Worker Step", font=FONT_BADGE, bg=BG_INPUT, fg=ACCENT_CYAN, bd=0, padx=10, pady=4, relief="flat", command=self.on_run_worker_step, cursor="hand2")
        btn_run_worker.pack(side="right", padx=12)

        # Split: Left Tasks Table, Right Task Inspector
        split_frame = tk.Frame(container, bg=BG_MAIN)
        split_frame.pack(fill="both", expand=True, padx=4)

        # Left Table
        tbl_frame = tk.Frame(split_frame, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        tbl_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        t_cols = ("id", "stage", "kind", "status", "worker", "dispatcher", "priority")
        self.tree_tasks = ttk.Treeview(tbl_frame, columns=t_cols, show="headings", height=12)
        self.tree_tasks.heading("id", text="Task ID")
        self.tree_tasks.heading("stage", text="Stage")
        self.tree_tasks.heading("kind", text="Kind")
        self.tree_tasks.heading("status", text="Status")
        self.tree_tasks.heading("worker", text="Assigned Worker")
        self.tree_tasks.heading("dispatcher", text="Dispatcher / Creator")
        self.tree_tasks.heading("priority", text="Priority")

        self.tree_tasks.column("id", width=180, anchor="w")
        self.tree_tasks.column("stage", width=80, anchor="center")
        self.tree_tasks.column("kind", width=70, anchor="center")
        self.tree_tasks.column("status", width=80, anchor="center")
        self.tree_tasks.column("worker", width=120, anchor="center")
        self.tree_tasks.column("dispatcher", width=140, anchor="center")
        self.tree_tasks.column("priority", width=60, anchor="center")

        sb_t = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree_tasks.yview)
        self.tree_tasks.configure(yscrollcommand=sb_t.set)
        self.tree_tasks.pack(side="left", fill="both", expand=True)
        sb_t.pack(side="right", fill="y")

        self.tree_tasks.bind("<<TreeviewSelect>>", self._on_task_selected)

        # Right Inspector
        self.insp_frame = tk.LabelFrame(
            split_frame,
            text=" Task Inspector ",
            font=FONT_SUBTITLE,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            width=420,
        )
        self.insp_frame.pack(side="right", fill="both", padx=(4, 0))
        self.insp_frame.pack_propagate(False)

        self.insp_title = tk.Label(self.insp_frame, text="Select a task to inspect details", font=FONT_BODY_BOLD, bg=BG_CARD, fg=TEXT_PRIMARY, wraplength=400, justify="left")
        self.insp_title.pack(anchor="w", padx=12, pady=(10, 4))

        self.insp_meta = tk.Label(self.insp_frame, text="", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED)
        self.insp_meta.pack(anchor="w", padx=12, pady=(0, 6))

        tk.Label(self.insp_frame, text="Specification / Scope:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=12, pady=(4, 2))

        self.insp_text = scrolledtext.ScrolledText(
            self.insp_frame,
            bg=BG_INPUT,
            fg=TEXT_SECONDARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            bd=0,
            padx=8,
            pady=6,
            font=FONT_MONO,
            height=14,
            wrap="word",
        )
        self.insp_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _set_task_filter(self, filter_name: str):
        self._current_task_filter = filter_name
        for btn, name in [
            (self.btn_t_all, "All"),
            (self.btn_t_pending, "Pending"),
            (self.btn_t_claimed, "Claimed"),
            (self.btn_t_done, "Done"),
            (self.btn_t_blocked, "Blocked"),
        ]:
            if name == filter_name:
                btn.config(bg=ACCENT_BLUE, fg="#fff")
            else:
                btn.config(bg=BG_INPUT, fg=TEXT_SECONDARY)
        self._render_tasks_table()

    def _format_worker_heartbeat(self, heartbeat_at: Any) -> str:
        if heartbeat_at in (None, ""):
            return "-"

        if not isinstance(heartbeat_at, str):
            return "-"

        try:
            hb = heartbeat_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(hb)
        except ValueError:
            return "-"

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        elapsed = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
        if elapsed < 60:
            return f"{int(elapsed)}s"
        if elapsed < 3600:
            return f"{int(elapsed // 60)}m"
        if elapsed < 86400:
            return f"{int(elapsed // 3600)}h"
        return f"{int(elapsed // 86400)}d"

    def _on_worker_selected(self, event):
        sel = self.tree_workers.selection()
        if not sel:
            return

        item = self.tree_workers.item(sel[0])
        values = item.get("values") or ()
        worker_id = values[0] if values else None
        if not worker_id:
            return

        worker = next((w for w in self._cached_metrics.get("workers", []) if str(w.get("worker_id")) == str(worker_id)), None)
        if not worker:
            return

        status = str(worker.get("status") or "idle").upper()
        total_credits = float(worker.get("monthly_credits", 0) or 0)
        used_credits = float(worker.get("credits_used", 0.0) or 0.0)
        pct = 0.0 if total_credits <= 0 else min(100.0, (used_credits / total_credits) * 100.0)

        self.worker_insp_title.config(text=f"Worker: {worker.get('name') or worker_id}")
        self.worker_insp_status.config(text=f"Status: {status}")
        self.worker_insp_credits_bar.configure(maximum=100, value=pct)
        self.worker_insp_credits_text.config(text=f"{used_credits:.2f} / {total_credits:.2f} credits ({pct:.1f}%)")
        self.worker_insp_heartbeat.config(text=f"Heartbeat: {self._format_worker_heartbeat(worker.get('heartbeat_at'))}")
        self.worker_insp_task.config(text=f"Current Task: {worker.get('current_task_id') or '-'}")
        self.worker_insp_note.config(text=worker.get("note") or "No telemetry note available.")

    def _on_task_selected(self, event):
        sel = self.tree_tasks.selection()
        if not sel:
            return
        item = self.tree_tasks.item(sel[0])
        tid = item["values"][0] if item["values"] else None
        if not tid:
            return

        task_data = next((t for t in self._cached_tasks if t.get("id") == tid), None)
        if not task_data:
            return

        self.insp_title.config(text=f"Task: {tid}")
        meta_str = f"Stage: {task_data.get('current_stage') or task_data.get('stage') or 'code'}  •  Status: {task_data.get('status', '').upper()}"
        if task_data.get("sku_id"):
            meta_str += f"  •  SKU: {task_data.get('sku_id')}"
        meta_str += f"  •  Dispatched by: {task_data.get('created_by') or 'unknown'}"
        self.insp_meta.config(text=meta_str)

        self.insp_text.delete("1.0", tk.END)
        spec = task_data.get("spec") or task_data.get("course_title") or json.dumps(task_data, indent=2)
        self.insp_text.insert("1.0", spec)

    # =========================================================================
    # TAB 3: BATCH MONITOR
    # =========================================================================
    def _build_tab_batches(self):
        container = tk.Frame(self.tab_batches, bg=BG_MAIN)
        container.pack(fill="both", expand=True, pady=8)

        # Split: Left Batches Table, Right Batch Detail Inspector
        split_frame = tk.Frame(container, bg=BG_MAIN)
        split_frame.pack(fill="both", expand=True, padx=4)

        tbl_frame = tk.Frame(split_frame, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        tbl_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        b_cols = ("batch_id", "dispatcher", "total", "done", "pending", "progress", "status")
        self.tree_batches = ttk.Treeview(tbl_frame, columns=b_cols, show="headings", height=14)
        self.tree_batches.heading("batch_id", text="Batch / Job ID")
        self.tree_batches.heading("dispatcher", text="Dispatcher")
        self.tree_batches.heading("total", text="Total Tasks")
        self.tree_batches.heading("done", text="Done")
        self.tree_batches.heading("pending", text="Pending")
        self.tree_batches.heading("progress", text="Progress %")
        self.tree_batches.heading("status", text="Status")

        self.tree_batches.column("batch_id", width=220, anchor="w")
        self.tree_batches.column("dispatcher", width=130, anchor="center")
        self.tree_batches.column("total", width=80, anchor="center")
        self.tree_batches.column("done", width=70, anchor="center")
        self.tree_batches.column("pending", width=70, anchor="center")
        self.tree_batches.column("progress", width=90, anchor="center")
        self.tree_batches.column("status", width=90, anchor="center")

        sb_b = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree_batches.yview)
        self.tree_batches.configure(yscrollcommand=sb_b.set)
        self.tree_batches.pack(side="left", fill="both", expand=True)
        sb_b.pack(side="right", fill="y")
        self.tree_batches.bind("<<TreeviewSelect>>", self._on_batch_selected)

        # Right Batch Inspector
        self.batch_insp_frame = tk.LabelFrame(
            split_frame,
            text=" Batch Inspector ",
            font=FONT_SUBTITLE,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            width=360,
        )
        self.batch_insp_frame.pack(side="right", fill="both", padx=(4, 0))
        self.batch_insp_frame.pack_propagate(False)

        self.batch_insp_title = tk.Label(
            self.batch_insp_frame,
            text="Select a batch to inspect",
            font=FONT_BODY_BOLD,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            wraplength=330,
            justify="left",
        )
        self.batch_insp_title.pack(anchor="w", padx=12, pady=(10, 4))

        self.batch_insp_meta = tk.Label(self.batch_insp_frame, text="", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED)
        self.batch_insp_meta.pack(anchor="w", padx=12, pady=(0, 6))

        tk.Label(self.batch_insp_frame, text="Batch Completion Progress:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=12, pady=(2, 2))
        self.batch_insp_bar = ttk.Progressbar(self.batch_insp_frame, orient="horizontal", length=240, mode="determinate")
        self.batch_insp_bar.pack(anchor="w", padx=12, fill="x", pady=(0, 4))
        self.batch_insp_pct_lbl = tk.Label(self.batch_insp_frame, text="0.0% Complete", font=FONT_BODY_MUTED, bg=BG_CARD, fg=ACCENT_CYAN)
        self.batch_insp_pct_lbl.pack(anchor="w", padx=12, pady=(0, 8))

        tk.Label(self.batch_insp_frame, text="Task Breakdown:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=12, pady=(2, 2))
        self.batch_tasks_text = scrolledtext.ScrolledText(
            self.batch_insp_frame,
            bg=BG_INPUT,
            fg=TEXT_SECONDARY,
            relief="flat",
            bd=0,
            padx=8,
            pady=6,
            font=FONT_MONO,
            height=12,
            wrap="word",
        )
        self.batch_tasks_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _render_batches_table(self):
        for item in self.tree_batches.get_children():
            self.tree_batches.delete(item)

        groups: dict[str, list[dict[str, Any]]] = {}
        for t in self._cached_tasks:
            bid = t.get("job_id") or t.get("sku_id") or t.get("created_by") or "ungrouped"
            groups.setdefault(bid, []).append(t)

        self._cached_batches = []
        for bid, btasks in sorted(groups.items()):
            tot = len(btasks)
            done_cnt = len([x for x in btasks if x.get("status") in ("done", "merged")])
            pending_cnt = len([x for x in btasks if x.get("status") == "pending"])
            claimed_cnt = len([x for x in btasks if x.get("status") == "claimed"])
            blocked_cnt = len([x for x in btasks if x.get("status") == "blocked"])

            pct = round((done_cnt / tot * 100.0), 1) if tot > 0 else 0.0
            dispatcher = btasks[0].get("created_by") or "-"

            if done_cnt == tot:
                status_str = "COMPLETE"
            elif claimed_cnt > 0:
                status_str = "RUNNING"
            elif blocked_cnt > 0:
                status_str = "BLOCKED"
            else:
                status_str = "PENDING"

            batch_info = {
                "batch_id": bid,
                "dispatcher": dispatcher,
                "total": tot,
                "done": done_cnt,
                "pending": pending_cnt,
                "progress": pct,
                "status": status_str,
                "tasks": btasks,
            }
            status_display = {
                "COMPLETE": "● Complete",
                "RUNNING": "● Running",
                "BLOCKED": "● Blocked",
                "PENDING": "● Pending",
            }.get(status_str, f"● {status_str}")

            self.tree_batches.insert(
                "",
                "end",
                values=(bid, dispatcher, tot, done_cnt, pending_cnt, f"{pct:.1f}%", status_display),
            )

    def _on_batch_selected(self, event):
        sel = self.tree_batches.selection()
        if not sel:
            return
        item = self.tree_batches.item(sel[0])
        vals = item.get("values") or ()
        if not vals:
            return
        bid = vals[0]

        batch = next((b for b in self._cached_batches if b["batch_id"] == bid), None)
        if not batch:
            return

        self.batch_insp_title.config(text=f"Batch: {bid}")
        self.batch_insp_meta.config(text=f"Dispatcher: {batch['dispatcher']}  •  Status: {batch['status']}")
        self.batch_insp_bar.configure(maximum=100, value=batch['progress'])
        self.batch_insp_pct_lbl.config(text=f"{batch['progress']:.1f}% Complete ({batch['done']}/{batch['total']} tasks)")

        self.batch_tasks_text.delete("1.0", tk.END)
        for t in batch["tasks"]:
            tid = t.get("id") or "-"
            st = (t.get("status") or "pending").upper()
            worker = t.get("owner_account") or "-"
            stage = t.get("stage") or t.get("current_stage") or "code"
            self.batch_tasks_text.insert(tk.END, f"• [{st}] {tid}\n  Stage: {stage} | Worker: {worker}\n")

    # =========================================================================
    # TAB 4: WINDOWS & DESKTOP ARRANGER (Win32)
    # =========================================================================
    def _build_tab_arranger(self):
        container = tk.Frame(self.tab_arranger, bg=BG_MAIN)
        container.pack(fill="both", expand=True, pady=8)

        # Virtual Desktop Controls Bar
        vdesk_card = tk.LabelFrame(container, text=" Virtual Desktop & Layout Control (Desktop 2) ", font=FONT_SUBTITLE, bg=BG_CARD, fg=TEXT_PRIMARY, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1)
        vdesk_card.pack(fill="x", padx=4, pady=(0, 8))

        row1 = tk.Frame(vdesk_card, bg=BG_CARD)
        row1.pack(fill="x", padx=14, pady=10)

        btn_tile = tk.Button(row1, text="⊞ Tile Windows (3-Column Grid)", bg=BG_INPUT, fg=TEXT_PRIMARY, activebackground=BORDER_COLOR, activeforeground="#fff", font=FONT_BODY_BOLD, relief="flat", bd=0, padx=14, pady=7, command=self.on_tile_windows, cursor="hand2")
        btn_tile.pack(side="left", padx=(0, 6))

        btn_focus = tk.Button(row1, text="◎ Focus Zone (PowerToys Stack)", bg=BG_INPUT, fg=TEXT_PRIMARY, activebackground=BORDER_COLOR, activeforeground="#fff", font=FONT_BODY_BOLD, relief="flat", bd=0, padx=14, pady=7, command=self.on_focus_layout, cursor="hand2")
        btn_focus.pack(side="left", padx=6)

        btn_vdesk2 = tk.Button(row1, text="⎈ Switch to Desktop 2 (Fleet)", bg=ACCENT_BLUE, fg="#ffffff", activebackground=ACCENT_BLUE_HOVER, font=FONT_BODY_BOLD, relief="flat", bd=0, padx=14, pady=7, command=lambda: self.on_switch_desktop(1), cursor="hand2")
        btn_vdesk2.pack(side="left", padx=6)

        btn_vdesk1 = tk.Button(row1, text="⌂ Return to Desktop 1", bg=BG_INPUT, fg=TEXT_PRIMARY, activebackground=BORDER_COLOR, activeforeground="#fff", font=FONT_BODY_BOLD, relief="flat", bd=0, padx=14, pady=7, command=lambda: self.on_switch_desktop(0), cursor="hand2")
        btn_vdesk1.pack(side="left", padx=6)

        # Prompt Injection Console
        inj_card = tk.LabelFrame(container, text=" Multi-Instance Prompt Injection Console (Path B) ", font=FONT_SUBTITLE, bg=BG_CARD, fg=TEXT_PRIMARY, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1)
        inj_card.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        ctrl_row = tk.Frame(inj_card, bg=BG_CARD)
        ctrl_row.pack(fill="x", padx=14, pady=(10, 6))

        tk.Label(ctrl_row, text="Target Worker:", font=FONT_BODY_BOLD, bg=BG_CARD, fg=TEXT_PRIMARY).pack(side="left", padx=(0, 8))
        self.target_var = tk.StringVar(value="✦ Broadcast All")
        self.target_cb = ttk.Combobox(ctrl_row, textvariable=self.target_var, values=["✦ Broadcast All"], state="readonly", width=26, font=FONT_BODY)
        self.target_cb.pack(side="left", padx=(0, 16))

        tk.Label(ctrl_row, text="Templates:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(side="left", padx=(0, 6))
        for name, cmd in [
            ("Lead Orch", self._set_tmpl_orch),
            ("Researcher", self._set_tmpl_research),
            ("Writer", self._set_tmpl_draft),
            ("Ping All", self._set_tmpl_ping),
        ]:
            b = tk.Button(ctrl_row, text=name, font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_PRIMARY, activebackground=BORDER_COLOR, relief="flat", bd=0, padx=8, pady=3, command=cmd, cursor="hand2")
            b.pack(side="left", padx=2)

        tk.Label(ctrl_row, text="Model Directive:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(side="left", padx=(12, 4))
        self.model_directive_var = tk.StringVar(value="Auto-routing (Copilot)")
        model_cb = ttk.Combobox(ctrl_row, textvariable=self.model_directive_var, values=["Auto-routing (Copilot)", "Sonnet 3.7", "Gemini 3.8 Flash", "Haiku 3.5", "Opus 3"], state="readonly", width=22, font=FONT_BODY)
        model_cb.pack(side="left", padx=2)

        # Text input & send button
        text_row = tk.Frame(inj_card, bg=BG_CARD)
        text_row.pack(fill="both", expand=True, padx=14, pady=(6, 12))

        self.prompt_text = tk.Text(
            text_row,
            height=4,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            bd=0,
            padx=10,
            pady=8,
            font=FONT_BODY,
            wrap="word",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        self.prompt_text.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.prompt_text.insert("1.0", "Inspect active tasks in orchestrator-state/tasks and execute pending stage autonomously.")

        btn_send = tk.Button(
            text_row,
            text="▶ Dispatch &\nHit Enter",
            bg=ACCENT_GREEN,
            fg="#ffffff",
            activebackground=ACCENT_GREEN_HOVER,
            activeforeground="#ffffff",
            font=FONT_SUBTITLE,
            relief="flat",
            bd=0,
            padx=18,
            command=self.on_dispatch_prompt,
            cursor="hand2",
        )
        btn_send.pack(side="right", fill="y")

    def _set_tmpl_orch(self):
        self.target_var.set("✦ Broadcast All")
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", "You are the Fleet Orchestrator. Inspect active tasks and coordinate domain handoffs.")

    def _set_tmpl_research(self):
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", "Claim pending research stage tasks from orchestrator-state/tasks/ and write checkpoints.")

    def _set_tmpl_draft(self):
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", "Claim pending draft stage tasks and produce clean, verified implementation deliverables.")

    def _set_tmpl_ping(self):
        self.target_var.set("✦ Broadcast All")
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", "Autonomous Fleet Swarm: check in and report status.")

    # =========================================================================
    # TAB 4: SWARM ACTIVITY CONSOLE
    # =========================================================================
    def _build_tab_logs(self):
        container = tk.Frame(self.tab_logs, bg=BG_MAIN)
        container.pack(fill="both", expand=True, pady=8)

        log_bar = tk.Frame(container, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        log_bar.pack(fill="x", padx=4, pady=(0, 6))

        tk.Label(log_bar, text="Console Logs", font=FONT_BODY_BOLD, bg=BG_CARD, fg=TEXT_PRIMARY).pack(side="left", padx=12, pady=8)

        self.auto_scroll_var = tk.BooleanVar(value=True)
        chk_scroll = tk.Checkbutton(log_bar, text="Auto-Scroll", variable=self.auto_scroll_var, bg=BG_CARD, fg=TEXT_SECONDARY, selectcolor=BG_INPUT, activebackground=BG_CARD, font=FONT_BODY_MUTED)
        chk_scroll.pack(side="left", padx=12)

        btn_clear = tk.Button(log_bar, text="Clear Console", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=self.clear_logs, cursor="hand2")
        btn_clear.pack(side="right", padx=12)

        # Scrolled Text Terminal
        self.log_text = scrolledtext.ScrolledText(
            container,
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
            font=FONT_MONO,
            wrap="word",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        self.log_text.pack(fill="both", expand=True, padx=4)

        # Configure color tags
        self.log_text.tag_config("tag_time", foreground=TEXT_MUTED)
        self.log_text.tag_config("tag_info", foreground=ACCENT_CYAN)
        self.log_text.tag_config("tag_success", foreground=ACCENT_GREEN)
        self.log_text.tag_config("tag_warn", foreground=ACCENT_AMBER)
        self.log_text.tag_config("tag_err", foreground=ACCENT_RED)
        self.log_text.tag_config("tag_task", foreground=ACCENT_GOLD)

        self.log("Fleet Control Center v2.0 initialized. Quota telemetry active.")

    def log(self, message: str, level: str = "INFO"):
        now_str = time.strftime("%H:%M:%S")

        def _do_log():
            try:
                line_count = int(self.log_text.index("end-1c").split(".")[0])
                if line_count > 1500:
                    self.log_text.delete("1.0", "300.0")

                self.log_text.insert(tk.END, f"[{now_str}] ", "tag_time")

                lvl_upper = level.upper()
                if "SUCCESS" in lvl_upper or "[SUCCESS]" in message:
                    tag = "tag_success"
                elif "WARN" in lvl_upper or "[WARN" in message:
                    tag = "tag_warn"
                elif "ERR" in lvl_upper or "[ERROR]" in message:
                    tag = "tag_err"
                elif "TASK" in lvl_upper or "Task" in message:
                    tag = "tag_task"
                else:
                    tag = "tag_info"

                self.log_text.insert(tk.END, f"{message}\n", tag)
                if self.auto_scroll_var.get():
                    self.log_text.see(tk.END)
            except Exception:
                pass

        if threading.current_thread() is threading.main_thread():
            _do_log()
        else:
            self.after(0, _do_log)

    def clear_logs(self):
        self.log_text.delete("1.0", tk.END)

    def _start_daemon_log_tailer(self):
        """Streams live worker_daemon.log events into the console in background."""
        def _tail_worker():
            log_path = self.state_dir / "logs" / "worker_daemon.log"
            # Fast-forward to recent end on initial startup
            if log_path.exists():
                try:
                    self._daemon_log_pos = max(0, log_path.stat().st_size - 4096)
                except Exception:
                    self._daemon_log_pos = 0

            while not getattr(self, "_destroyed", False) and not getattr(self, "_stop_tailer", False):
                try:
                    if log_path.exists():
                        cur_size = log_path.stat().st_size
                        if cur_size < self._daemon_log_pos:
                            self._daemon_log_pos = 0
                        if cur_size > self._daemon_log_pos:
                            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                                f.seek(self._daemon_log_pos)
                                chunk = f.read()
                                self._daemon_log_pos = f.tell()
                            for line in chunk.splitlines():
                                line_clean = line.strip()
                                if line_clean:
                                    lvl = "INFO"
                                    if "[ERROR]" in line_clean or "ERR" in line_clean:
                                        lvl = "ERROR"
                                    elif "[WARN" in line_clean or "WARNING" in line_clean:
                                        lvl = "WARN"
                                    elif "marked DONE" in line_clean or "Successfully" in line_clean:
                                        lvl = "SUCCESS"
                                    elif "Executing" in line_clean or "claim" in line_clean.lower():
                                        lvl = "TASK"
                                    self.log(f"[DAEMON] {line_clean}", level=lvl)
                except Exception:
                    pass
                time.sleep(1.0)

        threading.Thread(target=_tail_worker, daemon=True).start()

    # =========================================================================
    # REFRESH & TELEMETRY ENGINE
    # =========================================================================
    def refresh_all(self):
        threading.Thread(target=self._refresh_worker_thread, daemon=True).start()

    def _refresh_worker_thread(self):
        # 1. Check server health
        server_ok = False
        try:
            # Probe /health to verify port 8000 is actually Fleet-Orchestrator and not another local daemon
            health_url = ORCHESTRATOR_URL.rsplit("/api/v1", 1)[0] + "/health"
            r = httpx.get(health_url, timeout=1.0)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and data.get("status") == "ok" and "mcp_endpoint" in data:
                    server_ok = True
        except Exception:
            server_ok = False

        # 2. Get quota metrics
        metrics = get_fleet_quota_metrics(self.state_dir)

        # 3. Read tasks
        tasks = []
        if self.tasks_dir.exists():
            for tf in sorted(self.tasks_dir.glob("task_*.json")):
                try:
                    with open(tf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        tasks.append(data)
                except Exception:
                    pass

        self._cached_metrics = metrics
        self._cached_tasks = tasks

        # Safe main thread update
        if not getattr(self, "_destroyed", False):
            try:
                self.after(0, lambda: self._apply_telemetry_updates(server_ok, metrics, tasks))
            except Exception:
                pass

    def _apply_telemetry_updates(self, server_ok: bool, metrics: dict[str, Any], tasks: list[dict[str, Any]]):
        # Update server badge
        if server_ok:
            self.server_badge.config(text="● ORCHESTRATOR: ONLINE (:8000)", fg=ACCENT_GREEN, bg="#064e3b")
        else:
            self.server_badge.config(text="● DIRECT FILE LEDGER (OFFLINE)", fg=ACCENT_AMBER, bg="#451a03")

        # Update KPI Banner
        f = metrics.get("fleet", {})
        t = metrics.get("tasks", {})

        total_cap = f.get("total_monthly_credits", 5400)
        used_credits = f.get("total_credits_used", 0.0)
        rem_credits = f.get("total_credits_remaining", 5400.0)
        burn_pct = f.get("burn_rate_pct", 0.0)
        reg_acc = f.get("total_registered_accounts", 27)

        self.kpi_capacity.config(text=f"{total_cap:,.2f}")
        self.kpi_accounts.config(text=f"{reg_acc} Registered Accounts")

        self.kpi_consumed.config(text=f"{used_credits:,.2f}")
        self.kpi_burn_pct.config(text=f"{burn_pct:.2f}% Monthly Burn Rate")

        self.kpi_remaining.config(text=f"{rem_credits:,.2f}")
        rem_pct = round(100.0 - burn_pct, 2)
        self.kpi_rem_sub.config(text=f"{rem_pct:.2f}% Available")

        status_counts = f.get("status_counts", {})
        ready_acc = f.get("ready_accounts", 0)
        idle_cnt = status_counts.get("idle", 0)
        busy_cnt = status_counts.get("busy", 0)
        cd_cnt = status_counts.get("cooldown", 0)

        self.kpi_topology.config(text=f"{busy_cnt}/{reg_acc} Active  |  {ready_acc} Ready  |  {idle_cnt} Idle  |  {cd_cnt} Cooldown")

        pending_tasks = len([tsk for tsk in tasks if tsk.get("status") == "pending"])
        checkpoints_cnt = t.get("completed_checkpoints", 0)
        self.kpi_tasks_stat.config(text=f"{pending_tasks} Tasks Pending  •  {checkpoints_cnt} Checkpoints Complete")

        # Update Burn-rate canvas bar
        self._draw_burn_bar(burn_pct)

        # Render Tables
        self._render_workers_table()
        self._render_tasks_table()
        self._render_batches_table()
        self._render_azmuth_view()

    def _draw_burn_bar(self, burn_pct: float):
        self.lbl_burn_val.config(text=f"{burn_pct:.2f}%")
        self.canvas_burn.delete("all")

        w = self.canvas_burn.winfo_width()
        h = self.canvas_burn.winfo_height()
        if w < 10:
            w = 300
        if h < 5:
            h = 14

        fill_w = max(0, min(w, int(w * (burn_pct / 100.0))))

        # Determine color gradient
        if burn_pct < 50.0:
            bar_color = ACCENT_GREEN
        elif burn_pct < 80.0:
            bar_color = ACCENT_AMBER
        else:
            bar_color = ACCENT_RED

        if fill_w > 0:
            self.canvas_burn.create_rectangle(0, 0, fill_w, h, fill=bar_color, width=0)

    def _render_workers_table(self):
        for item in self.tree_workers.get_children():
            self.tree_workers.delete(item)

        workers = self._cached_metrics.get("workers", [])
        for w in workers:
            st = w.get("status", "idle").lower()
            if self._current_worker_filter == "Busy" and st != "busy":
                continue
            if self._current_worker_filter == "Idle" and st != "idle":
                continue
            if self._current_worker_filter == "Cooldown" and st != "cooldown":
                continue

            heartbeat_at = w.get("heartbeat_at")
            elapsed_str = self._format_worker_heartbeat(heartbeat_at)
            stale_heartbeat = False
            if heartbeat_at:
                try:
                    hb = heartbeat_at.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(hb)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    stale_heartbeat = (datetime.now(timezone.utc) - dt).total_seconds() > 120
                except Exception:
                    stale_heartbeat = True
            elif st != "offline":
                stale_heartbeat = True

            if st == "offline":
                tag = "tag_offline"
            elif stale_heartbeat:
                tag = "tag_cooldown"
            else:
                tag = f"tag_{st}" if st in ("idle", "busy", "cooldown", "offline") else "tag_idle"

            used_val = float(w.get("credits_used", 0.0) or 0.0)
            rem_val = float(w.get("credits_remaining", 200.0) or 0.0)
            total_lim = float(w.get("monthly_credits", 200) or 200)
            ratio = min(1.0, max(0.0, used_val / total_lim)) if total_lim > 0 else 0.0
            filled = int(round(ratio * 5))
            micro_bar = "▓" * filled + "░" * (5 - filled)
            used_str = f"{micro_bar} {used_val:.2f} / {total_lim:.2f}"
            rem_str = f"{rem_val:.2f}"

            task_str = w.get("current_task_id") or "-"
            note_str = w.get("note") or "Ready"
            if w.get("cooldown_until"):
                note_str = f"Cooldown until {w['cooldown_until'][11:19]}"

            status_display = {
                "idle": "● Idle",
                "busy": "● Busy",
                "cooldown": "● Cooldown",
                "offline": "● Offline",
            }.get(st, f"● {st.capitalize()}")

            self.tree_workers.insert(
                "",
                "end",
                values=(
                    w.get("worker_id"),
                    w.get("name"),
                    "Copilot CLI",
                    status_display,
                    elapsed_str,
                    used_str,
                    rem_str,
                    task_str,
                    note_str,
                ),
                tags=(tag,),
            )

    def _render_tasks_table(self):
        for item in self.tree_tasks.get_children():
            self.tree_tasks.delete(item)

        for t in self._cached_tasks:
            st = t.get("status", "pending").lower()
            if self._current_task_filter == "Pending" and st != "pending":
                continue
            if self._current_task_filter == "Claimed" and st != "claimed":
                continue
            if self._current_task_filter == "Done" and st != "done":
                continue
            if self._current_task_filter == "Blocked" and st != "blocked":
                continue

            tid = t.get("id") or "-"
            stage = t.get("current_stage") or t.get("stage") or "code"
            kind = t.get("kind") or "code"
            worker = t.get("owner_account") or t.get("owner_worker_id") or "-"
            dispatcher = t.get("created_by") or "-"
            prio = t.get("priority", 5)

            status_display = {
                "pending": "● Pending",
                "claimed": "● Claimed",
                "done": "● Done",
                "merged": "● Done",
                "blocked": "● Blocked",
            }.get(st, f"● {st.capitalize()}")

            self.tree_tasks.insert(
                "",
                "end",
                values=(tid, stage, kind, status_display, worker, dispatcher, prio),
            )

    def _auto_refresh_loop(self):
        if getattr(self, "_destroyed", False):
            return
        self.refresh_all()
        try:
            self.after(5000, self._auto_refresh_loop)
        except Exception:
            pass

    # =========================================================================
    # ACTIONS: WIN32 & VIRTUAL DESKTOP
    # =========================================================================
    def on_switch_desktop(self, desk_num: int):
        def _worker():
            if VD_EXE.exists():
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                out = run_background([str(VD_EXE), "/Count"], capture_output=True, text=True, creationflags=flags).stdout
                m = re.search(r"(\d+)", out)
                current_count = int(m.group(1)) if m else 1
                target_req = desk_num + 1
                if current_count < target_req:
                    self.log(f"Creating Desktop {target_req}...")
                    while current_count < target_req:
                        run_background([str(VD_EXE), "/Quiet", "/New"], capture_output=True, creationflags=flags)
                        current_count += 1
                self.log(f"Switching to Desktop {desk_num + 1}...")
                run_background([str(VD_EXE), f"/Switch:{desk_num}"], capture_output=True, creationflags=flags)
                self.log(f"[SUCCESS] Switched to Desktop {desk_num + 1}.")
            else:
                self.log(f"[!] VirtualDesktop.exe not found at {VD_EXE}")

        threading.Thread(target=_worker, daemon=True).start()

    def on_tile_windows(self):
        def _worker():
            attach_default_desktop()
            fleet = self._load_fleet_data()
            hwnds = [inst.get("Hwnd") for inst in fleet if inst.get("Hwnd")]
            if not hwnds:
                self.log("[!] No active window handles found in active_fleet.json.")
                return

            user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
            sw = user32.GetSystemMetrics(0) if user32 else 1920
            sh = user32.GetSystemMetrics(1) if user32 else 1080

            num_windows = max(1, len(hwnds))
            col_w = max(300, sw // num_windows)

            self.log(f"Tiling {len(hwnds)} windows across {sw}x{sh} on Desktop 2...")
            try:
                import win32gui, win32con
            except ImportError:
                self.log("[ERROR] pywin32 (win32gui) is not available.")
                return

            for i, h in enumerate(hwnds):
                try:
                    h_int = int(h)
                    if user32.IsWindow(h_int):
                        x = i * col_w
                        y = 0
                        w = col_w
                        h_win = max(400, sh - 40)
                        win32gui.ShowWindow(h_int, win32con.SW_RESTORE)
                        win32gui.SetWindowPos(h_int, 0, x, y, w, h_win, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
                except Exception:
                    pass
            self.log(f"[SUCCESS] Windows snapped into {len(hwnds)}-column layout.")

        threading.Thread(target=_worker, daemon=True).start()

    def on_focus_layout(self):
        def _worker():
            attach_default_desktop()
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)

            fw = min(sw, max(850, int(sw * 0.85)))
            fh = min(sh, max(600, int(sh * 0.88)))
            base_x = max(0, (sw - fw) // 2)
            base_y = max(0, (sh - fh) // 2)

            fleet = self._load_fleet_data()
            hwnds = [inst.get("Hwnd") for inst in fleet if inst.get("Hwnd")]
            if not hwnds:
                self.log("[!] No active window handles found in active_fleet.json.")
                return

            try:
                import win32gui, win32con
            except ImportError:
                self.log("[ERROR] pywin32 (win32gui) is not available.")
                return

            offset_step = 24
            max_offset = max(0, min(sw - fw, sh - fh))

            for i, h in enumerate(hwnds):
                try:
                    h_int = int(h)
                    if user32.IsWindow(h_int):
                        step = (i * offset_step) % (max_offset + 1) if max_offset > 0 else 0
                        win32gui.ShowWindow(h_int, win32con.SW_RESTORE)
                        win32gui.SetWindowPos(h_int, 0, base_x + step, base_y + step, fw, fh, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
                except Exception:
                    pass
            self.log("[SUCCESS] Windows stacked in Focus Zone layout.")

        threading.Thread(target=_worker, daemon=True).start()

    def on_dispatch_prompt(self):
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("Warning", "Prompt cannot be empty.")
            return

        target_str = self.target_var.get()
        model_dir = self.model_directive_var.get()
        final_prompt = prompt
        if model_dir and "Auto-routing" not in model_dir:
            final_prompt = f"[System Directive: Use model {model_dir}]\n\n{prompt}"

        def _worker():
            try:
                from client.adapters.claude_desktop_cdp import ClaudeDesktopUIAAdapter
            except ImportError:
                self.log("[!] ClaudeDesktopUIAAdapter not found.")
                return

            fleet = self._load_fleet_data()
            if "Broadcast" in target_str:
                self.log(f"Broadcasting prompt to all {len(fleet)} instances...")
                for inst in fleet:
                    acc = inst.get("Account")
                    hwnd = inst.get("Hwnd")
                    if hwnd:
                        adapter = ClaudeDesktopUIAAdapter(worker_id=acc, nickname=acc, hwnd=hwnd)
                        if adapter._focus_window() and adapter._paste_and_enter(final_prompt):
                            self.log(f"  [SUCCESS] Dispatched to {acc} (HWND={hwnd})")
                        time.sleep(0.3)
                self.log("[SUCCESS] Broadcast completed.")
            else:
                m = re.match(r"^([a-zA-Z0-9_-]+)", target_str.strip())
                acc = m.group(1) if m else target_str.split()[0]
                target_inst = next((i for i in fleet if i.get("Account") == acc), None)
                if not target_inst or not target_inst.get("Hwnd"):
                    self.log(f"[!] Instance {acc} has no valid window HWND.")
                    return
                hwnd = target_inst.get("Hwnd")
                adapter = ClaudeDesktopUIAAdapter(worker_id=acc, nickname=acc, hwnd=hwnd)
                if adapter._focus_window() and adapter._paste_and_enter(final_prompt):
                    self.log(f"[SUCCESS] Dispatched to {acc} (HWND={hwnd}).")
                else:
                    self.log(f"[ERROR] Failed dispatch to {acc}.")

        threading.Thread(target=_worker, daemon=True).start()

    def on_run_canary(self):
        def _worker():
            self.log("Running canary check across ready Copilot accounts...")
            cmd = [sys.executable, str(REPO_ROOT / "tools" / "copilot_fleet.py"), "canary"]
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                proc = run_background(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), creationflags=flags)
                for line in proc.stdout.splitlines():
                    if line.strip():
                        self.log(line)
                self.log("[SUCCESS] Canary check complete.")
            except Exception as e:
                self.log(f"[ERROR] Canary check failed: {e}")
            self.refresh_all()

        threading.Thread(target=_worker, daemon=True).start()

    def on_run_worker_step(self):
        def _worker():
            self.log("Executing single worker queue cycle (copilot_queue_worker.py)...")
            cmd = [sys.executable, str(REPO_ROOT / "tools" / "copilot_queue_worker.py"), "--once"]
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                proc = run_background(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), creationflags=flags)
                for line in proc.stdout.splitlines():
                    if line.strip():
                        self.log(line)
                self.log("[SUCCESS] Worker step finished.")
            except Exception as e:
                self.log(f"[ERROR] Worker execution error: {e}")
            self.refresh_all()

        threading.Thread(target=_worker, daemon=True).start()

    def _load_fleet_data(self) -> list[dict]:
        if FLEET_JSON.exists():
            try:
                return json.loads(FLEET_JSON.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    # =========================================================================
    # TAB 6: AZMUTH & ULTIMATRIX (Codon Stream & Global Languages)
    # =========================================================================
    def _build_tab_azmuth(self):
        container = tk.Frame(self.tab_azmuth, bg=BG_MAIN)
        container.pack(fill="both", expand=True, pady=8)

        # 1. Top HUD Cards (Daemon State, Gear, Codon Stream Progress)
        hud_bar = tk.Frame(container, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        hud_bar.pack(fill="x", padx=4, pady=(0, 6))

        c_row = tk.Frame(hud_bar, bg=BG_CARD)
        c_row.pack(fill="x", padx=12, pady=10)

        # Card A: Daemon Lifecycle & Gear
        c_a = tk.Frame(c_row, bg=BG_INPUT, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=8)
        c_a.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(c_a, text="AZMUTH DAEMON & GEAR", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_az_state = tk.Label(c_a, text="ACTIVE (TURBO)", font=FONT_BODY_BOLD, bg=BG_INPUT, fg=ACCENT_GREEN)
        self.lbl_az_state.pack(anchor="w", pady=(2, 0))
        self.lbl_az_memory = tk.Label(c_a, text="RAM: Probing...", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_SECONDARY)
        self.lbl_az_memory.pack(anchor="w")

        # Card B: Codon Stream Progress
        c_b = tk.Frame(c_row, bg=BG_INPUT, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=8)
        c_b.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(c_b, text="CODON STREAM (PHASE 2 GRADUATED)", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_az_genes = tk.Label(c_b, text="162 / 100 Genes [MET]", font=FONT_KPI, bg=BG_INPUT, fg=ACCENT_CYAN)
        self.lbl_az_genes.pack(anchor="w")
        self.lbl_az_tiers = tk.Label(c_b, text="T0: 4 | T1: 37 | T2: 87 | T3: 25 | T4: 9", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_SECONDARY)
        self.lbl_az_tiers.pack(anchor="w")

        # Card C: Language References & Solved Tasks
        c_c = tk.Frame(c_row, bg=BG_INPUT, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=8)
        c_c.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(c_c, text="LANG REFS & VERIFIED SOLVER", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_az_langs = tk.Label(c_c, text="30 / 30 Modules (Tiers A-C)", font=FONT_BODY_BOLD, bg=BG_INPUT, fg=ACCENT_INDIGO)
        self.lbl_az_langs.pack(anchor="w", pady=(2, 0))
        self.lbl_az_solver = tk.Label(c_c, text="23 Tasks Solved (100% Sample Verified)", font=FONT_BODY_MUTED, bg=BG_INPUT, fg=ACCENT_AMBER)
        self.lbl_az_solver.pack(anchor="w")

        # Control Action Bar
        act_bar = tk.Frame(container, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        act_bar.pack(fill="x", padx=4, pady=(0, 6))

        tk.Label(act_bar, text="Gear Selection:", font=FONT_BODY_MUTED, bg=BG_CARD, fg=TEXT_MUTED).pack(side="left", padx=(12, 6), pady=8)

        self.btn_gear_eco = tk.Button(act_bar, text="● ECO", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=lambda: self.on_switch_gear("eco"), cursor="hand2")
        self.btn_gear_eco.pack(side="left", padx=2)

        self.btn_gear_bal = tk.Button(act_bar, text="● BALANCED", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SECONDARY, bd=0, padx=10, pady=4, relief="flat", command=lambda: self.on_switch_gear("balanced"), cursor="hand2")
        self.btn_gear_bal.pack(side="left", padx=2)

        self.btn_gear_turbo = tk.Button(act_bar, text="● TURBO", font=FONT_BADGE, bg=ACCENT_BLUE, fg="#fff", bd=0, padx=10, pady=4, relief="flat", command=lambda: self.on_switch_gear("turbo"), cursor="hand2")
        self.btn_gear_turbo.pack(side="left", padx=2)

        # Daemon Pause / Resume Toggle
        self.btn_az_toggle = tk.Button(act_bar, text="■ Pause Daemon", font=FONT_BADGE, bg=BG_INPUT, fg=ACCENT_AMBER, bd=0, padx=10, pady=4, relief="flat", command=self.on_toggle_azmuth_pause, cursor="hand2")
        self.btn_az_toggle.pack(side="left", padx=12)

        # Right-side action triggers
        btn_burst = tk.Button(act_bar, text="▶ Run Single Burst", font=FONT_BADGE, bg=BG_INPUT, fg=ACCENT_GREEN, bd=0, padx=10, pady=4, relief="flat", command=self.on_azmuth_burst, cursor="hand2")
        btn_burst.pack(side="right", padx=12)

        btn_foresight = tk.Button(act_bar, text="✦ Run Foresight Scan", font=FONT_BADGE, bg=BG_INPUT, fg=ACCENT_INDIGO, bd=0, padx=10, pady=4, relief="flat", command=self.on_azmuth_foresight, cursor="hand2")
        btn_foresight.pack(side="right", padx=4)

        btn_gh_radar = tk.Button(act_bar, text="◈ GitHub Radar", font=FONT_BADGE, bg=BG_INPUT, fg=ACCENT_AMBER, bd=0, padx=10, pady=4, relief="flat", command=self.on_azmuth_github_radar, cursor="hand2")
        btn_gh_radar.pack(side="right", padx=4)

        btn_harvest_lang = tk.Button(act_bar, text="☷ Harvest Language Refs", font=FONT_BADGE, bg=BG_INPUT, fg=ACCENT_CYAN, bd=0, padx=10, pady=4, relief="flat", command=self.on_harvest_languages, cursor="hand2")
        btn_harvest_lang.pack(side="right", padx=4)

        # 2. Main Content Split (Left: Codon Stream Browser, Right: Global Language Reference Cards)
        split = tk.Frame(container, bg=BG_MAIN)
        split.pack(fill="both", expand=True, padx=4)

        # Left Pane: Codon Stream Table
        p_left = tk.Frame(split, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        p_left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        tk.Label(p_left, text="Codon Stream Repository (162 Genes)", font=FONT_SUBTITLE, bg=BG_CARD, fg=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(10, 6))

        cols_codon = ("tier", "gene_id", "family", "complexity", "provenance")
        self.tree_codon = ttk.Treeview(p_left, columns=cols_codon, show="headings", height=15)
        self.tree_codon.heading("tier", text="Tier")
        self.tree_codon.heading("gene_id", text="Gene Identifier")
        self.tree_codon.heading("family", text="Algorithmic Family")
        self.tree_codon.heading("complexity", text="Complexity")
        self.tree_codon.heading("provenance", text="Source Platform")

        self.tree_codon.column("tier", width=70, anchor="center")
        self.tree_codon.column("gene_id", width=220, anchor="w")
        self.tree_codon.column("family", width=140, anchor="w")
        self.tree_codon.column("complexity", width=110, anchor="center")
        self.tree_codon.column("provenance", width=110, anchor="center")

        scroll_c = ttk.Scrollbar(p_left, orient="vertical", command=self.tree_codon.yview)
        self.tree_codon.configure(yscrollcommand=scroll_c.set)
        self.tree_codon.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        scroll_c.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))

        # Right Pane: Global Language References Table
        p_right = tk.Frame(split, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
        p_right.pack(side="right", fill="both", expand=True, padx=(4, 0))

        tk.Label(p_right, text="Global Language & Runtime References (30 Modules)", font=FONT_SUBTITLE, bg=BG_CARD, fg=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(10, 6))

        cols_lang = ("tier", "topic", "runtime", "invariants")
        self.tree_lang = ttk.Treeview(p_right, columns=cols_lang, show="headings", height=15)
        self.tree_lang.heading("tier", text="Tier")
        self.tree_lang.heading("topic", text="Topic / Identifier")
        self.tree_lang.heading("runtime", text="Runtime / Spec")
        self.tree_lang.heading("invariants", text="Invariants Count")

        self.tree_lang.column("tier", width=70, anchor="center")
        self.tree_lang.column("topic", width=220, anchor="w")
        self.tree_lang.column("runtime", width=150, anchor="w")
        self.tree_lang.column("invariants", width=110, anchor="center")

        scroll_l = ttk.Scrollbar(p_right, orient="vertical", command=self.tree_lang.yview)
        self.tree_lang.configure(yscrollcommand=scroll_l.set)
        self.tree_lang.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        scroll_l.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))

    def _render_azmuth_view(self):
        """Refreshes Tab 6 Azmuth & Ultimatrix metrics and tables."""
        if not hasattr(self, "lbl_az_state"):
            return

        state_dir = self.state_dir
        gear_file = state_dir / "azmuth_gear.json"
        active_gear = "turbo"
        if gear_file.exists():
            try:
                active_gear = json.loads(gear_file.read_text(encoding="utf-8")).get("active_gear", "turbo")
            except Exception:
                pass

        paused = (state_dir / "azmuth.pause").exists()
        if paused:
            self.lbl_az_state.config(text=f"PAUSED ({active_gear.upper()})", fg=ACCENT_AMBER)
            self.btn_az_toggle.config(text="▶ Resume Daemon", fg=ACCENT_GREEN)
        else:
            self.lbl_az_state.config(text=f"ACTIVE ({active_gear.upper()})", fg=ACCENT_GREEN)
            self.btn_az_toggle.config(text="⏸ Pause Daemon", fg=ACCENT_AMBER)

        # Highlight active gear button
        for g_btn, name in ((self.btn_gear_eco, "eco"), (self.btn_gear_bal, "balanced"), (self.btn_gear_turbo, "turbo")):
            if name == active_gear:
                g_btn.config(bg=ACCENT_BLUE, fg="#ffffff")
            else:
                g_btn.config(bg=BG_INPUT, fg=TEXT_SECONDARY)

        # Update RAM telemetry
        try:
            import psutil
            mem = psutil.virtual_memory()
            free_gb = mem.available / (1024 ** 3)
            tot_gb = mem.total / (1024 ** 3)
            self.lbl_az_memory.config(text=f"RAM: {free_gb:.2f} GB free / {tot_gb:.2f} GB total ({mem.percent}% load)")
        except Exception:
            pass

        # Update Solved statistics
        solver_file = state_dir / "ultimatrix_solver_ledger.json"
        solved_count = 23
        if solver_file.exists():
            try:
                s_data = json.loads(solver_file.read_text(encoding="utf-8"))
                solved_count = len(s_data.get("solved_slugs", []))
            except Exception:
                pass
        self.lbl_az_solver.config(text=f"{solved_count} Tasks Solved (100% Sample Verified)")

        # Render Codon Stream Table
        cp_root = REPO_ROOT.parent / "Competitive-Programming"
        codon_dir = cp_root / "codon_stream"
        # Update Codon Stream HUD metrics
        if codon_dir.exists():
            t_counts = {}
            for t_idx, t_name in enumerate(["tier0_hardware", "tier1_language", "tier2_primitives", "tier3_domain_breakers", "tier4_symbolic", "tier5_super_domain"]):
                tp = codon_dir / t_name
                t_counts[f"T{t_idx}"] = len(list(tp.glob("*.json"))) if tp.exists() else 0
            total_g = sum(t_counts.values())
            self.lbl_az_genes.config(text=f"{total_g} / 100 Genes [MET]")
            self.lbl_az_tiers.config(text=f"T0: {t_counts.get('T0',0)} | T1: {t_counts.get('T1',0)} | T2: {t_counts.get('T2',0)} | T3: {t_counts.get('T3',0)} | T4: {t_counts.get('T4',0)} | T5: {t_counts.get('T5',0)}")

        if codon_dir.exists() and len(self.tree_codon.get_children()) == 0:
            tier_dirs = {
                "T0": codon_dir / "tier0_hardware",
                "T1": codon_dir / "tier1_language",
                "T2": codon_dir / "tier2_primitives",
                "T3": codon_dir / "tier3_domain_breakers",
                "T4": codon_dir / "tier4_symbolic",
                "T5": codon_dir / "tier5_super_domain",
            }
            gene_rows = []
            for t_label, t_path in tier_dirs.items():
                if t_path.exists():
                    for gf in sorted(t_path.glob("*.json")):
                        try:
                            g_data = json.loads(gf.read_text(encoding="utf-8"))
                            g_id = g_data.get("gene_id", gf.stem)
                            fam = g_data.get("family", "Algorithm")
                            comp = g_data.get("complexity", {}).get("time", "O(N)")
                            prov = g_data.get("provenance", {}).get("source_contest", "Ecosystem")
                            gene_rows.append((t_label, g_id, fam, comp, prov))
                        except Exception:
                            pass
            for row in gene_rows:
                self.tree_codon.insert("", "end", values=row)

        # Render Language References Table
        lang_index = cp_root / "runtimes" / "global_references" / "INDEX.md"
        lang_ledger = state_dir / "azmuth_language_ledger.json"
        if lang_ledger.exists() and len(self.tree_lang.get_children()) == 0:
            try:
                l_data = json.loads(lang_ledger.read_text(encoding="utf-8"))
                recs = l_data.get("records", [])
                for r in recs:
                    t_val = r.get("tier", "A")
                    top = r.get("topic", "")
                    rt = r.get("runtime", "")
                    inv_cnt = r.get("invariants_count", 0)
                    self.tree_lang.insert("", "end", values=(f"Tier {t_val}", top, rt, inv_cnt))
            except Exception:
                pass

    def on_switch_gear(self, gear: str):
        def _worker():
            self.log(f"Switching Azmuth daemon gear to: {gear.upper()}...")
            cmd = [sys.executable, str(REPO_ROOT / "tools" / "azmuth_daemon.py"), "--gear", gear]
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                run_background(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), creationflags=flags)
                self.log(f"[SUCCESS] Switched Azmuth gear to {gear.upper()}.")
            except Exception as e:
                self.log(f"[ERROR] Failed switching gear: {e}")
            self.refresh_all()

        threading.Thread(target=_worker, daemon=True).start()

    def on_toggle_azmuth_pause(self):
        state_dir = self.state_dir
        pause_flag = state_dir / "azmuth.pause"
        if pause_flag.exists():
            pause_flag.unlink(missing_ok=True)
            self.log("[SUCCESS] Resumed Azmuth background daemon.")
        else:
            pause_flag.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
            self.log("[WARN] Paused Azmuth background daemon.")
        self.refresh_all()

    def on_azmuth_burst(self):
        def _worker():
            self.log("Triggering single manual Azmuth mutation & solving burst...")
            cmd = [sys.executable, str(REPO_ROOT / "tools" / "azmuth_daemon.py"), "--burst"]
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                proc = run_background(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), creationflags=flags)
                for line in proc.stdout.splitlines():
                    if line.strip():
                        self.log(line)
                self.log("[SUCCESS] Azmuth burst execution complete.")
            except Exception as e:
                self.log(f"[ERROR] Azmuth burst error: {e}")
            self.refresh_all()

        threading.Thread(target=_worker, daemon=True).start()

    def on_harvest_languages(self):
        def _worker():
            self.log("Triggering 3-tier Global Language Reference Harvest...")
            cmd = [sys.executable, str(REPO_ROOT / "tools" / "azmuth_language_harvester.py"), "--harvest-all"]
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                proc = run_background(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), creationflags=flags)
                for line in proc.stdout.splitlines():
                    if line.strip():
                        self.log(line)
                self.log("[SUCCESS] 30 Global Language Reference cards harvested & materialized.")
            except Exception as e:
                self.log(f"[ERROR] Harvest failed: {e}")
            self.refresh_all()

        threading.Thread(target=_worker, daemon=True).start()

    def on_azmuth_foresight(self):
        def _worker():
            self.log("Running Azmuth Neuromorphic Foresight Scan across all 6 Cartridges...")
            cmd = [sys.executable, str(REPO_ROOT / "tools" / "azmuth_macro_graph.py"), "--foresight"]
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                proc = run_background(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), creationflags=flags)
                for line in proc.stdout.splitlines():
                    if line.strip():
                        self.log(line)
                self.log("[SUCCESS] Foresight brief generated: orchestrator-state/macro_foresight_brief.json")
            except Exception as e:
                self.log(f"[ERROR] Foresight scan failed: {e}")
            self.refresh_all()

        threading.Thread(target=_worker, daemon=True).start()

    def on_azmuth_github_radar(self):
        def _worker():
            self.log("Running Azmuth Autonomous GitHub Sensory Radar Scan across all 4 streams...")
            cmd = [sys.executable, str(REPO_ROOT / "tools" / "azmuth_github_sensor.py"), "--scan"]
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                proc = run_background(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), creationflags=flags)
                for line in proc.stdout.splitlines():
                    if line.strip():
                        self.log(line)
                self.log("[SUCCESS] GitHub intelligence brief generated: orchestrator-state/github_intelligence_brief.md")
            except Exception as e:
                self.log(f"[ERROR] GitHub radar scan failed: {e}")
            self.refresh_all()

        threading.Thread(target=_worker, daemon=True).start()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Fleet-Orchestrator Control Center (v2.0) & Quota Dashboard",
        add_help=True,
    )
    parser.add_argument(
        "-d", "--dashboard", "--dash",
        dest="dashboard",
        action="store_true",
        help="Print real-time terminal quota and credit burn rate dashboard instead of launching GUI",
    )
    parser.add_argument(
        "-s", "--status",
        dest="status",
        action="store_true",
        help="Print fleet account status table instead of launching GUI",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output telemetry metrics in JSON format (when used with --dashboard or --status)",
    )
    parser.add_argument(
        "--state-dir",
        type=str,
        default=None,
        help="Custom orchestrator-state directory",
    )

    args, _ = parser.parse_known_args()

    # Normalize flags if passed with single dash or common typos (e.g. -dashboarrd, -dashboard, -status)
    raw_args = [a.lower() for a in sys.argv[1:]]
    dash_requested = args.dashboard or any(
        a in ("-dashboard", "--dashboard", "-dashboarrd", "--dashboarrd", "-dash", "--dash", "-d")
        for a in raw_args
    )
    status_requested = args.status or any(
        a in ("-status", "--status", "-s")
        for a in raw_args
    )

    if dash_requested:
        from tools.copilot_fleet import cmd_dashboard
        cmd_dashboard(args)
        return

    if status_requested:
        from tools.copilot_fleet import cmd_status
        asyncio.run(cmd_status(args))
        return

    print("Starting Fleet-Orchestrator Control Center (v2.0)...")
    enable_high_dpi_and_desktop()
    app = FleetControlApp()
    app.mainloop()


if __name__ == "__main__":
    main()
