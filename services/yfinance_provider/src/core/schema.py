from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DataContract(BaseModel):
    """データ品質を保証するための基本クラス"""

    model_config = {"populate_by_name": True}

    @field_validator("*", mode="before")
    @classmethod
    def prevent_empty_strings(cls, v):
        if v == "":
            return None
        return v


class TickerInfo(DataContract):
    ticker: str = Field(alias="symbol")
    company_name: str = Field(alias="longName")
    currency: str = Field(default="USD")
    sector: str | None = None
    industry: str | None = None
    business_summary: str | None = Field(None, alias="longBusinessSummary")
    current_price: float = Field(0.0, alias="currentPrice")
    market_cap: int | None = Field(None, alias="marketCap")
    raw_json: str


class FinancialRecord(DataContract):
    ticker: str
    date: str
    item: str
    value: float
    period_type: str  # Annual / Quarterly


class StockPrice(DataContract):
    ticker: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    dividends: float = 0.0
    stock_splits: float = 0.0


class SyncStatus(DataContract):
    """マスターDB的な管理用スキーマ"""

    ticker: str
    last_sync_at: datetime
    last_status: str  # SUCCESS / FAILED / PARTIAL
    error_message: str | None = None
    data_quality_score: float = 1.0  # 0.0 to 1.0
