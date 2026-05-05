TABLE_SCHEMAS = {
    "filings": {
        "v1": """
            CREATE TABLE filings (
                doc_id VARCHAR PRIMARY KEY,
                edinet_code VARCHAR,
                sec_code VARCHAR,
                filer_name VARCHAR,
                doc_description VARCHAR,
                submit_datetime TIMESTAMP,
                form_code VARCHAR,
                doc_type_code VARCHAR,
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
    },
    "company_facts": {
        "v1": """
            CREATE TABLE company_facts (
                doc_id VARCHAR,
                ticker VARCHAR,
                item_name VARCHAR,
                item_value DOUBLE,
                unit VARCHAR,
                context_id VARCHAR,
                filed_date DATE,
                fiscal_year INTEGER,
                fiscal_period VARCHAR,
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (doc_id, item_name, context_id)
            )
        """
    },
    "narratives": {
        "v1": """
            CREATE TABLE narratives (
                doc_id VARCHAR,
                ticker VARCHAR,
                section_name VARCHAR,
                content_md_zstd BLOB,
                filed_date DATE,
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (doc_id, section_name)
            )
        """
    },
}

INDEX_SCHEMAS = [
    "CREATE INDEX IF NOT EXISTS idx_jp_filings_ticker ON filings (sec_code)",
    "CREATE INDEX IF NOT EXISTS idx_jp_facts_ticker ON company_facts (ticker)",
    "CREATE INDEX IF NOT EXISTS idx_jp_narratives_ticker ON narratives (ticker)",
]
