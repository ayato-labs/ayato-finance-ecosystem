CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS filings(
    doc_id VARCHAR PRIMARY KEY, 
    edinet_code VARCHAR, 
    sec_code VARCHAR, 
    filer_name VARCHAR, 
    doc_description VARCHAR, 
    submit_datetime TIMESTAMP, 
    form_code VARCHAR, 
    doc_type_code VARCHAR, 
    session_id VARCHAR, 
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_facts(
    doc_id VARCHAR, 
    ticker VARCHAR, 
    item_name VARCHAR, 
    item_value DOUBLE, 
    unit VARCHAR, 
    context_id VARCHAR, 
    filed_date DATE, 
    fiscal_year INTEGER, 
    fiscal_period VARCHAR, 
    session_id VARCHAR, 
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY(doc_id, item_name, context_id)
);

CREATE TABLE IF NOT EXISTS narratives(
    doc_id VARCHAR, 
    ticker VARCHAR, 
    section_name VARCHAR, 
    content_md_zstd BLOB, 
    filed_date DATE, 
    session_id VARCHAR, 
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY(doc_id, section_name)
);

INSERT INTO schema_version (version) VALUES (1);
