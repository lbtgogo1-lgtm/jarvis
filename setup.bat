@echo off
setlocal
cd /d "%~dp0"
title JARVIS Setup
set "JARVIS_PYTHON="
set "JARVIS_CREATE_ENV=1"
if exist ".venv\Scripts\python.exe" goto existing_environment
py -3.12 --version >nul 2>nul && set "JARVIS_PYTHON=py -3.12"
if defined JARVIS_PYTHON goto python_found
py -3.11 --version >nul 2>nul && set "JARVIS_PYTHON=py -3.11"
if defined JARVIS_PYTHON goto python_found
python -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3,11),(3,12)] else 1)" >nul 2>nul
if not errorlevel 1 set "JARVIS_PYTHON=python"
if defined JARVIS_PYTHON goto python_found
echo Install Python 3.11 or 3.12 with the Python launcher or Add to PATH enabled.
goto failed

:existing_environment
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3,11),(3,12)] else 1)" >nul 2>nul
if errorlevel 1 (
    echo The existing .venv is broken or uses an unsupported Python version.
    echo Rename the .venv folder, then run setup.bat again with Python 3.11 or 3.12.
    goto failed
)
set "JARVIS_CREATE_ENV=0"

:python_found
node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 22 ? 0 : 1)" >nul 2>nul
if errorlevel 1 (
    echo Install Node.js 22 LTS or newer, then open setup.bat again.
    goto failed
)
echo [1/4] Preparing Python environment...
if "%JARVIS_CREATE_ENV%"=="0" goto install_dependencies
%JARVIS_PYTHON% -m venv .venv
if errorlevel 1 goto failed
:install_dependencies
echo [2/4] Installing Python dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo [3/4] Installing frontend dependencies...
call npm ci
if errorlevel 1 goto failed
echo [4/4] Building the interface...
call npm run build
if errorlevel 1 goto failed
where ollama >nul 2>nul || echo Install Ollama from https://ollama.com
echo Run manually if the model is missing: ollama pull qwen3:8b
echo For offline STT model preparation see README.md
echo Setup complete. You can now run start.bat.
pause
exit /b 0

:failed
echo.
echo Setup failed. Read the error above. Do not run start.bat until setup completes.
pause
exit /b 1
