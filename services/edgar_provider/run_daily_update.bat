@echo off
chcp 65001 > nul
echo ===================================================
echo   EDGAR Provider - Daily Differential Update
echo ===================================================
echo ※現在、差分更新は各ティッカーを順次処理する --all オプションを使用します。
echo （注意：既存の実装では処理済みティッカーをスキップするロジックが含まれています）
echo 実行しています...
uv run python main.py --all
pause
