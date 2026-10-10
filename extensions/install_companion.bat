@echo off
REM Fleet-Orchestrator VS Code Companion Installer
REM Links the zero-compilation extension into VS Code's extensions directory.

set "TARGET_DIR=%USERPROFILE%\.vscode\extensions\fleet-companion"
set "SOURCE_DIR=%~dp0vscode-fleet-companion"

echo [*] Installing Fleet Swarm Companion to: %TARGET_DIR%

if not exist "%USERPROFILE%\.vscode\extensions" (
    mkdir "%USERPROFILE%\.vscode\extensions"
)

if exist "%TARGET_DIR%" (
    echo [*] Removing existing installation...
    rmdir "%TARGET_DIR%" 2>nul || rmdir /s /q "%TARGET_DIR%" 2>nul
)

echo [*] Creating NTFS Junction...
mklink /J "%TARGET_DIR%" "%SOURCE_DIR%" >nul 2>&1

if exist "%TARGET_DIR%\extension.js" (
    echo [OK] Successfully linked via NTFS Junction!
) else (
    echo [*] Falling back to file copy...
    xcopy /E /I /Y "%SOURCE_DIR%" "%TARGET_DIR%" >nul
    echo [OK] Successfully copied extension files!
)

echo.
echo ==============================================================================
echo  Fleet Swarm Companion installed!
echo  Open or reload VS Code to see:
echo    - Bottom Status Bar: $(zap) Fleet: 10 Gemini ^| 27 Copilot
echo    - Activity Bar: 'Fleet Swarm' sidebar TreeView
echo    - Quick Actions: Click status bar or press Ctrl+Shift+P -^> 'Fleet'
echo ==============================================================================
