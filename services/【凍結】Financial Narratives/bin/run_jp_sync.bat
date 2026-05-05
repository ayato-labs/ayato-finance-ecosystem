@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo ======================================================
echo Launching JP Sync Pipeline (Multi-Window Mode)
echo ======================================================

:: 従来の start コマンドを使用（確実性を優先）
start "Ingestion-JP" cmd /k "uv run python main.py --market jp --sync"
start "Worker-JP-1" cmd /k "uv run python -m src.structuring_worker --market jp --workers 5"
start "Worker-JP-2" cmd /k "uv run python -m src.structuring_worker --market jp --workers 5"
start "Writer" cmd /k "uv run python -m src.writer"

echo.
echo JP Sync processes have been launched in separate windows.
exit
