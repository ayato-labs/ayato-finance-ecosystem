@echo off
title Financial Narratives Orchestrator
echo ==================================================
echo Financial Narratives - State-Based Orchestration
echo ==================================================
echo.

set PYTHONPATH=%cd%

echo [1/4] Reconciling Data Lake and Job Queue...
uv run python src/reconciler.py

echo [2/4] Starting Parallel LLM Structuring Workers...
start "Financial Narratives - LLM Workers" cmd /c "set PYTHONPATH=%cd% && uv run python src/structuring_worker.py --workers 75"

echo [3/4] Starting Single Writer (DuckDB Serializer)...
start "Financial Narratives - Writer" cmd /c "set PYTHONPATH=%cd% && uv run python src/writer.py"

echo [4/4] Starting Ingestion (Data Lake Construction)...
:: Ingestion is usually the fastest part, but we run it in the main window
uv run python src/batch_fetch.py

echo.
echo ======================================================
echo Ingestion completed. Now waiting for Workers to finish...
echo ======================================================
echo.

:: 新設したモニタリングスクリプトで、全ジョブ完了まで待機
uv run python scripts/monitor_stats.py

echo.
echo ======================================================
echo All Pipeline Processes Completed Successfully.
echo ======================================================
pause
