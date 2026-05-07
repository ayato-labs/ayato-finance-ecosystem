@echo off
echo Running initial full ingestion: Pulling all available FRED series...
:: Using venv python
.venv\Scripts\python main.py sync --all-categories
pause
