import datetime as dt
from typing import ClassVar
from pydantic import BaseModel, Field

class BaseDbSchema(BaseModel):
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class DocumentManifestSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Unique document ID index (Primary Key)")
    status: str | None = Field(None, description="Current ingestion processing status")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "document_manifest"
        primary_key: ClassVar[list[str]] = ["doc_id"]

class FilingSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Unique document ID (Primary Key)")
    edinet_code: str | None = Field(None, description="Submitter EDINET identification code")
    sec_code: str | None = Field(None, description="Submitter security ticker code")
    filer_name: str | None = Field(None, description="Corporate company name of the filer")
    doc_description: str | None = Field(None, description="Document type description text")
    submit_datetime: dt.datetime | None = Field(None, description="EDINET official submission timestamp")
    form_code: str | None = Field(None, description="Type form category code")
    doc_type_code: str | None = Field(None, description="Specific document type category classification number")
    session_id: str | None = Field(None, description="Sync execution logging session ID")
    ingested_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record insertion timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "filings"
        primary_key: ClassVar[list[str]] = ["doc_id"]

class CompanyFactSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Associated document ID key")
    item_name: str = Field(..., description="XBRL taxonomy item account name")
    item_value: float | None = Field(None, description="Numerical value of the fact")
    unit: str | None = Field(None, description="Units classification (e.g. JPY, Shares)")
    context_id: str = Field(..., description="Filing statement context description ID")
    fiscal_year: int | None = Field(None, description="Target accounting fiscal year")
    fiscal_period: str | None = Field(None, description="Target fiscal period (e.g. FY, Q1, Q2, Q3)")
    session_id: str | None = Field(None, description="Sync execution logging session ID")
    ingested_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record insertion timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "company_facts"
        primary_key: ClassVar[list[str]] = ["doc_id", "item_name", "context_id"]

class NarrativeSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Associated document ID key")
    section_name: str = Field(..., description="Qualitative paragraph section category name")
    content_md: str | None = Field(None, description="Parsed text body content formatted in Markdown")
    session_id: str | None = Field(None, description="Sync execution logging session ID")
    ingested_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record insertion timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "narratives"
        primary_key: ClassVar[list[str]] = ["doc_id", "section_name"]

class FinancialStatementSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Unique document ID (Primary Key)")
    edinet_code: str | None = Field(None, description="Submitter EDINET identification code")
    sec_code: str | None = Field(None, description="Submitter security ticker code")
    fiscal_year: int | None = Field(None, description="Target accounting fiscal year")
    fiscal_period: str | None = Field(None, description="Target fiscal period (e.g. FY, Q1, Q2, Q3)")
    submit_datetime: dt.datetime | None = Field(None, description="EDINET official submission timestamp")
    current_assets: int | None = Field(None, description="Balance Sheet: Current assets")
    cash_and_deposits: int | None = Field(None, description="Balance Sheet: Cash and cash equivalents")
    total_assets: int | None = Field(None, description="Balance Sheet: Total assets")
    current_liabilities: int | None = Field(None, description="Balance Sheet: Current liabilities")
    total_liabilities: int | None = Field(None, description="Balance Sheet: Total liabilities")
    net_assets: int | None = Field(None, description="Balance Sheet: Total net assets")
    net_sales: int | None = Field(None, description="Income Statement: Net sales / revenue")
    operating_income: int | None = Field(None, description="Income Statement: Operating income")
    net_income: int | None = Field(None, description="Income Statement: Net income")
    is_equation_valid: bool | None = Field(None, description="Status validity validation of balance identity equation")
    is_consolidated: bool | None = Field(None, description="Boolean flag if financials are consolidated statements")
    interest_expense: int | None = Field(None, description="Income Statement: Interest expense value")
    operating_cash_flow: int | None = Field(None, description="Cash Flow Statement: Net cash from operating activities")
    industry_code: str | None = Field(None, description="Industrial classification mapping code")

    class SQLConfig:
        table_name: ClassVar[str] = "financial_statements"
        primary_key: ClassVar[list[str]] = ["doc_id"]

class IngestionLogSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Unique document ID key (Primary Key)")
    status: str | None = Field(None, description="Ingestion processing outcome status")
    last_attempt: dt.datetime | None = Field(None, description="Timestamp of the last processing attempt")
    retry_count: int = Field(0, description="Counter of historical retry attempts", json_schema_extra={"sql_default": "0"})
    error_message: str | None = Field(None, description="Detailed trace logs if attempt failed")

    class SQLConfig:
        table_name: ClassVar[str] = "ingestion_log"
        primary_key: ClassVar[list[str]] = ["doc_id"]

class IngestionProgressSchema(BaseDbSchema):
    target_date: dt.date = Field(..., description="Date calendar point of EDINET listings check (Primary Key)")
    status: str | None = Field(None, description="Processing status of the calendar date sync")
    doc_count: int | None = Field(None, description="Total documents processed on this date")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"}
    )

    class SQLConfig:
        table_name: ClassVar[str] = "ingestion_progress"
        primary_key: ClassVar[list[str]] = ["target_date"]
