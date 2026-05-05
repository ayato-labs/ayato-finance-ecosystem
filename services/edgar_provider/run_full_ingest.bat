@echo off
chcp 65001 > nul
echo ===================================================
echo   EDGAR Provider - Full Data Ingestion (Bulk)
echo ===================================================
echo バルクZIPファイルを使用して、全企業データを高速に取り込みます。
echo 実行しています...
uv run python main.py --bulk
pause
