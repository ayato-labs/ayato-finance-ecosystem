@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo ======================================================
echo Launching US Sync Pipeline (Multi-Window Mode)
echo ======================================================

start "Ingestion-US" cmd /k "uv run python main.py --market us --sync"
start "Worker-US-1" cmd /k "uv run python -m src.structuring_worker --market us --workers 5"
start "Worker-US-2" cmd /k "uv run python -m src.structuring_worker --market us --workers 5"
start "Writer" cmd /k "uv run python -m src.writer"

echo.
echo US Sync processes have been launched in separate windows.
exit
