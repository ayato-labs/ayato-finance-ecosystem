@echo off
setlocal
cd /d %~dp0\..

echo ======================================================
echo Launching Financial Narratives API Server
echo ======================================================

:: APIサーバーを起動
uv run python main.py --api --port 5013

pause
