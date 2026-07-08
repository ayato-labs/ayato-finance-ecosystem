import datetime as dt
from typing import Any, ClassVar
from pydantic import BaseModel, Field

class BaseDbSchema(BaseModel):
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class SyncStatusSchema(BaseDbSchema):
    ticker: str = Field(..., description="Ticker symbol of the financial asset (Primary Key)")
    last_sync_at: dt.datetime = Field(..., description="Timestamp when the sync was performed")
    last_status: str = Field(..., description="Sync outcome status (e.g. SUCCESS, FAILED, PARTIAL)")
    error_message: str | None = Field(None, description="Detailed error message if sync failed")
    quality_score: float = Field(1.0, description="Calculated data quality score (0.0 to 1.0)")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "sync_status"
        primary_key: ClassVar[list[str]] = ["ticker"]

class InfoSchema(BaseDbSchema):
    ticker: str = Field(..., description="Ticker symbol of the asset (Primary Key)")
    data: Any = Field(..., description="Raw stock profile info stored in JSON format")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "info"
        primary_key: ClassVar[list[str]] = ["ticker"]
        type_overrides: ClassVar[dict[str, str]] = {"data": "JSON"}

class FinancialRecordSchema(BaseDbSchema):
    ticker: str = Field(..., description="Ticker symbol of the asset")
    date: dt.date = Field(..., description="Filing statement reporting date")
    item: str = Field(..., description="Financial line item key/name")
    value: float | None = Field(None, description="Numerical value of the financial item")
    period_type: str = Field(..., description="Reporting period type (e.g. Annual, Quarterly)")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_names: ClassVar[list[str]] = ["financials", "balance_sheet", "cashflow"]
        unique_constraints: ClassVar[list[list[str]]] = [["ticker", "date", "item", "period_type"]]

class StockPriceSchema(BaseDbSchema):
    ticker: str = Field(..., description="Ticker symbol of the asset")
    date: dt.datetime = Field(..., description="Datetime interval timestamp")
    open: float = Field(..., description="Opening price of the interval")
    high: float = Field(..., description="Highest price during the interval")
    low: float = Field(..., description="Lowest price during the interval")
    close: float = Field(..., description="Closing price of the interval")
    volume: int = Field(..., description="Total volume traded during the interval")
    dividends: float = Field(0.0, description="Dividends paid on this date")
    stock_splits: float = Field(0.0, description="Stock split ratio adjustment on this date")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "prices"
        unique_constraints: ClassVar[list[list[str]]] = [["ticker", "date"]]

class ForexRateSchema(BaseDbSchema):
    symbol: str = Field(..., description="Forex cross currency symbol (e.g. USDJPY=X)")
    date: dt.date = Field(..., description="Date of the historical rate")
    rate: float = Field(..., description="Exchanged conversion close rate")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "forex_rates"
        unique_constraints: ClassVar[list[list[str]]] = [["symbol", "date"]]

class CryptoMetadataSchema(BaseDbSchema):
    ticker: str = Field(..., description="Crypto coin ticker symbol (Primary Key)")
    circulating_supply: float | None = Field(None, description="Circulating coin supply")
    total_supply: float | None = Field(None, description="Total coin supply")
    max_supply: float | None = Field(None, description="Maximum possible coin supply limit")
    market_cap: float | None = Field(None, description="Total market capitalization in USD")
    description: str | None = Field(None, description="Brief description text of the asset")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "crypto_metadata"
        primary_key: ClassVar[list[str]] = ["ticker"]
