@echo off
chcp 65001 > nul
echo ===================================================
echo   EDGAR Provider API Server
echo ===================================================
echo 起動しています...
uv run python main.py --api
pause
