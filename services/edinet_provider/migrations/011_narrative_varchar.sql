-- Migration 011: Migrate content_md from BLOB to VARCHAR
CREATE TABLE narr_db.narratives_new (
    doc_id VARCHAR,
    section_name VARCHAR,
    content_md VARCHAR, -- VARCHAR instead of BLOB
    session_id VARCHAR,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(doc_id, section_name)
);

DROP TABLE IF EXISTS narr_db.narratives;
ALTER TABLE narr_db.narratives_new RENAME TO narratives;
