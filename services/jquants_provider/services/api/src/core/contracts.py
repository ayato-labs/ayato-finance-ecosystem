from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class JPTickerContract(BaseModel):
    code: str
    name: str
    market_section_id: Optional[int] = None
    sector_id: Optional[int] = None
    last_session_id: Optional[str] = None


class JPFactContract(BaseModel):
    DisclosedDate: date
    DisclosedTime: str
    LocalCode: str
    DisclosureNumber: str
    Type: str
    FiscalYear: str
    FiscalPeriod: str
    NetSales: Optional[float] = None
    OperatingProfit: Optional[float] = None
    OrdinaryProfit: Optional[float] = None
    Profit: Optional[float] = None
    EarningsPerShare: Optional[float] = None
    TotalAssets: Optional[float] = None
    NetAssets: Optional[float] = None
    EquityToAssetRatio: Optional[float] = None
    BookValuePerShare: Optional[float] = None
    CashFlowsFromOperatingActivities: Optional[float] = None
    CashFlowsFromInvestingActivities: Optional[float] = None
    CashFlowsFromFinancingActivities: Optional[float] = None
    CashAndCashEquivalents: Optional[float] = None
    session_id: str
    ingested_at: datetime = Field(default_factory=datetime.now)

    @field_validator(
        "NetSales",
        "OperatingProfit",
        "OrdinaryProfit",
        "Profit",
        "EarningsPerShare",
        "TotalAssets",
        "NetAssets",
        "EquityToAssetRatio",
        "BookValuePerShare",
        "CashFlowsFromOperatingActivities",
        "CashFlowsFromInvestingActivities",
        "CashFlowsFromFinancingActivities",
        "CashAndCashEquivalents",
        mode="before",
    )
    @classmethod
    def clean_decimal(cls, v):
        if v is None or v == "" or (isinstance(v, float) and (v != v or abs(v) == float("inf"))):
            return None
        return v

    @field_validator("FiscalYear", "FiscalPeriod", "DisclosedTime", mode="before")
    @classmethod
    def clean_string(cls, v):
        if v is None or (isinstance(v, float) and v != v):
            return ""
        return str(v)

    class Config:
        arbitrary_types_allowed = True


class JPPriceContract(BaseModel):
    Date: date
    Code: str
    Open: Optional[float] = None
    High: Optional[float] = None
    Low: Optional[float] = None
    Close: Optional[float] = None
    Volume: Optional[int] = None
    AdjustmentOpen: Optional[float] = None
    AdjustmentHigh: Optional[float] = None
    AdjustmentLow: Optional[float] = None
    AdjustmentClose: Optional[float] = None
    AdjustmentVolume: Optional[int] = None
    TurnoverValue: Optional[float] = None
    session_id: str
    ingested_at: datetime = Field(default_factory=datetime.now)

    @field_validator(
        "Open",
        "High",
        "Low",
        "Close",
        "AdjustmentOpen",
        "AdjustmentHigh",
        "AdjustmentLow",
        "AdjustmentClose",
        "TurnoverValue",
        mode="before",
    )
    @classmethod
    def clean_decimal(cls, v):
        if v is None or v == "" or (isinstance(v, float) and (v != v or abs(v) == float("inf"))):
            return None
        return v

    @field_validator("Volume", "AdjustmentVolume", mode="before")
    @classmethod
    def cast_to_int(cls, v):
        if v is None or v == "" or (isinstance(v, float) and (v != v or abs(v) == float("inf"))):
            return None
        return int(float(v))


class JPIndexContract(BaseModel):
    Date: date
    Code: str
    Open: Optional[float] = None
    High: Optional[float] = None
    Low: Optional[float] = None
    Close: Optional[float] = None
    session_id: str
    ingested_at: datetime = Field(default_factory=datetime.now)

    @field_validator("Open", "High", "Low", "Close", mode="before")
    @classmethod
    def clean_decimal(cls, v):
        if v is None or v == "" or (isinstance(v, float) and (v != v or abs(v) == float("inf"))):
            return None
        return v


class JPDividendContract(BaseModel):
    AnnouncementDate: date
    Code: str
    RecordDate: date
    DividendValue: Optional[float] = None
    session_id: str
    ingested_at: datetime = Field(default_factory=datetime.now)
