@echo off
title Financial Figures - Master Launcher
:menu
cls
echo ==========================================
echo    Financial Figures Unified System
echo ==========================================
echo 1) Start API Server (Viewer / Read-Only)
echo 2) Start Full Sync (US + JP + EDINET)
echo 3) Start EDINET Sync (Statutory Data Only)
echo 4) Exit
echo ------------------------------------------
set /p choice="Select an option (1-4): "

if "%choice%"=="1" start cmd /k "run_server.bat" & goto menu
if "%choice%"=="2" start cmd /k "run_sync.bat" & goto menu
if "%choice%"=="3" start cmd /k "uv run python main.py --edinet-only" & goto menu
if "%choice%"=="4" exit

echo Invalid choice.
pause
goto menu
