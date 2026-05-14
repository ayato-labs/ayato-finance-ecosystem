-- Migration 007: Convert section_name from ENUM to VARCHAR for better resilience
-- Rationale: XBRL tags are unbounded. ENUM causes Conversion Error on new tags.

CREATE TABLE IF NOT EXISTS narr_db.narratives_v7 (
    doc_id VARCHAR NOT NULL,
    section_name VARCHAR NOT NULL, -- Reverted from section_name_t to VARCHAR
    content_md VARCHAR NOT NULL USING COMPRESSION ZSTD,
    session_id VARCHAR NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (doc_id, section_name)
);

-- Copy data, explicitly casting ENUM to VARCHAR
INSERT INTO narr_db.narratives_v7 (doc_id, section_name, content_md, session_id, ingested_at)
SELECT doc_id, CAST(section_name AS VARCHAR), content_md, session_id, ingested_at
FROM narr_db.narratives;

DROP TABLE narr_db.narratives;
ALTER TABLE narr_db.narratives_v7 RENAME TO narratives;

-- Cleanup the restrictive type
DROP TYPE IF EXISTS narr_db.section_name_t;

-- Track migration version
INSERT OR IGNORE INTO schema_version (version) VALUES (7);
