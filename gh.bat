@echo off
setlocal
REM ============================================================================
REM gh.bat - Zero-Friction Execution Wrapper for gh.ps1 (github-workflow)
REM Automatically bypasses PowerShell ExecutionPolicy, forces BOM-less UTF-8,
REM intercepts inline --body payloads into --body-file (INV-GH-BODY-FILE),
REM and provides github-workflow SOP shortcuts.
REM
REM Usage:
REM   .\gh.bat --gh-help                                      (wrapper help)
REM   .\gh.bat issue list                                     (raw gh pass-through)
REM   .\gh.bat issue-create --title "..." --type Feature ...  (SOP issue creation)
REM   .\gh.bat task --issue 28 --list                         (checklist toggler)
REM   .\gh.bat sub-issue --parent 28 --child 29               (GraphQL sub-issue)
REM   .\gh.bat close-verified 28 --comment "..."              (SHA-verified close)
REM ============================================================================

if "%~1"=="" goto :wrapper_help
if /I "%~1"=="/?" goto :wrapper_help
if /I "%~1"=="-help" goto :wrapper_help
if /I "%~1"=="--gh-help" goto :wrapper_help
if /I "%~1"=="-HelpWrapper" goto :wrapper_help

where pwsh >nul 2>nul
if %ERRORLEVEL% equ 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0gh.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gh.ps1" %*
)
exit /b %ERRORLEVEL%

:wrapper_help
where pwsh >nul 2>nul
if %ERRORLEVEL% equ 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0gh.ps1" wrapper-help
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gh.ps1" wrapper-help
)
exit /b %ERRORLEVEL%
