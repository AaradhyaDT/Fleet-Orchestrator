"""tests/test_azmuth_cli.py
-------------------------
Unit tests verifying the Azmuth global CLI dispatcher.
"""

import sys
from unittest.mock import patch
import pytest

from tools import azmuth_cli


def test_azmuth_cli_help(capsys):
    """Test that --help prints available subcommands cleanly."""
    with patch.object(sys, "argv", ["azmuth", "--help"]):
        with pytest.raises(SystemExit) as excinfo:
            azmuth_cli.main()
        assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "sweep" in captured.out
    assert "cbf" in captured.out
    assert "live" in captured.out
    assert "sde" in captured.out
    assert "gate" in captured.out
    assert "trigger" in captured.out


def test_azmuth_cli_no_args_launches_gui():
    """Running azmuth with 0 args should invoke launch_gui."""
    with patch.object(sys, "argv", ["azmuth"]), patch("tools.azmuth_cli.launch_gui", return_value=0) as mock_gui:
        code = azmuth_cli.main()
        assert code == 0
        mock_gui.assert_called_once()


def test_azmuth_cli_explicit_gui_subcommand():
    """Running azmuth gui should invoke launch_gui."""
    with patch.object(sys, "argv", ["azmuth", "gui"]), patch("tools.azmuth_cli.launch_gui", return_value=0) as mock_gui:
        code = azmuth_cli.main()
        assert code == 0
        mock_gui.assert_called_once()


def test_azmuth_cli_cbf_subcommand(capsys):
    """Running azmuth cbf runs the CBF governor."""
    with patch.object(sys, "argv", ["azmuth", "cbf"]):
        code = azmuth_cli.main()
        assert code == 0
    captured = capsys.readouterr()
    assert "AZMUTH CONTROL BARRIER FUNCTION" in captured.out
