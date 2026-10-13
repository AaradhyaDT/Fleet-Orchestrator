@echo off
REM Fleet-Orchestrator Zero-Distraction CLI Wrapper
REM Usage:
REM   .\fleet.bat status
REM   .\fleet.bat run-task --spec "..."
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

if /I "%~1"=="job" goto :fleet_job

"%PY_CMD%" -u "%~dp0tools\unified_fleet_cli.py" %*
goto :eof

:fleet_job
"%PY_CMD%" -u "%~dp0tools\fleet_jobs.py" %2 %3 %4 %5 %6 %7 %8 %9
goto :eof
