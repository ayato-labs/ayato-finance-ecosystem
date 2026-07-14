@echo off
setlocal enabledelayedexpansion

echo ====================================================
echo  Scrap and Rebuild Virtual Environment (uv)
echo ====================================================

cd /d "%~dp0"

:: 1. Scrap existing .venv
if exist ".venv" (
    echo [1/3] Removing old .venv directory...
    rmdir /s /q ".venv"
    if exist ".venv" (
        echo [ERROR] Failed to remove .venv. Make sure no process is using it.
        exit /b 1
    )
) else (
    echo [1/3] No existing .venv found. Skipping removal.
)

:: 2. Create new virtual environment
echo [2/3] Creating fresh virtual environment...
uv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment with uv.
    exit /b 1
)

:: 3. Build & Install editable package
echo [3/3] Installing package in editable mode with dependencies...
uv pip install -e .
if errorlevel 1 (
    echo [ERROR] Failed to install package in editable mode.
    exit /b 1
)

echo ====================================================
echo  Rebuild Completed Successfully!
echo ====================================================
pause
