@echo off
setlocal
cd /d "%~dp0"
python tools\fleet_gui.py %*
