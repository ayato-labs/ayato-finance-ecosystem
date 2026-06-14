-- Shard: master
-- Table: ingestion_log
CREATE TABLE IF NOT EXISTS ingestion_log (
    doc_id VARCHAR PRIMARY KEY,
    status VARCHAR, -- (PENDING, SUCCESS, PARTIAL_FAIL)
    last_attempt TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT
);

-- Table: ingestion_progress
CREATE TABLE IF NOT EXISTS ingestion_progress (
    target_date DATE PRIMARY KEY,
    status VARCHAR, -- (completed, failed)
    doc_count INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
