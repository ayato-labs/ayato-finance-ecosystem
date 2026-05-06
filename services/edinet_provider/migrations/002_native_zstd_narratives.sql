-- Migration to transition narratives from Python ZSTD BLOBs to Native DuckDB VARCHARs

-- 1. Create a new table with VARCHAR instead of BLOB
CREATE TABLE IF NOT EXISTS narr_db.narratives_new(
    doc_id VARCHAR, 
    ticker VARCHAR, 
    section_name VARCHAR, 
    content_md VARCHAR, -- Changed from BLOB to VARCHAR
    filed_date DATE, 
    session_id VARCHAR, 
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY(doc_id, section_name)
);

DROP TABLE IF EXISTS narr_db.narratives;
ALTER TABLE narr_db.narratives_new RENAME TO narratives;

INSERT INTO schema_version (version) VALUES (2);
