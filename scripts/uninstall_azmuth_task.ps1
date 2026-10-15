# scripts/uninstall_azmuth_task.ps1
# Unregisters FleetAzmuthDaemon from HKCU Run key cleanly

$ErrorActionPreference = "SilentlyContinue"

$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $RunKey -Name "FleetAzmuthDaemon" -ErrorAction SilentlyContinue

Write-Host "[+] Unregistered FleetAzmuthDaemon from HKCU Run key." -ForegroundColor Yellow
