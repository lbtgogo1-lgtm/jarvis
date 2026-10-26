@echo off
setlocal
cd /d "%~dp0"
docker compose -f compose.searxng.yml stop
if errorlevel 1 (
    pause
    exit /b 1
)
echo JARVIS SearXNG stopped. Ollama and other projects were not stopped.
