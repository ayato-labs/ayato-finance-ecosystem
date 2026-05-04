from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TransactionType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    TAX = "TAX"
    FEE = "FEE"


class AssetType(StrEnum):
    STOCK = "STOCK"
    CRYPTO = "CRYPTO"
    CASH = "CASH"


class Transaction(BaseModel):
    id: int | None = None
    ticker: str
    transaction_type: TransactionType = Field(alias="type", serialization_alias="type")
    asset_type: AssetType = AssetType.STOCK
    quantity: float
    price: float
    fee: float = 0.0
    currency: str = "USD"
    timestamp: datetime = Field(default_factory=datetime.now)
    memo: str | None = None

    model_config = {"populate_by_name": True, "from_attributes": True}


class AssetSummary(BaseModel):
    id: str | None = None
    ticker: str
    asset_type: AssetType
    total_quantity: float
    average_price: float
    current_price: float | None = None
    market_value: float | None = None
    unrealized_gain: float | None = None
    gain_percent: float | None = None
    currency: str = "USD"
    weight: float | None = None
    financial_health_score: float | None = None
    benchmark_gain_percent: float | None = None
    benchmark_unrealized_gain: float | None = None
    crypto_metadata: dict | None = None


class BenchmarkSummary(BaseModel):
    name: str
    ticker: str
    gain_percent: float


class PortfolioSummary(BaseModel):
    total_market_value: float | None = None
    total_unrealized_gain: float | None = None
    gain_percent: float | None = None
    display_currency: str = "JPY"
    display_symbol: str = "¥"
    volatility: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    benchmark_volatility: float | None = None
    benchmark_sharpe: float | None = None
    benchmark_max_drawdown: float | None = None
    sortino_ratio: float | None = None
    beta: float | None = None
    correlation: float | None = None
    assets: list[AssetSummary]
    benchmarks: list[BenchmarkSummary] = []
    macro_indicators: dict[str, float] = {}
    shadow_market_value: float | None = None
    shadow_gain_percent: float | None = None
    shadow_unrealized_gain: float | None = None
    alpha_value: float | None = None
    alpha_percent: float | None = None
