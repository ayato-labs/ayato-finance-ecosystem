import os

# LLM Configuration
# 優先順位順に使用するモデルのリスト。最初のモデルが失敗した場合、次を試行する。
GOOGLE_AI_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

# API Configuration
USER_AGENT = os.environ.get("USER_AGENT", "FinancialNarrativesAgent/1.0 (contact: ayato-labs)")
DEFAULT_PORT = 5013

# Storage Configuration
DEFAULT_DB_PATH = "finance_narratives.duckdb"
DUCKDB_MEMORY_LIMIT = "2GB"

# Market Configuration
SEC_TICKERS = ["AAPL", "NVDA", "GOOGL", "AMZN", "META", "MSFT", "TSLA"]
