@echo off
title Financial Figures - Full EDINET Backfill
echo [Warning] This will perform a 5-year historical backfill for EDINET statutory data.
echo [Warning] This may take a long time and consume significant AI API tokens.
echo.
set /p confirm="Do you want to proceed? (Y/N): "
if /i "%confirm%" neq "Y" exit /b

echo [Backfill] Starting Full EDINET Backfill (5 Years)...
uv run python main.py --edinet-backfill AUTO
echo [Success] Full backfill completed.
pause
