import duckdb
import os

def generate_migration():
    reg_db = 'data/edinet_registry.duckdb'
    facts_db = 'data/edinet_facts.duckdb'
    
    conn_reg = duckdb.connect(reg_db)
    forms = [r[0] for r in conn_reg.execute('SELECT DISTINCT form_code FROM filings WHERE form_code IS NOT NULL').fetchall()]
    docs = [r[0] for r in conn_reg.execute('SELECT DISTINCT doc_type_code FROM filings WHERE doc_type_code IS NOT NULL').fetchall()]
    conn_reg.close()
    
    conn_facts = duckdb.connect(facts_db)
    units = [r[0] for r in conn_facts.execute('SELECT DISTINCT unit FROM company_facts WHERE unit IS NOT NULL').fetchall()]
    if 'pure' not in units:
        units.append('pure')
    conn_facts.close()
    
    # Form types and doc types can be many, let's just make sure we have the ones we found.
    # We add 'UNKNOWN' to all enums just in case.
    for l in [forms, docs, units]:
        if 'UNKNOWN' not in l:
            l.append('UNKNOWN')

    sql = f"""-- Migration 005: ENUM optimization
-- Note: DuckDB requires ENUM types to be created per-database.
-- Since we use ATTACH, we create them in the specific database.

-- 1. Create ENUM types
CREATE TYPE registry_db.form_code_t AS ENUM ({', '.join([f"'{v}'" for v in forms])});
CREATE TYPE registry_db.doc_type_code_t AS ENUM ({', '.join([f"'{v}'" for v in docs])});
CREATE TYPE facts_db.unit_t AS ENUM ({', '.join([f"'{v}'" for v in units])});
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
"""
    with open('migrations/005_optimize_enums.sql', 'w', encoding='utf-8') as f:
        f.write(sql)
    print("Migration 005 generated.")

if __name__ == "__main__":
    generate_migration()
