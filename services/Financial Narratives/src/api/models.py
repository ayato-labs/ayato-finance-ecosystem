from pydantic import BaseModel
from datetime import datetime, date

class SectionData(BaseModel):
    # Dynamic sections like "Item 1", "Item 1A", etc.
    # We use a dict since section names vary
    sections: dict[str, str | None]

class FilingRecord(BaseModel):
    accession_number: str
    ticker: str
    form: str
    filing_date: date
    sections: dict
    metadata: dict
    updated_at: datetime


class StatsResponse(BaseModel):
    total_filings: int
    ticker_stats: list[dict]
