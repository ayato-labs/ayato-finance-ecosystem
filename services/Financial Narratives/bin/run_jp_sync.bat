@echo off
setlocal
cd /d %~dp0\..

echo ======================================================
echo Launching JP Sync Pipeline in Windows Terminal Tabs
echo ======================================================

:: wt (Windows Terminal) を使用して、1つのウィンドウにタブで展開
:: main.py はルートにあるため、カレントディレクトリからのパスを正しく指定
wt -w 0 nt --title "Ingestion-JP" cmd /k "uv run python main.py --market jp --sync" ; ^
nt --title "Worker-JP-1" cmd /k "uv run python src/structuring_worker.py --market jp --workers 5" ; ^
nt --title "Worker-JP-2" cmd /k "uv run python src/structuring_worker.py --market jp --workers 5" ; ^
nt --title "Writer" cmd /k "uv run python src/writer.py"

exit
