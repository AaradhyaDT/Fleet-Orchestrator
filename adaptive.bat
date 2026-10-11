@echo off
REM ============================================================================
REM adaptive.bat - Zero-Friction Launcher for /adaptive-workflow Orchestrator
REM ============================================================================

set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%tools\adaptive_engine.py" %*
