@echo off
echo Running daily incremental market-wide sync (last 7 days)...
uv run python -c "from src.engine import JPEDINETEngine; engine = JPEDINETEngine(); engine.sync_market(days=7)"
pause
