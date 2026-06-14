-- Migration 008: Global ENUM Resilience Fix
-- Rationale: Convert all potentially unbounded code fields to VARCHAR to prevent Conversion Errors from external data.

-- 1. Registry DB: Convert form_code and doc_type_code
CREATE TABLE IF NOT EXISTS registry_db.filings_v8 (
    doc_id VARCHAR PRIMARY KEY,
    edinet_code VARCHAR,
    sec_code VARCHAR,
    filer_name VARCHAR,
    doc_description VARCHAR,
    submit_datetime TIMESTAMP,
    form_code VARCHAR, -- Reverted from ENUM
    doc_type_code VARCHAR, -- Reverted from ENUM
    session_id VARCHAR,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO registry_db.filings_v8 (doc_id, edinet_code, sec_code, filer_name, doc_description, submit_datetime, form_code, doc_type_code, session_id, ingested_at)
SELECT doc_id, edinet_code, sec_code, filer_name, doc_description, submit_datetime,
       CAST(form_code AS VARCHAR), CAST(doc_type_code AS VARCHAR),
       session_id, ingested_at
FROM registry_db.filings;

DROP TABLE registry_db.filings;
ALTER TABLE registry_db.filings_v8 RENAME TO filings;

-- 2. Facts DB: Convert unit and fiscal_period
CREATE TABLE IF NOT EXISTS facts_db.company_facts_v8 (
    doc_id VARCHAR NOT NULL,
    item_name VARCHAR NOT NULL,
    item_value DOUBLE,
    unit VARCHAR, -- Reverted from ENUM
    context_id VARCHAR NOT NULL,
    fiscal_year INTEGER,
    fiscal_period VARCHAR, -- Reverted from ENUM
    session_id VARCHAR,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (doc_id, item_name, context_id)
);

INSERT INTO facts_db.company_facts_v8 (doc_id, item_name, item_value, unit, context_id, fiscal_year, fiscal_period, session_id, ingested_at)
SELECT doc_id, item_name, item_value, 
       CAST(unit AS VARCHAR), 
       context_id, fiscal_year, 
       CAST(fiscal_period AS VARCHAR), 
       session_id, ingested_at
FROM facts_db.company_facts;

DROP TABLE facts_db.company_facts;
ALTER TABLE facts_db.company_facts_v8 RENAME TO company_facts;

-- 3. Cleanup restrictive types
DROP TYPE IF EXISTS registry_db.form_code_enum;
DROP TYPE IF EXISTS registry_db.doc_type_code_enum;
DROP TYPE IF EXISTS registry_db.form_code_t;
DROP TYPE IF EXISTS registry_db.doc_type_code_t;
DROP TYPE IF EXISTS facts_db.unit_enum;
DROP TYPE IF EXISTS facts_db.period_enum;
DROP TYPE IF EXISTS facts_db.unit_t;
DROP TYPE IF EXISTS facts_db.fiscal_period_t;

-- Track migration version
INSERT OR IGNORE INTO schema_version (version) VALUES (8);
