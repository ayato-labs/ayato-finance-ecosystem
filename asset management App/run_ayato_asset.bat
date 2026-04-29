@echo off
title Ayato Asset Management - Launcher
echo ==========================================
echo   Ayato Asset Management (Relative-First)
echo ==========================================
echo.
echo [INFO] Ensure Ports 5005 and 5006 are running.
echo.

:: Start Backend
echo Starting Backend (Port 5007)...
start "Ayato-Backend" cmd /k "uv run python main.py"

:: Start Crypto Price Service
echo Starting Crypto Price Service (Port 5012)...
start "Ayato-Crypto" cmd /k "cd ..\daily_crypto_price && uv run python main.py"

:: Start Frontend
echo Starting Frontend (Port 3000)...
start "Ayato-Frontend" cmd /k "cd src\frontend && npm run dev"

echo.
echo ------------------------------------------
echo Processes started.
echo Dashboard: http://localhost:3000
echo ------------------------------------------
echo.
pause
