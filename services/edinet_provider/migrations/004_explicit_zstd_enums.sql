-- Migration to apply explicit Python-side Zstandard compression and dictionary/ENUM optimization
-- 1. Narratives: change content_md to BLOB for zstandard binary
CREATE TABLE IF NOT EXISTS narr_db.narratives_new(
    doc_id VARCHAR, 
    section_name VARCHAR, 
    content_md BLOB, -- To store Zstandard compressed bytes
    session_id VARCHAR NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY(doc_id, section_name)
);

DROP TABLE IF EXISTS narr_db.narratives;
ALTER TABLE narr_db.narratives_new RENAME TO narratives;

INSERT OR IGNORE INTO schema_version (version) VALUES (4);
