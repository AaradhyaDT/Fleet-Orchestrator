@echo off
title Azmuth Tray Launcher
powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0tools\azmuth_tray.ps1"
exit /b 0
