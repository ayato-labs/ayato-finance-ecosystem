@echo off
echo Running resilient historical fetch (30-day batches, 5 years total)...
uv run python historical_loader.py

echo.
echo Running self-healing backfill for missing narratives...
uv run python backfill.py

echo.
echo Running TTL cleanup for raw data cache (30-day retention)...
uv run python scripts/cleanup_raw_data.py

pause
