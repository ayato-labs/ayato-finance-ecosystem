@echo off
:: FREDデータ同期バッチファイル
cd /d %~dp0
call .venv\Scripts\activate
python main.py sync --symbols DFF UNRATE
pause
