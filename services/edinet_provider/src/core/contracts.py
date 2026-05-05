from datetime import date
from pydantic import BaseModel, ConfigDict

class DataContract(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore")

class JPFilingMetadata(DataContract):
    doc_id: str
    edinet_code: str
    sec_code: str | None = None
    filer_name: str
    doc_description: str
    submit_datetime: str
    form_code: str
    doc_type_code: str
    session_id: str

class JPFactContract(DataContract):
    doc_id: str
    ticker: str
    item_name: str
    item_value: float | None = None
    unit: str | None = None
    context_id: str
    filed_date: date
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    session_id: str

class JPNarrativeContract(DataContract):
    doc_id: str
    ticker: str
    section_name: str # e.g., '事業等のリスク', '経営方針'
    content_md_zstd: bytes
    filed_date: date
    session_id: str
