from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, field_validator


class DataContract(BaseModel):
    """Base class for all data contracts in the EDINET Provider."""
    model_config = ConfigDict(strict=True, extra="ignore")


class FilingMetadata(DataContract):
    """Metadata for every filed document (Registry Layer)."""
    doc_id: str
    edinet_code: str
    sec_code: str | None = None
    filer_name: str
    doc_description: str
    submit_datetime: datetime
    form_code: str
    doc_type_code: str
    session_id: str

    @field_validator("sec_code", mode="before")
    @classmethod
    def normalize_sec_code(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        # Normalize 5-digit codes ending in 0 (common in EDINET) to 4 digits
        if len(s) == 5 and s.endswith("0"):
            return s[:4]
        return s

    @field_validator("submit_datetime", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime:
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                # EDINET API returns 'YYYY-MM-DD HH:MM' or similar
                return datetime.fromisoformat(v.replace(" ", "T"))
            except ValueError:
                return datetime.strptime(v, "%Y-%m-%d %H:%M")
        raise ValueError(f"Invalid datetime format: {v}")


class CompanyFact(DataContract):
    """Numerical financial data (Facts Layer)."""
    doc_id: str
    item_name: str
    item_value: float | None = None
    unit: str | None = None
    context_id: str
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    session_id: str  # Traceability


class NarrativeBlock(DataContract):
    """Extracted text blocks (Narratives Layer)."""
    doc_id: str
    section_name: str  # e.g., '事業等のリスク', '経営方針'
    content_md: str
    session_id: str  # Traceability
