@echo off
setlocal enabledelayedexpansion

REM ===================================================================
REM   Workspace Master Database Sync Script
REM   Synchronizes all local databases across the finance workspace.
REM ===================================================================

echo [START] Workspace-wide Database Synchronization
echo Date: %DATE% %TIME%
echo.

REM 1. J-Quants Provider (Historical & API Data)
echo [1/7] Syncing J-Quants API Data...
pushd "jquants_provider"
uv run python main.py --sync-tickers
popd
echo.

REM 2. EDINET Provider (Datalake & Narrative Data)
echo [2/7] Syncing EDINET Datalake...
pushd "edinet_provider"
uv run python -m src.datalake.cli --market --days 7
popd
echo.

REM 3. EDGAR Provider (US Statutory Data)
echo [3/7] Syncing SEC EDGAR Data...
pushd "edgar_provider"
uv run python main.py sync --days 7
popd
echo.

REM 4. yfinance Provider (Stock Prices & Financials)
echo [4/7] Syncing yfinance Data (US/JP Market)...
pushd "yfinance_provider"
set PYTHONPATH=.
uv run python -m src.collector.main --sync-market all --workers 8
popd
echo.

REM 6. Macro Economic Data (FRED)
echo [6/7] Syncing Macro Economic Data (DFF, DGS10)...
pushd "macro"
uv run python main.py sync
popd
echo.

REM 7. Market Index Data
echo [7/7] Syncing Market Index Data (^GSPC)...
pushd "index"
uv run python main.py sync
popd
echo.

echo ===================================================================
echo [COMPLETE] All databases synchronized.
echo Check the individual 'logs/' directories for detailed JSON traces.
echo ===================================================================
pause
