from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SeriesMetadata(BaseModel):
    series_id: str
    title: str
    units: str
    frequency: str
    seasonal_adjustment: str
    last_updated: datetime
    notes: Optional[str] = None
