@echo off
title Financial Narratives Data Sync
echo ==================================================
echo Financial Narratives - State-Based Orchestration
echo ==================================================
echo.

echo [1/3] Starting Automated Data Sync (Ingestion to Data Lake)...
uv run python main.py --sync
echo.

echo [2/3] Running Reconciler (Calculating Delta and Enqueuing Jobs)...
uv run python main.py --reconcile
echo.

echo [3/3] Starting Parallel Structuring Worker Pool...
echo (This will run continuously to process queued jobs. Press Ctrl+C to stop)
uv run python main.py --work --workers 10

pause
