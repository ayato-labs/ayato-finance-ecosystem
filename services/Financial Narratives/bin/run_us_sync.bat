@echo off
setlocal
cd /d %~dp0\..

echo ======================================================
echo Launching US Sync Pipeline in Windows Terminal Tabs
echo ======================================================

wt -w 0 nt --title "Ingestion-US" cmd /k "uv run python main.py --market us --sync" ; ^
nt --title "Worker-US-1" cmd /k "uv run python src/structuring_worker.py --market us --workers 5" ; ^
nt --title "Worker-US-2" cmd /k "uv run python src/structuring_worker.py --market us --workers 5" ; ^
nt --title "Writer" cmd /k "uv run python src/writer.py"

exit
