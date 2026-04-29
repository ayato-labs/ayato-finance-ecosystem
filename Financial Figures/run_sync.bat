@echo off
title Financial Figures - Unified Market Sync
echo [Sync Mode] Starting Incremental Sync for US, JP, and EDINET...
uv run python main.py --sync-market all --incremental
echo [Success] Sync process completed.
pause
