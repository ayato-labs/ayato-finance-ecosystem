-- Migration to remove redundant columns from facts and narratives tables
-- Kept session_id for traceability as per system requirements.

-- 1. Recreate company_facts without ticker, filed_date
CREATE TABLE IF NOT EXISTS company_facts_new(
    doc_id VARCHAR, 
    item_name VARCHAR, 
    item_value DOUBLE, 
    unit VARCHAR, 
    context_id VARCHAR, 
    fiscal_year INTEGER, 
    fiscal_period VARCHAR, 
    session_id VARCHAR NOT NULL, -- Restored
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY(doc_id, item_name, context_id)
);

DROP TABLE IF EXISTS company_facts;
ALTER TABLE company_facts_new RENAME TO company_facts;

-- 2. Recreate narratives without ticker, filed_date
CREATE TABLE IF NOT EXISTS narratives_new(
    doc_id VARCHAR, 
    section_name VARCHAR, 
    content_md VARCHAR,
    session_id VARCHAR NOT NULL, -- Restored
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY(doc_id, section_name)
);

DROP TABLE IF EXISTS narratives;
ALTER TABLE narratives_new RENAME TO narratives;

INSERT INTO schema_version (version) VALUES (3);
