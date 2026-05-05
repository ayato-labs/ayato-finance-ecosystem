@echo off
setlocal
cd /d %~dp0\..

echo ======================================================
echo Starting Financial Narratives API Server
echo ======================================================

:: APIサーバーの起動 (FastAPI + Uvicorn)
:: ポート番号などは src/api/main.py や環境変数に従う
uv run python -m uvicorn src.api.main:app --host 0.0.0.0 --port 5013 --reload

pause
