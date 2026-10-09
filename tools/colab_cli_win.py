#!/usr/bin/env python3
"""
Windows-Compatible Launcher for Google Colab CLI (`colab`).
Bypasses Unix-only `termios` & `tty` module imports on Windows.
Enables native execution of `colab new`, `colab exec`, `colab run`, `colab stop`, etc.
"""

import sys
from unittest.mock import MagicMock

# Stub Unix-only modules on Windows before importing colab_cli
if sys.platform == "win32":
    if "termios" not in sys.modules:
        sys.modules["termios"] = MagicMock()
    if "tty" not in sys.modules:
        sys.modules["tty"] = MagicMock()

try:
    from colab_cli.cli import main
except ImportError:
    import subprocess
    # Run via uv run if colab_cli is not in local Python environment
    cmd = ["uv", "run", "--with", "google-colab-cli", "python", __file__] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))

if __name__ == "__main__":
    main()
