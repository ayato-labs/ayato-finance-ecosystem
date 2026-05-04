@echo off
title Financial Narratives API Server
echo Starting Financial Narratives API Server...
uv run uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
pause
