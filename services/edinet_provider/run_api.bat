@echo off
REM API Server Launcher
echo Starting EDINET Provider API Server...
call .venv\Scripts\activate
python -m uvicorn main:app --reload
pause
