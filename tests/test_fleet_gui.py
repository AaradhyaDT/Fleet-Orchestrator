from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.fleet_gui import FleetControlApp, enable_high_dpi_and_desktop


def test_enable_high_dpi_and_desktop_safe():
    # Should not raise any unhandled exceptions
    res = enable_high_dpi_and_desktop()
    assert isinstance(res, bool)


def test_fleet_control_app_instantiation():
    # Verify FleetControlApp initializes, binds widgets, and applies theme without crashing
    try:
        app = FleetControlApp()
        app.update_idletasks()

        # Check essential UI components exist
        assert hasattr(app, "kpi_capacity")
        assert hasattr(app, "kpi_consumed")
        assert hasattr(app, "kpi_remaining")
        assert hasattr(app, "canvas_burn")
        assert hasattr(app, "tree_workers")
        assert hasattr(app, "tree_tasks")
        assert hasattr(app, "tree_batches")
        assert hasattr(app, "worker_insp_frame")
        assert hasattr(app, "batch_insp_frame")
        assert hasattr(app, "log_text")

        # Test heartbeat formatting
        assert app._format_worker_heartbeat(None) == "-"
        assert app._format_worker_heartbeat("") == "-"

        # Verify dispatcher column in tasks table
        assert "dispatcher" in app.tree_tasks["columns"]
        # Verify elapsed column in workers table
        assert "elapsed" in app.tree_workers["columns"]
        # Verify batch columns
        assert "batch_id" in app.tree_batches["columns"]
        assert "dispatcher" in app.tree_batches["columns"]

        # Test refresh execution
        app.refresh_all()
        app.update_idletasks()

        # Test logging
        app.log("Test log entry", level="INFO")
        log_content = app.log_text.get("1.0", "end-1c")
        assert "Test log entry" in log_content

        app.destroy()
    except Exception as e:
        # If running in a headless CI environment with no display
        if "no display name" in str(e).lower() or "display" in str(e).lower():
            pytest.skip("No graphical display available in current environment")
        else:
            raise e


def test_httpx_logging_suppressed():
    import logging
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING


def test_fleet_gui_cli_dashboard_flag():
    from tools.fleet_gui import main

    with patch("tools.copilot_fleet.cmd_dashboard") as mock_dash:
        with patch.object(sys, "argv", ["fleet_gui.py", "--dashboard"]):
            main()
            mock_dash.assert_called_once()

    with patch("tools.copilot_fleet.cmd_dashboard") as mock_dash:
        with patch.object(sys, "argv", ["fleet_gui.py", "-dashboarrd"]):
            main()
            mock_dash.assert_called_once()


def test_fleet_gui_cli_status_flag():
    from tools.fleet_gui import main

    with patch("tools.copilot_fleet.cmd_status") as mock_status:
        with patch.object(sys, "argv", ["fleet_gui.py", "-status"]):
            main()
            mock_status.assert_called_once()

