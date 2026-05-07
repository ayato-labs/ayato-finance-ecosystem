@echo off
:: ローカルAPI起動バッチファイル
cd /d %~dp0
call .venv\Scripts\activate
python src/api/server.py
pause
