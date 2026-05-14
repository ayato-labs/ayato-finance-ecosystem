-- Reverting to compressed BLOBs for extreme storage efficiency
-- This is a breaking change for the narratives table, but necessary to handle multi-year backfills.
DROP TABLE IF EXISTS narr_db.narratives;

CREATE TABLE narr_db.narratives(
    doc_id VARCHAR, 
    section_name VARCHAR, 
    content_md BLOB, -- Using BLOB for zstd compressed data
    session_id VARCHAR, 
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY(doc_id, section_name)
);
