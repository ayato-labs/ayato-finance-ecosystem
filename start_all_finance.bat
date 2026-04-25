@echo off
setlocal
title Ayato Finance Ecosystem - Master Launcher

echo [Step 1/2] Cleaning up existing processes on ports 5005-5010...
powershell -Command "foreach($p in @(5005,5006,5007,5008,5009,5010)) { $ids = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess; if($ids) { $ids | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } } }"

echo [Step 2/2] Starting Finance Ecosystem in Windows Terminal...

wt --title "Stock Price API" -d "daily_stock_price" cmd /k "uv run python main.py --api --port 5005 --host 127.0.0.1" ^; new-tab --title "Financial Figures" -d "Financial Figures" cmd /k "uv run python main.py --api --no-sync --read-only" ^; new-tab --title "Asset Backend" -d "asset management App\src\backend" cmd /k "uv run python main.py" ^; new-tab --title "Asset Frontend" -d "asset management App\src\frontend" cmd /k "npm run dev" ^; new-tab --title "Market Index API" -d "index" cmd /k ".\.venv\Scripts\python main.py server" ^; new-tab --title "Macro Economic API" -d "macro" cmd /k ".\.venv\Scripts\python main.py server"

echo.
echo All processes requested.
echo - Stock Price API:     http://localhost:5005
echo - Financial Figures:   http://localhost:5006
echo - Asset Backend:       http://localhost:5007
echo - Asset Frontend:      http://localhost:5008
echo - Market Index API:    http://localhost:5009
echo - Macro Economic API:  http://localhost:5010
echo.
pause
