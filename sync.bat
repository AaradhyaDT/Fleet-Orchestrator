@echo off
setlocal
REM ============================================================================
REM sync.bat - Zero-Friction Execution Wrapper for sync.ps1
REM Automatically bypasses PowerShell ExecutionPolicy across fresh clones/devices.
REM Options:
REM   .\sync.bat                     - Safe auto-commit with secret scanning & push
REM   .\sync.bat -m "msg"            - Custom commit message
REM   .\sync.bat -SkipCI / -NoCI     - Fast day-to-day sync (appends [skip ci])
REM   .\sync.bat -PullOnly           - Rebase and pull from origin without committing
REM ============================================================================

where pwsh >nul 2>nul
if %ERRORLEVEL% equ 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync.ps1" %*
)
exit /b %ERRORLEVEL%