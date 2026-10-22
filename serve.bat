@echo off
REM serve.bat — One-click Fleet-Orchestrator API Server Launcher
REM Usage:
REM   .\serve.bat              Start on 0.0.0.0:8000 (LAN accessible for mobile Lens)
REM   .\serve.bat --local      Start on 127.0.0.1:8000 only
REM   .\serve.bat --port 9000  Custom port

setlocal enabledelayedexpansion

set "HOST=0.0.0.0"
set "PORT=8000"

:parse_args
if "%~1"=="" goto :start
if /I "%~1"=="--local" ( set "HOST=127.0.0.1" & shift & goto :parse_args )
if /I "%~1"=="--port"  ( set "PORT=%~2" & shift & shift & goto :parse_args )
shift
goto :parse_args

:start
REM Resolve Python
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

title Fleet-Orchestrator API [%HOST%:%PORT%]
echo.
echo  Fleet-Orchestrator API Server
echo  Listening on %HOST%:%PORT%
echo  Mobile Lens: http://192.168.1.5:%PORT%/lens
echo  Health:      http://127.0.0.1:%PORT%/health
echo  QA Status:   http://127.0.0.1:%PORT%/api/v1/qa/status
echo  Press Ctrl+C to stop.
echo.

cd /d "%~dp0"
"%PY%" -m uvicorn server.main:app --host %HOST% --port %PORT%
