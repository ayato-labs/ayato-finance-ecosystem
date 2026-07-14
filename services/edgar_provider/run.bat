@echo off
setlocal

@REM All company get command in 2 years.
@REM run.bat sync --days 730
@REM Get one company command in 2 years.
@REM run.bat get --ticker AAPL --days 730

:: Run main.py using the local virtualenv python and pass all batch arguments
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" main.py %*
