-- Migration 005: ENUM optimization
-- Note: DuckDB requires ENUM types to be created per-database.
-- Since we use ATTACH, we create them in the specific database.

-- 1. Create ENUM types
CREATE TYPE registry_db.form_code_t AS ENUM ('04A000', '090001', '020000', '04C000', '07A000', '030001', '113001', '120003', '042000', '170001', '027001', '054001', '07C000', '04C001', '030000', '102000', '040000', '110000', '170000', '010000', '060007', '043A00', '054000', '150003', '010002', '253000', '030002', '023001', '140000', '022000', '103000', '040001', '042100', '102101', '995000', '020002', '10A000', '142001', '022001', '024001', '023000', '020001', '04A001', '10C000', '053000', '053001', '102100', 'UNKNOWN');
CREATE TYPE registry_db.doc_type_code_t AS ENUM ('120', '200', '230', '160', '040', '350', '080', '240', '360', '135', '090', '235', '180', '030', '190', '270', '250', '130', '290', '100', '300', '220', '210', 'UNKNOWN');
CREATE TYPE facts_db.unit_t AS ENUM ('nan', '－', '円', 'pure', 'UNKNOWN');
CREATE TYPE facts_db.fiscal_period_t AS ENUM ('FY', 'Q1', 'Q2', 'Q3', 'Q4', 'UNKNOWN');

-- 2. Migrate registry_db.filings
CREATE TABLE registry_db.filings_new (
    doc_id VARCHAR PRIMARY KEY, 
    edinet_code VARCHAR, 
    sec_code VARCHAR, 
    filer_name VARCHAR, 
    doc_description VARCHAR, 
    submit_datetime TIMESTAMP, 
    form_code registry_db.form_code_t, 
    doc_type_code registry_db.doc_type_code_t, 
    session_id VARCHAR, 
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO registry_db.filings_new 
SELECT doc_id, edinet_code, sec_code, filer_name, doc_description, submit_datetime, 
       CAST(form_code AS registry_db.form_code_t), 
       CAST(doc_type_code AS registry_db.doc_type_code_t), 
       session_id, ingested_at 
FROM registry_db.filings;
DROP TABLE registry_db.filings;
ALTER TABLE registry_db.filings_new RENAME TO filings;

-- 3. Migrate facts_db.company_facts
CREATE TABLE facts_db.company_facts_new (
    doc_id VARCHAR, 
    item_name VARCHAR, 
    item_value DOUBLE, 
    unit facts_db.unit_t, 
    context_id VARCHAR, 
    fiscal_year INTEGER, 
    fiscal_period facts_db.fiscal_period_t, 
    session_id VARCHAR NOT NULL, 
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY(doc_id, item_name, context_id)
);
INSERT INTO facts_db.company_facts_new 
SELECT doc_id, item_name, item_value, 
       CAST(unit AS facts_db.unit_t), 
       context_id, fiscal_year, 
       CAST(fiscal_period AS facts_db.fiscal_period_t), 
       session_id, ingested_at 
FROM facts_db.company_facts;
DROP TABLE facts_db.company_facts;
ALTER TABLE facts_db.company_facts_new RENAME TO company_facts;

INSERT OR IGNORE INTO schema_version (version) VALUES (5);
