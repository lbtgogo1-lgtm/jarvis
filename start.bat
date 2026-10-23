@echo off
setlocal
cd /d "%~dp0"
title JARVIS
if not exist ".venv\Scripts\python.exe" goto missing_python
if not exist "dist\index.html" goto missing_frontend
".venv\Scripts\python.exe" -u windows_launcher.py start
set "JARVIS_EXIT=%ERRORLEVEL%"
if "%JARVIS_EXIT%"=="0" exit /b 0
echo.
echo JARVIS could not start. Read the error above.
echo Server details, if available: data\startup.log
pause
exit /b %JARVIS_EXIT%

:missing_python
echo Python environment is missing. Run setup.bat in this folder first.
echo Wait for "Setup complete" before running start.bat again.
goto failed

:missing_frontend
echo The interface has not been built. Run setup.bat in this folder first.
echo Wait for "Setup complete" before running start.bat again.

:failed
echo.
pause
exit /b 1
