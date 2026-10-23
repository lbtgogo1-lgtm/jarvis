@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & exit /b 1)
if not exist dist\index.html (echo Run setup.bat first. & exit /b 1)
.venv\Scripts\python windows_launcher.py start
