' Silent Background Launcher for Azmuth Tray Controller
' Launches azmuth_tray.ps1 completely hidden with zero console window or taskbar button.
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
TrayScript = ScriptDir & "\tools\azmuth_tray.ps1"

WshShell.Run "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & TrayScript & """", 0, False
