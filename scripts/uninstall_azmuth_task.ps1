# scripts/uninstall_azmuth_task.ps1
# Unregisters FleetAzmuthDaemon and FleetAzmuthTray from HKCU Run key cleanly

$ErrorActionPreference = "SilentlyContinue"

$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $RunKey -Name "FleetAzmuthDaemon" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path $RunKey -Name "FleetAzmuthTray" -ErrorAction SilentlyContinue

Write-Host "[+] Unregistered FleetAzmuthDaemon and FleetAzmuthTray from HKCU Run key." -ForegroundColor Yellow
