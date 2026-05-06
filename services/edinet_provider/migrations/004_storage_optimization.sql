-- Migration 004: Storage Optimization via ENUMs and ZSTD Compression
-- Goal: Improve storage efficiency by converting repetitive strings to ENUMs and applying ZSTD to text.

-- 1. Master DB: Ingestion Status
CREATE TYPE IF NOT EXISTS ingestion_status AS ENUM ('PENDING', 'SUCCESS', 'PARTIAL_FAIL');

CREATE TABLE IF NOT EXISTS ingestion_log (
    doc_id VARCHAR PRIMARY KEY,
    status VARCHAR NOT NULL,
    last_attempt TIMESTAMP NOT NULL,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE TABLE ingestion_log_new (
    doc_id VARCHAR PRIMARY KEY,
    status ingestion_status NOT NULL,
    last_attempt TIMESTAMP NOT NULL,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT
);

INSERT INTO ingestion_log_new SELECT * FROM ingestion_log;
DROP TABLE ingestion_log;
ALTER TABLE ingestion_log_new RENAME TO ingestion_log;


-- 2. Registry DB: Form Codes and Doc Types
CREATE TYPE IF NOT EXISTS registry_db.form_code_enum AS ENUM (SELECT DISTINCT form_code FROM registry_db.filings WHERE form_code IS NOT NULL);
CREATE TYPE IF NOT EXISTS registry_db.doc_type_code_enum AS ENUM (SELECT DISTINCT doc_type_code FROM registry_db.filings WHERE doc_type_code IS NOT NULL);

CREATE TABLE registry_db.filings_new (
    doc_id VARCHAR PRIMARY KEY,
    edinet_code VARCHAR NOT NULL,
    sec_code VARCHAR,
    filer_name VARCHAR NOT NULL,
    doc_description VARCHAR,
    submit_datetime TIMESTAMP NOT NULL,
    form_code registry_db.form_code_enum,
    doc_type_code registry_db.doc_type_code_enum,
    session_id VARCHAR NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO registry_db.filings_new SELECT * FROM registry_db.filings;
DROP TABLE registry_db.filings;
ALTER TABLE registry_db.filings_new RENAME TO filings;


-- 3. Facts DB: Units and Periods
CREATE TYPE IF NOT EXISTS facts_db.unit_enum AS ENUM (SELECT DISTINCT unit FROM facts_db.company_facts WHERE unit IS NOT NULL);
CREATE TYPE IF NOT EXISTS facts_db.period_enum AS ENUM (SELECT DISTINCT fiscal_period FROM facts_db.company_facts WHERE fiscal_period IS NOT NULL);

CREATE TABLE facts_db.company_facts_new (
    doc_id VARCHAR NOT NULL,
    item_name VARCHAR NOT NULL,
    item_value DOUBLE,
    unit facts_db.unit_enum,
    context_id VARCHAR NOT NULL,
    fiscal_year INTEGER,
    fiscal_period facts_db.period_enum,
    session_id VARCHAR NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (doc_id, item_name, context_id)
);

INSERT INTO facts_db.company_facts_new SELECT * FROM facts_db.company_facts;
DROP TABLE facts_db.company_facts;
ALTER TABLE facts_db.company_facts_new RENAME TO company_facts;


-- 4. Narrative DB: Section Names and ZSTD Compression
CREATE TYPE IF NOT EXISTS narr_db.section_name_enum AS ENUM (SELECT DISTINCT section_name FROM narr_db.narratives WHERE section_name IS NOT NULL);

CREATE TABLE narr_db.narratives_new (
    doc_id VARCHAR NOT NULL,
    section_name narr_db.section_name_enum NOT NULL,
    content_md VARCHAR NOT NULL USING COMPRESSION ZSTD,
    session_id VARCHAR NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (doc_id, section_name)
);

INSERT INTO narr_db.narratives_new SELECT * FROM narr_db.narratives;
DROP TABLE narr_db.narratives;
ALTER TABLE narr_db.narratives_new RENAME TO narratives;

-- Update schema version
INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (4, CURRENT_TIMESTAMP);
