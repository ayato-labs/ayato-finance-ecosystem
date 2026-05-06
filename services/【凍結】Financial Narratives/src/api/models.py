from datetime import date, datetime

from pydantic import BaseModel


class PipelineStats(BaseModel):
    PENDING: int
    PROCESSING: int
    COMPLETED: int
    FAILED: int


class FilingRecord(BaseModel):
    accession_number: str
    ticker: str
    form: str
    filing_date: date
    sections: dict
    metadata: dict
    structured_facts: dict | None = None
    updated_at: datetime


class StatsResponse(BaseModel):
    total_filings: int
    ticker_stats: list[dict]
    pipeline_stats: PipelineStats | None = None
