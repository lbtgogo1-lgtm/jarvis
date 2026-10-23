@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.11+ is required. & exit /b 1)
where node >nul 2>nul || (echo Install Node.js LTS first. & exit /b 1)
python -m venv .venv || exit /b 1
.venv\Scripts\python -m pip install -r requirements.txt || exit /b 1
call npm ci || exit /b 1
call npm run build || exit /b 1
where ollama >nul 2>nul || echo Install Ollama from https://ollama.com
 echo Run manually after approval: ollama pull qwen3:8b
 echo For offline STT model preparation see README.md
 echo Setup complete.
