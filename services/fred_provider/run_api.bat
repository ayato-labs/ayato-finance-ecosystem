@echo off
echo Starting FRED provider API service...
.venv\Scripts\python -m src.api.server
pause
