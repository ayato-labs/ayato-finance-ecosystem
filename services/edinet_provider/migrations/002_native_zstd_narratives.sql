-- Migration to transition narratives from Python ZSTD BLOBs to Native DuckDB VARCHARs

-- 1. Create a new table with VARCHAR instead of BLOB
CREATE TABLE IF NOT EXISTS narratives_new(
    doc_id VARCHAR, 
    ticker VARCHAR, 
    section_name VARCHAR, 
    content_md VARCHAR, -- Changed from BLOB to VARCHAR
    filed_date DATE, 
    session_id VARCHAR, 
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY(doc_id, section_name)
);

-- We won't copy old BLOB data automatically because decompression in SQL is complex.
-- The incremental nature of the system means new data will populate this natively.
-- Drop the old table and rename the new one.
DROP TABLE IF EXISTS narratives;
ALTER TABLE narratives_new RENAME TO narratives;

INSERT INTO schema_version (version) VALUES (2);
