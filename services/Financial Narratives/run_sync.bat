@echo off
title Financial Narratives Data Sync
echo Starting Automated Data Sync (US/JP Market)...
uv run python src/batch_fetch.py
echo.
echo Sync process completed.
pause
