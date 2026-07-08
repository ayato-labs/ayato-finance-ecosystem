import datetime as dt
from typing import ClassVar
from pydantic import BaseModel, Field

class BaseDbSchema(BaseModel):
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class CategorySchema(BaseDbSchema):
    category_id: int = Field(..., description="ID of the FRED category (Primary Key)")
    name: str | None = Field(None, description="Name of the category")
    last_audited: dt.datetime | None = Field(None, description="Timestamp when the category was last audited")

    class SQLConfig:
        table_name: ClassVar[str] = "categories"
        primary_key: ClassVar[list[str]] = ["category_id"]

class CategorySeriesSchema(BaseDbSchema):
    category_id: int = Field(..., description="Category ID mapping")
    series_id: str = Field(..., description="Series ID mapping")

    class SQLConfig:
        table_name: ClassVar[str] = "category_series"
        primary_key: ClassVar[list[str]] = ["category_id", "series_id"]

class ObservationSchema(BaseDbSchema):
    series_id: str = Field(..., description="FRED series symbol key")
    date: dt.date = Field(..., description="Date of the macro economic observation")
    value: float | None = Field(None, description="Numerical value of the observation on this date")

    class SQLConfig:
        table_name: ClassVar[str] = "observations"
        primary_key: ClassVar[list[str]] = ["series_id", "date"]

class SeriesMetadataSchema(BaseDbSchema):
    series_id: str = Field(..., description="FRED series symbol key (Primary Key)")
    title: str | None = Field(None, description="Title name of the macroeconomic series")
    units: str | None = Field(None, description="Reporting measurement units")
    frequency: str | None = Field(None, description="Measurement update frequency (e.g. Daily, Monthly)")
    seasonal_adjustment: str | None = Field(None, description="Seasonal adjustment status text")
    last_updated: dt.datetime | None = Field(None, description="Timestamp when series was last updated by FRED")
    notes: str | None = Field(None, description="Detailed explanatory notes regarding the series")
    observation_start: dt.date | None = Field(None, description="Start date of historical observations")
    observation_end: dt.date | None = Field(None, description="End date of historical observations")

    class SQLConfig:
        table_name: ClassVar[str] = "series_metadata"
        primary_key: ClassVar[list[str]] = ["series_id"]
