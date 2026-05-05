import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SEC EDGAR Requirements
    SEC_USER_AGENT: str = "MyFinancialApp-Demo user@example.com"

    # AI Models
    GEMINI_API_KEY: str | None = None
    LIGHT_GOOGLE_AI_MODELS: list[str] = ["gemma-4-31b-it", "gemma-4-26b-a4b-it"]
    GEMINI_TEMPERATURE: float = 0.0

    # Target Standard Labels (Common Interface)
    TARGET_LABELS: list[str] = [
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
        "ResearchAndDevelopment",
        "CapitalExpenditure",
        "OperatingCashFlow",
        "InvestingCashFlow",
        "FinancingCashFlow",
        "CashAndDeposits",
        "InterestBearingDebt",
    ]

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

    # J-Quants (JP Market)
    JQUANTS_API_KEY: str | None = None
    JQUANTS_REFRESH_TOKEN: str | None = None

    # EDINET (JP Statutory)
    EDINET_API_KEY: str | None = None

    # Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    MARKETS_DIR: Path = DATA_DIR / "markets"

    DB_PATH_US: Path = MARKETS_DIR / "us.duckdb"
    DB_PATH_JP: Path = MARKETS_DIR / "jp.duckdb"
    DB_PATH_EDINET_RAW: Path = DATA_DIR / "audit" / "edinet_raw.duckdb"
    DB_PATH_EDINET_NORM: Path = MARKETS_DIR / "edinet_normalized.duckdb"
    DB_PATH_TRACEABILITY: Path = DATA_DIR / "audit" / "traceability.duckdb"
    DB_PATH_MASTER: Path = DATA_DIR / "master.duckdb"

    # API Endpoints
    SEC_TICKERS_URL: str = "https://www.sec.gov/files/company_tickers.json"
    SEC_COMPANY_FACTS_URL_BASE: str = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    EDINET_MASTER_URL: str = (
        "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip"
    )

    # Server configuration
    API_PORT: int = 5006

    # Performance Tuning
    AI_MAPPING_BATCH_SIZE: int = 10
    DUCKDB_MEMORY_LIMIT: str = "2GB"
    DUCKDB_THREADS: int = 4
    SYNC_QUEUE_MAXSIZE: int = 50

    @property
    def db_read_only(self) -> bool:
        return os.environ.get("DB_READ_ONLY", "false").lower() == "true"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",  # Allow unknown env vars without crashing
    }


settings = Settings()
