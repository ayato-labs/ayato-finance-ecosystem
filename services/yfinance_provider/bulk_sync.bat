@echo off
echo ==================================================
echo   yfinance Local Mirror: FULL BULK SYNC
echo   Target: 4444 Tickers (5 Years History)
echo ==================================================
set PYTHONPATH=%PYTHONPATH%;%CD%
uv run python -m src.collector.main --force --workers 8
pause
