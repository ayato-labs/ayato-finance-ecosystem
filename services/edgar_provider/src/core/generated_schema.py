"""
AUTO-GENERATED FILE. DO NOT EDIT.
Generated from src/core/contracts.py
"""

TABLE_SCHEMAS = {
    "metrics": {
        "v1": """
CREATE TABLE IF NOT EXISTS metrics (
    run_id VARCHAR,
    step_name VARCHAR,
    ticker VARCHAR,
    latency_ms DOUBLE,
    status VARCHAR,
    error_log VARCHAR,
    inputs VARCHAR,
    outputs VARCHAR,
    recorded_at TIMESTAMP
);
        """
    },
    "processed_companies": {
        "v1": """
CREATE TABLE IF NOT EXISTS processed_companies (
    ticker VARCHAR,
    cik VARCHAR,
    status VARCHAR,
    last_processed_at TIMESTAMP,
    error_log VARCHAR,
    PRIMARY KEY (ticker)
);
        """
    },
    "tickers": {
        "v1": """
CREATE TABLE IF NOT EXISTS tickers (
    ticker VARCHAR,
    cik VARCHAR,
    name VARCHAR,
    exchange VARCHAR,
    last_session_id VARCHAR,
    ingested_at TIMESTAMP,
    PRIMARY KEY (ticker)
);
        """
    },
    "company_facts": {
        "v1": """
CREATE TABLE IF NOT EXISTS company_facts (
    ticker VARCHAR,
    cik VARCHAR,
    accession_number VARCHAR,
    form VARCHAR,
    filed_date DATE,
    fiscal_year SMALLINT,
    fiscal_period VARCHAR,
    label VARCHAR,
    value DOUBLE,
    unit VARCHAR,
    is_standardized BOOLEAN,
    raw_tag VARCHAR,
    session_id VARCHAR,
    ingested_at TIMESTAMP,
    PRIMARY KEY (ticker, accession_number, label)
);
        """
    },
    "narratives": {
        "v1": """
CREATE TABLE IF NOT EXISTS narratives (
    ticker VARCHAR,
    cik VARCHAR,
    accession_number VARCHAR,
    form VARCHAR,
    filed_date DATE,
    section_name VARCHAR,
    content_md_zstd BLOB,
    session_id VARCHAR,
    ingested_at TIMESTAMP,
    PRIMARY KEY (ticker, accession_number, section_name)
);
        """
    },
    "databases": {
        "v1": """
CREATE TABLE IF NOT EXISTS databases (
    db_id VARCHAR,
    file_path VARCHAR,
    role VARCHAR,
    schema_version VARCHAR,
    created_at TIMESTAMP,
    PRIMARY KEY (db_id)
);
        """
    },
    "data_catalog": {
        "v1": """
CREATE TABLE IF NOT EXISTS data_catalog (
    partition_key VARCHAR,
    db_id VARCHAR,
    description VARCHAR,
    updated_at TIMESTAMP,
    PRIMARY KEY (partition_key)
);
        """
    },
}

INDEX_SCHEMAS = [
    "CREATE INDEX IF NOT EXISTS idx_us_tickers_cik ON tickers (cik)",
    "CREATE INDEX IF NOT EXISTS idx_us_facts_lookup ON company_facts (ticker, fiscal_year, fiscal_period)",
    "CREATE INDEX IF NOT EXISTS idx_us_narratives_lookup ON narratives (ticker, form, section_name)",
]
