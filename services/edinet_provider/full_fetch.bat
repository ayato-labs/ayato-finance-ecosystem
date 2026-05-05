@echo off
echo Running full historical fetch (last 5 years, market-wide)...
uv run python -c "from src.engine import JPEDINETEngine; engine = JPEDINETEngine(); engine.sync_market(days=1825)"

echo.
echo Running self-healing backfill for missing narratives...
uv run python backfill.py

pause
