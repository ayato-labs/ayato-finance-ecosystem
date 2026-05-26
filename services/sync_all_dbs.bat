@echo off
setlocal enabledelayedexpansion

REM ===================================================================
REM   Workspace Master Database Sync Script
REM   Synchronizes all local databases across the finance workspace.
REM ===================================================================

echo [START] Workspace-wide Database Synchronization
echo Date: %DATE% %TIME%
echo.

REM 1. Financial Figures (Main DB + EDINET Reconciler)
echo [1/8] Syncing Financial Figures (Incremental US/JP/EDINET)...
pushd "Financial Figures"
uv run python main.py --sync-market all --incremental
popd
echo.

REM 2. Daily Stock Price (High-Compression DuckDB)
echo [2/8] Syncing Daily Stock Price (All Markets)...
pushd "daily_stock_price"
uv run python main.py --sync-market all --workers 5
popd
echo.

REM 3. yfinance Provider (Mirror DB)
echo [3/8] Syncing yfinance Provider Mirror...
pushd "yfinance_provider"
set PYTHONPATH=.
uv run python -m src.collector.main --workers 16
popd
echo.

REM 4. EDINET Provider (Datalake Ingestion)
echo [4/8] Syncing EDINET Provider Datalake...
pushd "edinet_provider"
uv run python -m src.datalake.cli --market --days 7
popd
echo.

REM 5. Financial Narratives (Qualitative Data)
echo [5/8] Syncing Financial Narratives (US/JP Recent)...
pushd "Financial Narratives"
set PYTHONPATH=.
uv run python src/batch_fetch.py --days 7
popd
echo.

REM 6. Macro Economic Data (FRED)
echo [6/8] Syncing Macro Economic Data (DFF, DGS10)...
pushd "macro"
uv run python main.py sync
popd
echo.

REM 7. Market Index Data
echo [7/8] Syncing Market Index Data (^GSPC)...
pushd "index"
uv run python main.py sync
popd
echo.

REM 8. Forex Data
echo [8/8] Syncing Forex Data (JPY, EUR, CNY)...
pushd "forex"
uv run python main.py sync
popd
echo.

echo ===================================================================
echo [COMPLETE] All databases synchronized.
echo Check the individual 'logs/' directories for detailed JSON traces.
echo ===================================================================
pause
