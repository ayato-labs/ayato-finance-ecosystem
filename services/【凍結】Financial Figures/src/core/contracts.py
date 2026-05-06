from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DataContract(BaseModel):
    """Base class for all data contracts with validation."""

    model_config = ConfigDict(
        strict=False,  # Allow coercion (e.g., ISO string to date)
        extra="ignore",  # Allow extra fields in raw data, but ignore them
    )


# --- Common Tickers ---


class USTickerContract(DataContract):
    ticker: str
    cik: str
    name: str
    last_session_id: str


class JPTickerContract(DataContract):
    code: str
    name: str
    market_section: str
    sector: str
    last_session_id: str


# --- US Market (Long Format) ---


class USFactContract(DataContract):
    cik: str
    taxonomy: str
    tag: str
    label: str
    unit: str
    value: float
    end_date: date
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    form: str | None = None
    filed_date: date | None = None
    accession_number: str
    session_id: str


# --- JP Market (Wide Format - J-Quants Native) ---


class JPFactContract(DataContract):
    DisclosedDate: date
    DisclosedTime: str
    LocalCode: str
    DisclosureNumber: str
    Type: str
    FiscalYear: str
    FiscalPeriod: str
    # Financial fields as DOUBLE/float
    NetSales: float | None = None
    OperatingProfit: float | None = None
    OrdinaryProfit: float | None = None
    Profit: float | None = None
    EarningsPerShare: float | None = None
    TotalAssets: float | None = None
    NetAssets: float | None = None
    Equity: float | None = None
    EquityToAssetRatio: float | None = None
    BookValuePerShare: float | None = None
    CashFlowsFromOperatingActivities: float | None = None
    CashFlowsFromInvestingActivities: float | None = None
    CashFlowsFromFinancingActivities: float | None = None
    CashAndCashEquivalents: float | None = None
    session_id: str


# --- Traceability ---


class SyncSessionContract(DataContract):
    session_id: str
    market: str
    status: str
    started_at: datetime
    git_commit_hash: str


class MappingAuditContract(DataContract):
    mapping_id: str
    session_id: str
    source_tag: str
    mapped_label: str
    reasoning: str
    confidence_score: float
    mapped_at: datetime
    llm_model_version: str
