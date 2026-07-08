import datetime as dt
from typing import ClassVar
from pydantic import BaseModel, Field

class BaseDbSchema(BaseModel):
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class CompanyFactSchema(BaseDbSchema):
    fact_id: str = Field(..., description="Unique MD5 hash key of the financial fact record (Primary Key)")
    code: str | None = Field(None, description="Ticker symbol code of the listed company")
    disclosed_date: dt.date | None = Field(None, description="Filing disclosure publication date")
    fiscal_year: int | None = Field(None, description="Target accounting fiscal year")
    fiscal_period: str | None = Field(None, description="Target fiscal period designation (e.g. FY, Q1, Q2, Q3)")
    taxonomy: str | None = Field(None, description="XBRL taxonomy namespace identification (e.g. JPX, EDINET)")
    tag: str | None = Field(None, description="Line item account mapping taxonomy tag")
    label: str | None = Field(None, description="Human readable label of the account tag")
    value: float | None = Field(None, description="Numerical value of the fact item")
    unit: str | None = Field(None, description="Units classification (e.g. JPY, Shares)")
    accession_number: str | None = Field(None, description="SEC/EDINET accession index code")
    session_id: str | None = Field(None, description="Sync execution logging session ID")
    ingested_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record insertion timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "company_facts"
        primary_key: ClassVar[list[str]] = ["fact_id"]

class TickerSchema(BaseDbSchema):
    code: str = Field(..., description="Unique ticker symbol code (Primary Key)")
    name: str | None = Field(None, description="Listed corporate company name")
    market_section: str | None = Field(None, description="Designated market exchange division division section")
    sector: str | None = Field(None, description="Industrial classification group sector name")
    last_session_id: str | None = Field(None, description="Last execution run logging session ID")

    class SQLConfig:
        table_name: ClassVar[str] = "tickers"
        primary_key: ClassVar[list[str]] = ["code"]
