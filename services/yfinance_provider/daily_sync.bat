@echo off
echo ==================================================
echo   yfinance Local Mirror: DAILY INCREMENTAL SYNC
echo   Skips tickers synced within the last 24 hours
echo ==================================================
set PYTHONPATH=%PYTHONPATH%;%CD%
uv run python -m src.collector.main --workers 16
pause
