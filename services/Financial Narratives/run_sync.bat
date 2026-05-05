@echo off
setlocal
cd /d %~dp0

echo ======================================================
echo Financial Narrative Pipeline - Sync Manager
echo ======================================================
echo Which market do you want to sync? (Opening in Tabs)
echo [1] Japan Market (JP)
echo [2] US Market (US)
echo [3] Both Markets (Separate Windows)
set /p choice="Select (1-3): "

if "%choice%"=="1" call bin\run_jp_sync.bat
if "%choice%"=="2" call bin\run_us_sync.bat
if "%choice%"=="3" (
    :: 各市場を独立したウィンドウ（タブ統合済）で起動
    start cmd /c bin\run_jp_sync.bat
    start cmd /c bin\run_us_sync.bat
)
