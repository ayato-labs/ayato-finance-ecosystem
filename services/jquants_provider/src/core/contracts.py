from datetime import date, datetime
from decimal import Decimal
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
    NetSales: Optional[Decimal] = None
    OperatingProfit: Optional[Decimal] = None
    OrdinaryProfit: Optional[Decimal] = None
    Profit: Optional[Decimal] = None
    EarningsPerShare: Optional[Decimal] = None
    TotalAssets: Optional[Decimal] = None
    NetAssets: Optional[Decimal] = None
    EquityToAssetRatio: Optional[Decimal] = None
    BookValuePerShare: Optional[Decimal] = None
    CashFlowsFromOperatingActivities: Optional[Decimal] = None
    CashFlowsFromInvestingActivities: Optional[Decimal] = None
    CashFlowsFromFinancingActivities: Optional[Decimal] = None
    CashAndCashEquivalents: Optional[Decimal] = None
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
    Open: Optional[Decimal] = None
    High: Optional[Decimal] = None
    Low: Optional[Decimal] = None
    Close: Optional[Decimal] = None
    Volume: Optional[int] = None
    AdjustmentOpen: Optional[Decimal] = None
    AdjustmentHigh: Optional[Decimal] = None
    AdjustmentLow: Optional[Decimal] = None
    AdjustmentClose: Optional[Decimal] = None
    AdjustmentVolume: Optional[int] = None
    TurnoverValue: Optional[Decimal] = None
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
    Open: Optional[Decimal] = None
    High: Optional[Decimal] = None
    Low: Optional[Decimal] = None
    Close: Optional[Decimal] = None
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
    DividendValue: Optional[Decimal] = None
    session_id: str
    ingested_at: datetime = Field(default_factory=datetime.now)
