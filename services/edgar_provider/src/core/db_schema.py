import datetime as dt
from typing import Any, ClassVar
from pydantic import BaseModel, Field

class BaseDbSchema(BaseModel):
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class FilingSchema(BaseDbSchema):
    accession_number: str = Field(..., description="SEC accession number key (Primary Key)")
    ticker: str | None = Field(None, description="Filer corporate ticker symbol")
    cik: str | None = Field(None, description="SEC Central Index Key (CIK)")
    form: str | None = Field(None, description="Filer form type (e.g. 10-K, 10-Q)")
    filing_date: dt.date | None = Field(None, description="SEC official filing date")
    sections: Any = Field(None, description="Parsed text sections of the document stored in JSON format")
    metadata: Any = Field(None, description="Accompanying metadata stored in JSON format")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record insertion timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "filings"
        primary_key: ClassVar[list[str]] = ["accession_number"]
        type_overrides: ClassVar[dict[str, str]] = {"sections": "JSON", "metadata": "JSON"}

class CompanyFactSchema(BaseDbSchema):
    fact_id: str = Field(..., description="Unique MD5 hash identifier of the fact (Primary Key)")
    accession_number: str | None = Field(None, description="Accompanying SEC document accession number")
    ticker: str | None = Field(None, description="Corporate ticker symbol")
    concept: str | None = Field(None, description="XBRL taxonomy concept identification tag")
    label: str | None = Field(None, description="Human readable label of the concept tag")
    value: float | None = Field(None, description="Numerical value of the fact")
    unit: str | None = Field(None, description="Measurement units classification (e.g. USD, Shares)")
    fiscal_year: int | None = Field(None, description="Target accounting fiscal year")
    fiscal_period: str | None = Field(None, description="Target accounting fiscal period (e.g. FY, Q1, Q2, Q3)")
    period_start: dt.date | None = Field(None, description="Filing statement reporting interval start date")
    period_end: dt.date | None = Field(None, description="Filing statement reporting interval end date")
    period_instant: dt.date | None = Field(None, description="Instant reporting point date")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record insertion timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "company_facts"
        primary_key: ClassVar[list[str]] = ["fact_id"]
