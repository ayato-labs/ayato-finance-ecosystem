@echo off
echo ==================================================
echo   yfinance Local Mirror: API SERVER
echo   Endpoint: http://localhost:5015
echo ==================================================
set PYTHONPATH=%PYTHONPATH%;%CD%
uv run python -m src.api.main
pause
