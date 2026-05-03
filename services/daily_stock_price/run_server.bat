@echo off
REM Daily Stock Price DB - API Server
SET PORT=5005
echo ==========================================
echo Starting API Server (Port: %PORT%)...
echo ==========================================
uv run python main.py --api --port %PORT% --host 127.0.0.1
pause
