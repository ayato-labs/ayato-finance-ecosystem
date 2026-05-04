from datetime import date, datetime
from pydantic import BaseModel

class FilingRecord(BaseModel):
    accession_number: str
    ticker: str
    form: str
    filing_date: date
    sections: dict
    metadata: dict
    structured_facts: dict | None = None
    updated_at: datetime


class SyncResponse(BaseModel):
    message: str
    status: str
