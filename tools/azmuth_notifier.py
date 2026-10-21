#!/usr/bin/env python3
"""tools/azmuth_notifier.py
-------------------------
Lightweight, non-blocking Windows native Toast Notification dispatcher
for high-salience Azmuth radar opportunities.

Uses PowerShell Windows.UI.Notifications WinRT API headlessly with 0 external dependencies.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
NOTIFICATION_CACHE = ROOT / "orchestrator-state" / "azmuth_notified_cache.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AzmuthNotifier] %(message)s",
)
logger = logging.getLogger("azmuth_notifier")


def _load_notified_ids() -> set[str]:
    if NOTIFICATION_CACHE.exists():
        try:
            data = json.loads(NOTIFICATION_CACHE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return set(data)
        except Exception as e:
            logger.warning("Failed to load notified cache: %s", e)
    return set()


def _save_notified_id(item_id: str) -> None:
    try:
        notified = _load_notified_ids()
        notified.add(item_id)
        # Keep last 500 items
        trimmed = list(notified)[-500:]
        NOTIFICATION_CACHE.write_text(json.dumps(trimmed, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to save notified id: %s", e)


def notify_opportunity(
    title: str,
    message: str,
    item_id: Optional[str] = None,
    url: Optional[str] = None,
    force: bool = False,
) -> bool:
    """Dispatches a non-intrusive Windows toast notification for an opportunity.
    
    Deduplicates based on item_id unless force=True.
    """
    if sys.platform != "win32":
        logger.info("[MockToast] %s - %s", title, message)
        return True

    if item_id and not force:
        notified = _load_notified_ids()
        if item_id in notified:
            logger.debug("Item %s already notified, skipping.", item_id)
            return False

    # Clean strings for PowerShell script
    safe_title = title.replace('"', '`"').replace("$", "`$")
    safe_msg = message.replace('"', '`"').replace("$", "`$")

    ps_script = f"""
$ErrorActionPreference = 'SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{safe_title}</text>
            <text>{safe_msg}</text>
        </binding>
    </visual>
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Azmuth Radar")
$notifier.Show($toast)
"""

    try:
        # Non-blocking headless execution
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if item_id:
            _save_notified_id(item_id)
        logger.info("Dispatched notification for: %s", title)
        return True
    except Exception as e:
        logger.warning("Failed to dispatch Windows toast: %s", e)
        return False


if __name__ == "__main__":
    test_id = "test_manual_invocation"
    notify_opportunity(
        title="Azmuth Radar Active",
        message="Windows Toast Dispatcher verified and operational.",
        item_id=test_id,
        force=True,
    )
    print("Notification dispatched successfully.")
