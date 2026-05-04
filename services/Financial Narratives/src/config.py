import os

# LLM Configuration
# デフォルトで Gemini 2.0 Flash を使用。環境変数で上書き可能。
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "gemini-2.0-flash")

# API Configuration
USER_AGENT = os.environ.get("USER_AGENT", "FinancialNarrativesAgent/1.0 (contact: ayato-labs)")
DEFAULT_PORT = 5013

# Storage Configuration
DEFAULT_DB_PATH = "finance_narratives.duckdb"
DUCKDB_MEMORY_LIMIT = "2GB"

# Market Configuration
SEC_TICKERS = ["AAPL", "NVDA", "GOOGL", "AMZN", "META", "MSFT", "TSLA"]
