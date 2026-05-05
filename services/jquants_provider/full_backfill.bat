@echo off
setlocal
cd /d %~dp0

echo [J-Quants Provider] Starting Full Backfill...
echo Logs will be displayed here and saved to logs/app.log

set "PYTHONUNBUFFERED=1"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

:: 1. Sync Tickers
echo [%DATE% %TIME%] Syncing Tickers...
"%PYTHON_EXE%" main.py --sync-tickers

:: 2. Sync Daily Prices
echo [%DATE% %TIME%] Syncing Daily Prices (730 days window)...
"%PYTHON_EXE%" main.py --sync-prices --limit 730

:: 3. Sync Financial Summaries
echo [%DATE% %TIME%] Syncing Financial Summaries (730 days window)...
"%PYTHON_EXE%" main.py --sync-market --limit 730

:: 4. Sync Dividends
echo [%DATE% %TIME%] Syncing Dividends...
"%PYTHON_EXE%" main.py --sync-dividends

:: 5. Sync Indices
echo [%DATE% %TIME%] Syncing Indices (730 days window)...
"%PYTHON_EXE%" main.py --sync-indices --limit 730

echo [%DATE% %TIME%] Full Backfill Process Completed.
pause
