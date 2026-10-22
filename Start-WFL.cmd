@echo off
cd /d "%~dp0"
if exist "%~dp0release\OTONova-Windows-V1.0\OTONova.exe" (
  start "" "%~dp0release\OTONova-Windows-V1.0\OTONova.exe"
) else (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0vcv_gui.py"
)
