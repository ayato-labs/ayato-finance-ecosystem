@echo off
setlocal enabledelayedexpansion

REM ===================================================================
REM   Ayato Finance Ecosystem - Sequential Market Sync Master
REM   Synchronizes all financial data services in a serial order.
REM   Parallelization is handled internally by each service.
REM ===================================================================

echo [START] Workspace-wide Database Synchronization
echo Date: %DATE% %TIME%
echo.

pushd "services"

REM 1. J-Quants Provider (JP Market Tickers & Statements)
echo [1/8] Syncing J-Quants API Data...
if exist "jquants_provider" (
    pushd "jquants_provider"
    uv run python main.py --sync-tickers --sync-daily
    popd
) else (
    echo [SKIP] jquants_provider not found.
)
echo.

REM 2. EDINET Provider (JP Financial Datalake)
echo [2/8] Syncing EDINET Datalake...
if exist "edinet_provider" (
    pushd "edinet_provider"
    REM Removed fixed --days to trigger smart discovery from last DB record
    uv run python -m src.datalake.cli --market
    popd
) else (
    echo [SKIP] edinet_provider not found.
)
echo.

REM 3. EDGAR Provider (US Filing Data)
echo [3/8] Syncing SEC EDGAR Data...
if exist "edgar_provider" (
    pushd "edgar_provider"
    uv run python main.py sync --days 7
    popd
) else (
    echo [SKIP] edgar_provider not found.
)
echo.

REM 4. yfinance Provider (Global Stock Prices & Financials)
echo [4/8] Syncing yfinance Data (US/JP Market)...
if exist "yfinance_provider" (
    pushd "yfinance_provider"
    set PYTHONPATH=.
    uv run python -m src.collector.main --sync-market all --workers 8
    popd
) else (
    echo [SKIP] yfinance_provider not found.
)
echo.

REM 5. Crypto Price Data
echo [5/8] Syncing Crypto Price Data (BTC, ETH, etc.)...
if exist "daily_crypto_price" (
    pushd "daily_crypto_price"
    uv run python main.py --sync
    popd
) else (
    echo [SKIP] daily_crypto_price not found.
)
echo.

REM 6. Forex Data (Currency Rates)
echo [6/8] Syncing Forex Data (JPY, EUR, etc.)...
if exist "forex" (
    pushd "forex"
    uv run python main.py sync
    popd
) else (
    echo [SKIP] forex not found.
)
echo.

REM 7. Macro Economic Data (FRED)
echo [7/8] Syncing Macro Economic Data (DFF, DGS10)...
if exist "macro" (
    pushd "macro"
    uv run python main.py sync
    popd
) else (
    echo [SKIP] macro not found.
)
echo.

REM 8. Market Index Data
echo [8/8] Syncing Market Index Data (^GSPC)...
if exist "index" (
    pushd "index"
    uv run python main.py sync
    popd
) else (
    echo [SKIP] index not found.
)

popd

echo ===================================================================
echo [COMPLETE] All databases synchronized.
echo All data centralized in root /data directory.
echo ===================================================================
pause
