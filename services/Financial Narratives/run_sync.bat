@echo off
title Financial Narratives Orchestrator
echo ==================================================
echo Financial Narratives - State-Based Orchestration
echo ==================================================
echo.

set PYTHONPATH=%cd%

echo [1/3] Reconciling Data Lake and Job Queue...
uv run python src/reconciler.py

echo [2/3] Starting Parallel LLM Structuring Workers in background...
start "Financial Narratives - LLM Workers" cmd /c "set PYTHONPATH=%cd% && uv run python src/structuring_worker.py --workers 30"

echo [3/3] Starting Ingestion (Data Lake Construction)...
uv run python src/batch_fetch.py

echo.
echo ======================================================
echo Ingestion process completed. 
echo LLM Workers are still running in the separate window.
echo You can close it once it shows 'No more jobs' for a while.
echo ======================================================
pause
