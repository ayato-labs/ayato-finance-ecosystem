@echo off
REM Data Synchronization Launcher
echo Starting Data Synchronization Pipeline...
call .venv\Scripts\activate
python backfill.py
echo Sync Complete.
pause
