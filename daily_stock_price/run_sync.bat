@echo off
REM Daily Stock Price DB - Market Sync
echo ==========================================
echo Starting Market Delta Sync...
echo ==========================================
uv run python main.py --sync-market all --workers 5
echo.
echo ==========================================
echo Sync Complete.
echo ==========================================
pause
