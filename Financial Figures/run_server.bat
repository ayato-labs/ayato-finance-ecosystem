@echo off
title Financial Figures - API Server
echo [Viewer Mode] Starting API Server on Port 5006...
echo (Read-only mode enabled for safe parallel access)
uv run python main.py --api --no-sync --read-only
pause
