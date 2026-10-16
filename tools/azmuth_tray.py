#!/usr/bin/env python3
"""tools/azmuth_tray.py
---------------------
Windows System Tray Controller for the Azmuth Autonomous Engine.

Features:
1. Live Gear Selection: Whisper (Low Power), Balanced (Auto-Managed), Turbo (High Throughput).
2. Circuit Breaker Watcher: Real-time memory pressure monitoring. Auto-downshifts if RAM drops < 3.0 GB.
3. Pause / Resume Toggle.
4. Immediate Cycle Trigger ("Harvest 1 Task Now", "Run Full Cycle Now").
5. Real-time Status Display in Tray Tooltip & Menu (RAM load, available GB, tasks ingested).
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw

# Root directory anchoring
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pystray
from pystray import MenuItem as item

from tools.azmuth_daemon import (
    GEARS,
    GEAR_FILE,
    PAUSE_FILE,
    RUN_LOG,
    check_and_enforce_gear_safety,
    execute_cycle,
    get_current_gear,
    get_memory_status_gb,
    is_paused,
    set_current_gear,
    set_paused,
)
from tools.azmuth_corpus_harvester import CORPUS_LEDGER, harvest_single_task

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AzmuthTray] %(message)s",
)
logger = logging.getLogger("azmuth_tray")


def create_tray_icon_image(gear: str, paused: bool = False) -> Image.Image:
    """Dynamically generates a crisp 64x64 tray icon based on gear state and pause status."""
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Base color depending on gear
    if paused:
        color = (120, 120, 120)       # Gray
        accent = (200, 80, 80)        # Red accent
    elif gear == "turbo":
        color = (235, 75, 50)         # Crimson / Fire Orange
        accent = (255, 215, 0)        # Gold
    elif gear == "whisper":
        color = (50, 180, 90)         # Emerald Green
        accent = (150, 240, 170)      # Light green
    else:  # balanced
        color = (30, 144, 255)        # Electric Azure Blue
        accent = (0, 215, 255)        # Cyan

    # Outer circle ring
    draw.ellipse((4, 4, size - 4, size - 4), outline=color, width=5)

    # Inner futuristic geometric core (Azmuth Omnitrix / Gear Glyph)
    if paused:
        # Pause bars
        draw.rectangle((22, 18, 28, 46), fill=color)
        draw.rectangle((36, 18, 42, 46), fill=color)
    elif gear == "turbo":
        # Lightning / Warp Arrow
        points = [(32, 12), (44, 28), (34, 28), (40, 52), (20, 32), (30, 32)]
        draw.polygon(points, fill=accent, outline=color)
    elif gear == "whisper":
        # Leaf / Slender diamond
        points = [(32, 14), (46, 32), (32, 50), (18, 32)]
        draw.polygon(points, fill=accent, outline=color)
    else:
        # Balanced hourglass / dual triangles
        tri1 = [(32, 32), (18, 16), (46, 16)]
        tri2 = [(32, 32), (18, 48), (46, 48)]
        draw.polygon(tri1, fill=accent, outline=color)
        draw.polygon(tri2, fill=accent, outline=color)

    return image


class AzmuthTrayApp:
    def __init__(self):
        self.icon: Optional[pystray.Icon] = None
        self._running = True
        self.last_reported_gear = get_current_gear()
        self.last_paused = is_paused()

    def get_ingested_count(self) -> int:
        if CORPUS_LEDGER.exists():
            try:
                data = json.loads(CORPUS_LEDGER.read_text(encoding="utf-8"))
                return len(data.get("tasks_processed", []))
            except Exception:
                pass
        return 0

    def get_status_summary(self) -> str:
        total, avail, load = get_memory_status_gb()
        gear = get_current_gear().upper()
        paused = "PAUSED" if is_paused() else "ACTIVE"
        ingested = self.get_ingested_count()
        return f"Azmuth [{paused}] | Gear: {gear} | Free RAM: {avail:.1f}GB ({load}%) | CP: {ingested} tasks"

    def on_set_gear(self, gear_name: str):
        def handler(icon, item):
            set_current_gear(gear_name, reason="Tray Menu Selection")
            self.update_icon()
        return handler

    def on_toggle_pause(self, icon, item):
        currently_paused = is_paused()
        set_paused(not currently_paused, reason="Tray Menu Toggle")
        self.update_icon()

    def on_harvest_single(self, icon, item):
        threading.Thread(target=harvest_single_task, daemon=True).start()

    def on_run_cycle(self, icon, item):
        threading.Thread(target=execute_cycle, daemon=True).start()

    def on_quit(self, icon, item):
        self._running = False
        if self.icon:
            self.icon.stop()

    def update_icon(self):
        if not self.icon:
            return
        current_gear = get_current_gear()
        paused = is_paused()
        self.icon.icon = create_tray_icon_image(current_gear, paused=paused)
        self.icon.title = self.get_status_summary()
        self.icon.menu = self.build_menu()

    def build_menu(self) -> pystray.Menu:
        total, avail, load = get_memory_status_gb()
        ingested = self.get_ingested_count()

        def is_gear_checked(gear_name: str):
            return lambda item: get_current_gear() == gear_name

        def is_paused_checked(item):
            return is_paused()

        return pystray.Menu(
            item(f"Azmuth Engine: {'PAUSED' if is_paused() else 'ACTIVE'}", lambda icon, item: None, enabled=False),
            item(f"RAM: {avail:.1f}GB free / {total:.1f}GB ({load}% load)", lambda icon, item: None, enabled=False),
            item(f"CP Corpus: {ingested} tasks cataloged", lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("🚀 Turbo Mode (Warp / Fast Ingest)", self.on_set_gear("turbo"), checked=is_gear_checked("turbo"), radio=True),
            item("⚡ Balanced Mode (Auto-Managed)", self.on_set_gear("balanced"), checked=is_gear_checked("balanced"), radio=True),
            item("🌱 Whisper Mode (Low Power / Quiet)", self.on_set_gear("whisper"), checked=is_gear_checked("whisper"), radio=True),
            pystray.Menu.SEPARATOR,
            item("⏸️ Pause Azmuth Background", self.on_toggle_pause, checked=is_paused_checked),
            pystray.Menu.SEPARATOR,
            item("▶️ Harvest 1 Task Now", self.on_harvest_single),
            item("🔄 Run Verification Cycle Now", self.on_run_cycle),
            pystray.Menu.SEPARATOR,
            item("❌ Exit System Tray Icon", self.on_quit),
        )

    def background_monitor_loop(self):
        """Monitors circuit breaker and refreshes tray state every 3 seconds."""
        while self._running:
            try:
                # Enforce circuit breaker safety
                check_and_enforce_gear_safety()
                current_gear = get_current_gear()
                paused = is_paused()

                # If gear or pause state changed externally (e.g. CLI or circuit breaker), refresh icon
                if current_gear != self.last_reported_gear or paused != self.last_paused:
                    self.last_reported_gear = current_gear
                    self.last_paused = paused
                    self.update_icon()

                if self.icon:
                    self.icon.title = self.get_status_summary()
            except Exception as e:
                logger.debug(f"Background monitor tick error: {e}")

            time.sleep(3)

    def run(self):
        initial_gear = get_current_gear()
        initial_paused = is_paused()
        image = create_tray_icon_image(initial_gear, paused=initial_paused)

        self.icon = pystray.Icon(
            "AzmuthEngine",
            image,
            self.get_status_summary(),
            menu=self.build_menu(),
        )

        monitor_thread = threading.Thread(target=self.background_monitor_loop, daemon=True)
        monitor_thread.start()

        logger.info("Azmuth System Tray Controller started.")
        self.icon.run()


if __name__ == "__main__":
    app = AzmuthTrayApp()
    app.run()
