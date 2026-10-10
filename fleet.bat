@echo off
REM Fleet-Orchestrator Zero-Distraction CLI Wrapper
REM Usage:
REM   .\fleet.bat status
REM   .\fleet.bat submit --spec "..."
REM   .\fleet.bat tasks
REM   .\fleet.bat reconcile
REM   .\fleet.bat watch

setlocal enabledelayedexpansion

REM Resolve Python interpreter: check .venv then global python
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

"%PY_CMD%" "%~dp0tools\unified_fleet_cli.py" %*
