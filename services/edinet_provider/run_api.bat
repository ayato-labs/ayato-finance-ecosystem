@echo off
echo Starting EDINET API Server...
uv run uvicorn main:app --reload --port 5009
pause
