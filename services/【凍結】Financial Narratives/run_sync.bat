@echo off
setlocal
cd /d %~dp0

echo ======================================================
echo Financial Narrative Pipeline - Sync Manager
echo ======================================================
echo Which market do you want to launch?
echo [1] Japan Market (JP)
echo [2] US Market (US)
echo [3] Both Markets (JP and US)
set /p choice="Select (1-3): "

if "%choice%"=="1" (
    call bin\run_jp_sync.bat
    exit
)
if "%choice%"=="2" (
    call bin\run_us_sync.bat
    exit
)
if "%choice%"=="3" (
    echo Launching JP market...
    start "JP-Sync" cmd /c "bin\run_jp_sync.bat"
    timeout /t 2 >nul
    echo Launching US market...
    start "US-Sync" cmd /k "bin\run_us_sync.bat"
    exit
)

echo Invalid selection.
pause
exit
