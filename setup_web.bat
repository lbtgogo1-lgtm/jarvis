@echo off
setlocal
cd /d "%~dp0"
title JARVIS Web Search Setup
where docker >nul 2>nul
if errorlevel 1 (
    echo Install Docker Desktop for Windows from https://www.docker.com/products/docker-desktop/
    echo Enable Linux containers and the WSL2 backend, then run this script again.
    goto failed
)
docker info >nul 2>nul
if errorlevel 1 (
    echo Start Docker Desktop and wait until the engine is running.
    goto failed
)
if not exist ".venv\Scripts\python.exe" (
    echo Run setup.bat successfully before setup_web.bat.
    goto failed
)
".venv\Scripts\python.exe" -c "import httpx, httpcore, bs4" >nul 2>nul
if errorlevel 1 (
    echo New web dependencies are missing. Run the updated setup.bat first.
    goto failed
)
".venv\Scripts\python.exe" prepare_web.py
if errorlevel 1 goto failed
docker compose -f compose.searxng.yml up -d --wait --wait-timeout 120
if errorlevel 1 goto failed
".venv\Scripts\python.exe" check_web.py
if errorlevel 1 goto failed
echo SearXNG JSON search is ready. In JARVIS settings, enable Internet search and save.
echo Optional: set TAVILY_API_KEY in your environment only if choosing Tavily.
pause
exit /b 0
:failed
echo Web setup or connection check failed. Read the error above.
echo Existing local AI chat remains available. Check Docker logs with:
echo docker compose -f compose.searxng.yml logs --tail 30
pause
exit /b 1
