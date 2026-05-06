@echo off
setlocal
cd /d %~dp0

echo ========================================================
echo J-Quants Data Smart Differential Sync
echo ========================================================
echo.

:: Check for virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv directory.
    pause
    exit /b 1
)

set PYTHON_EXE=.venv\Scripts\python.exe

echo [1/3] Syncing Ticker Master...
%PYTHON_EXE% main.py --sync-tickers
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Ticker sync encountered an issue. Continuing...
)

echo.
echo [2/3] Syncing Stock Prices (Differential)...
%PYTHON_EXE% main.py --sync-prices
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Price sync failed. Check logs/error.log for details.
)

echo.
echo [3/3] Syncing Market Financials (Differential)...
%PYTHON_EXE% main.py --sync-market
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Financials sync failed. Check logs/error.log for details.
)

echo.
echo ========================================================
echo Sync process completed.
echo Check logs/app.log for performance metrics.
echo ========================================================
pause
