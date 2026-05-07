from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SeriesMetadata(BaseModel):
    series_id: str
    title: str
    units: str
    frequency: str
    seasonal_adjustment: str
    last_updated: datetime
    notes: Optional[str] = None
