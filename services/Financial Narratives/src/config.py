import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
# 優先順位順に使用するモデルのリスト。最初のモデルが失敗した場合、次を試行する。
GOOGLE_AI_MODELS = ["gemma-4-31b-it", "gemma-4-26b-a4b-it"]
# API Configuration
# API Configuration
USER_AGENT = os.environ.get(
    "USER_AGENT", "ayato-labs-finance-sync/1.0 (contact: ayato-labs@example.com)"
)
DEFAULT_PORT = 5013

# Storage Configuration
DEFAULT_DB_PATH = "data/financial_narratives.duckdb"
DUCKDB_MEMORY_LIMIT = "2GB"

# Market Configuration
SEC_TICKERS = ["AAPL", "NVDA", "GOOGL", "AMZN", "META", "MSFT", "TSLA"]
