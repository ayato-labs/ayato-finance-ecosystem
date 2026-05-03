@echo off
setlocal
title Ayato Finance Ecosystem - Market Sync Master

echo [Step 1/1] Starting Market Sync for all services in Windows Terminal...

wt --title "Sync: Stock Price" -d "services\daily_stock_price" cmd /k "uv run python main.py --sync-market all" ^; ^
new-tab --title "Sync: Financial Figures" -d "services\Financial Figures" cmd /k "uv run python main.py --sync-market all" ^; ^
new-tab --title "Sync: Narratives" -d "services\Financial Narratives" cmd /k "uv run python main.py --sync" ^; ^
new-tab --title "Sync: Index" -d "services\index" cmd /k ".\.venv\Scripts\python main.py sync" ^; ^
new-tab --title "Sync: Macro" -d "services\macro" cmd /k ".\.venv\Scripts\python main.py sync" ^; ^
new-tab --title "Sync: Forex" -d "services\forex" cmd /k "uv run python main.py sync"

echo.
echo All sync processes requested.
echo Please check individual tabs for progress.
pause
