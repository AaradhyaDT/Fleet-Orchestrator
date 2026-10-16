# scripts/install_azmuth_task.ps1
# Installs FleetAzmuthDaemon to run at Windows User Startup and execute quietly in the background.

$ErrorActionPreference = "Stop"

$RepoRoot = "F:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator"
$PythonExe = (Get-Command python.exe).Source
$PythonwExe = Join-Path (Split-Path $PythonExe) "pythonw.exe"
$ActionExe = if (Test-Path $PythonwExe) { $PythonwExe } else { $PythonExe }
$ScriptPath = Join-Path $RepoRoot "tools\azmuth_daemon.py"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  INSTALLING FLEET AZMUTH DAEMON (WINDOWS BACKGROUND)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Repository Root : $RepoRoot"
Write-Host "  Python Binary   : $ActionExe"
Write-Host "  Target Script   : $ScriptPath"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Azmuth Daemon script not found at $ScriptPath"
}

# 1. Register Daemon in HKCU Startup Run key (runs windowlessly on logon and keeps daily loop alive)
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$RunCommand = "`"$ActionExe`" `"$ScriptPath`" --loop --interval-hours 24"

Set-ItemProperty -Path $RunKey -Name "FleetAzmuthDaemon" -Value $RunCommand
Write-Host "[+] Successfully registered in HKCU Run Key: FleetAzmuthDaemon" -ForegroundColor Green
Write-Host "    Value: $RunCommand" -ForegroundColor Gray

# 2. Register Tray Controller in HKCU Startup Run key
$TrayScriptPath = Join-Path $RepoRoot "tools\azmuth_tray.py"
if (Test-Path $TrayScriptPath) {
    $TrayRunCommand = "`"$ActionExe`" `"$TrayScriptPath`""
    Set-ItemProperty -Path $RunKey -Name "FleetAzmuthTray" -Value $TrayRunCommand
    Write-Host "[+] Successfully registered in HKCU Run Key: FleetAzmuthTray" -ForegroundColor Green
    Write-Host "    Value: $TrayRunCommand" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[OK] Fleet Azmuth Daemon & System Tray successfully armed." -ForegroundColor Cyan
Write-Host "    - Runs windowlessly on Windows logon"
Write-Host "    - System tray icon provides instant Speed Gear toggle & RAM circuit breaker"
Write-Host "    - Executes daily cycle every 24 hours"
Write-Host "    - Senses gaps, resolves with Gemini 3.8 Flash, and runs zero-token local audits."
