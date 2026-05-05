import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # J-Quants (JP Market)
    JQUANTS_API_KEY: str | None = None
    JQUANTS_REFRESH_TOKEN: str | None = None
    JQUANTS_RATE_LIMIT: int = 5  # Requests per minute

    # J-Quants V2 Field Names (Japanese Market Schema)
    JQUANTS_V2_LABELS: list[str] = [
        "NetSales",
        "OperatingProfit",
        "OrdinaryProfit",
        "Profit",
        "EarningsPerShare",
        "TotalAssets",
        "NetAssets",
        "Equity",
        "EquityToAssetRatio",
        "BookValuePerShare",
        "CashFlowsFromOperatingActivities",
        "CashFlowsFromInvestingActivities",
        "CashFlowsFromFinancingActivities",
        "CashAndCashEquivalents",
    ]

    # Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"

    # Domain Shards
    MASTER_DB_PATH: Path = DATA_DIR / "master.duckdb"  # Central catalog
    JP_MASTER_DB_PATH: Path = DATA_DIR / "jquants_master.duckdb"  # Tickers/Sectors
    JP_PRICES_DB_PATH: Path = DATA_DIR / "jquants_prices.duckdb"  # Stock Prices
    JP_FACTS_DB_PATH: Path = DATA_DIR / "jquants_financials.duckdb"  # Financials

    # Server configuration
    API_PORT: int = 5007

    # Performance Tuning
    DUCKDB_MEMORY_LIMIT: str = "2GB"
    DUCKDB_THREADS: int = 4

    @property
    def db_read_only(self) -> bool:
        return os.environ.get("DB_READ_ONLY", "false").lower() == "true"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
