from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

class DataContract(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore")

class MetricsContract(DataContract):
    """Execution metrics and tracing for pipeline steps."""
    run_id: str = Field(..., description="Unique identifier for the execution run")
    step_name: str = Field(..., description="Name of the pipeline step")
    ticker: str = Field(..., description="Ticker symbol being processed")
    latency_ms: float = Field(..., description="Execution time in milliseconds")
    status: str = Field(..., description="Status of the step (success, failed)")
    error_log: str | None = Field(None, description="Error message if failed")
    inputs: str | None = Field(None, description="JSON string of inputs")
    outputs: str | None = Field(None, description="JSON string of outputs")
    recorded_at: datetime | None = Field(default_factory=datetime.now, description="Timestamp of recording")

class ProcessedCompanyContract(DataContract):
    """State tracking for ingested companies."""
    ticker: str = Field(..., description="Ticker symbol of the company")
    cik: str | None = Field(None, description="CIK identifier")
    status: str = Field(..., description="Current ingestion status (completed, failed)")
    last_processed_at: datetime | None = Field(default_factory=datetime.now, description="Last update timestamp")
    error_log: str | None = Field(None, description="Error message if failed")

class USTickerContract(DataContract):
    """Metadata for SEC registered companies."""
    ticker: str = Field(..., description="Stock ticker symbol")
    cik: str = Field(..., description="Central Index Key (10 digits)")
    name: str = Field(..., description="Company legal name")
    exchange: str | None = Field(None, description="Stock exchange name")
    last_session_id: str = Field(..., description="Session ID that ingested this record")
    ingested_at: datetime | None = Field(default_factory=datetime.now, description="Timestamp of ingestion")

class USFactContract(DataContract):
    """Standardized financial facts (XBRL)."""
    ticker: str = Field(..., description="Stock ticker symbol")
    cik: str = Field(..., description="Central Index Key")
    accession_number: str = Field(..., description="Filing accession number")
    form: str = Field(..., description="Filing form type (e.g., 10-K, 10-Q)")
    filed_date: date = Field(..., description="Date the filing was submitted")
    fiscal_year: int = Field(..., description="Fiscal year of the statement")
    fiscal_period: str = Field(..., description="Fiscal period (e.g., Q1, FY)")
    label: str = Field(..., description="Standardized fact label (e.g., NetIncome)")
    value: float | None = Field(None, description="Numeric value of the fact")
    unit: str | None = Field(None, description="Unit of measurement (e.g., USD)")
    is_standardized: bool = Field(True, description="Whether the label is normalized")
    raw_tag: str | None = Field(None, description="Original XBRL tag for traceability")
    session_id: str = Field(..., description="Session ID that ingested this record")
    ingested_at: datetime | None = Field(default_factory=datetime.now, description="Timestamp of ingestion")

class USNarrativeContract(DataContract):
    """Extracted text narratives from filings."""
    ticker: str = Field(..., description="Stock ticker symbol")
    cik: str = Field(..., description="Central Index Key")
    accession_number: str = Field(..., description="Filing accession number")
    form: str = Field(..., description="Filing form type (e.g., 10-K, 10-Q)")
    filed_date: date = Field(..., description="Date the filing was submitted")
    section_name: str = Field(..., description="Extracted section (e.g., 'Risk Factors', 'MD&A')")
    content_md_zstd: bytes = Field(..., description="Zstandard compressed markdown content")
    session_id: str = Field(..., description="Session ID that ingested this record")
    ingested_at: datetime | None = Field(default_factory=datetime.now, description="Timestamp of ingestion")

# --- Master Database (Control Plane) Contracts ---

class DatabaseRegistryContract(DataContract):
    """Registry of distributed database files."""
    db_id: str = Field(..., description="Unique identifier for the database shard (e.g., 'edgar_2024')")
    file_path: str = Field(..., description="Relative or absolute path to the DuckDB file")
    role: str = Field(..., description="Role of this DB (e.g., 'facts', 'narratives', 'master')")
    schema_version: str = Field(..., description="Current schema version of this DB")
    created_at: datetime | None = Field(default_factory=datetime.now, description="Creation timestamp")

class DataCatalogContract(DataContract):
    """Catalog mapping data partitions to database shards."""
    partition_key: str = Field(..., description="Key describing the partition (e.g., 'AAPL_2024')")
    db_id: str = Field(..., description="Identifier of the database shard holding this partition")
    description: str | None = Field(None, description="Human-readable description of the partition")
    updated_at: datetime | None = Field(default_factory=datetime.now, description="Last update timestamp")
