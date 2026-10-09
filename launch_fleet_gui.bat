@echo off
setlocal
cd /d "%~dp0"
echo Starting Fleet-Orchestrator Control Center (v2.0)...
python tools\fleet_gui.py %*
