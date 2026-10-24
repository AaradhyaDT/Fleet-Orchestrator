@echo off
REM Fleet-Orchestrator Zero-Distraction CLI Wrapper
REM Usage:
REM   .\fleet.bat status
REM   .\fleet.bat run-task --spec "..."
REM   .\fleet.bat submit --spec "..."
REM   .\fleet.bat tasks
REM   .\fleet.bat reconcile
REM   .\fleet.bat watch
REM   .\fleet.bat copilot-prompt "..."
REM   .\fleet.bat copilot status

setlocal enabledelayedexpansion

REM Resolve Python interpreter: check .venv then global python
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

if /I "%~1"=="job" goto :fleet_job
if /I "%~1"=="accounts" goto :fleet_accounts
if /I "%~1"=="agy" goto :fleet_agy
if /I "%~1"=="agy-chat" goto :fleet_agy_chat
if /I "%~1"=="agy-profile" goto :fleet_agy_profile
if /I "%~1"=="copilot" goto :fleet_copilot
if /I "%~1"=="copilot-prompt" goto :fleet_copilot_prompt
if /I "%~1"=="copilot-rotator" goto :fleet_copilot_rotator

"%PY_CMD%" -u "%~dp0tools\unified_fleet_cli.py" %*
goto :eof

:fleet_job
"%PY_CMD%" -u "%~dp0tools\fleet_jobs.py" %2 %3 %4 %5 %6 %7 %8 %9
goto :eof

:fleet_accounts
"%PY_CMD%" -u "%~dp0tools\fleet_accounts.py" %*
exit /b %errorlevel%

:fleet_agy
"%PY_CMD%" -u "%~dp0tools\agy_rotator.py" exec -p %2 %3 %4 %5 %6 %7 %8 %9
exit /b %errorlevel%

:fleet_agy_chat
"%PY_CMD%" -u "%~dp0tools\agy_rotator.py" chat %2 %3 %4 %5 %6 %7 %8 %9
exit /b %errorlevel%

:fleet_agy_profile
"%PY_CMD%" -u "%~dp0tools\agy_rotator.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %errorlevel%

:fleet_copilot
"%PY_CMD%" -u "%~dp0tools\copilot_fleet.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %errorlevel%

:fleet_copilot_prompt
"%PY_CMD%" -u "%~dp0tools\copilot_rotator.py" exec -p %2 %3 %4 %5 %6 %7 %8 %9
exit /b %errorlevel%

:fleet_copilot_rotator
"%PY_CMD%" -u "%~dp0tools\copilot_rotator.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %errorlevel%
