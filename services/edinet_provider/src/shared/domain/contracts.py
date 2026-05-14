from enum import StrEnum

from pydantic import BaseModel


class IngestionStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    PARTIAL_FAIL = "PARTIAL_FAIL"
    FAILED = "FAILED"


class FiscalPeriod(StrEnum):
    FY = "FY"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"


class DataContract(BaseModel):
    doc_id: str
    session_id: str


class FilingMetadata(DataContract):
    edinet_code: str | None
    sec_code: str | None
    filer_name: str | None
    doc_description: str | None
    submit_datetime: str | None
    form_code: str | None
    doc_type_code: str | None


class CompanyFact(DataContract):
    item_name: str
    item_value: float
    unit: str
    context_id: str
    fiscal_year: int
    fiscal_period: FiscalPeriod = FiscalPeriod.FY


class NarrativeBlock(DataContract):
    section_name: str
    content_md: str
