@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
uv run --with google-colab-cli python "%~dp0tools\colab_cli_win.py" %*
endlocal
