"""
Schema-as-Code: The authoritative definition of the EDINET Provider database.
This file serves as the Single Source of Truth (SSoT) for DDL and documentation.
"""

TABLE_DEFINITIONS = {
    "master": {
        "description": "Master Control Database - State Management & Governance",
        "tables": {
            "schema_version": {
                "description": "Migration tracking",
                "ddl": """
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            },
            "ingestion_log": {
                "description": "Tracks sync status and self-healing progress",
                "ddl": """
                    CREATE TABLE IF NOT EXISTS ingestion_log (
                        doc_id VARCHAR PRIMARY KEY,
                        status VARCHAR, -- 'PENDING', 'SUCCESS', 'PARTIAL_FAIL'
                        last_attempt TIMESTAMP,
                        retry_count INTEGER DEFAULT 0,
                        error_message TEXT
                    )
                """
            }
        }
    },
    "registry_db": {
        "description": "Registry Database - Document Catalog & Metadata",
        "tables": {
            "filings": {
                "description": "Metadata for every filed document",
                "ddl": """
                    CREATE TABLE IF NOT EXISTS filings (
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
            }
        }
    },
    "facts_db": {
        "description": "Facts Database - Numerical Financial Data",
        "tables": {
            "company_facts": {
                "description": "Parsed CSV data (Type 5) mapped to standard items",
                "ddl": """
                    CREATE TABLE IF NOT EXISTS company_facts (
                        doc_id VARCHAR,
                        item_name VARCHAR,
                        item_value DOUBLE,
                        unit VARCHAR,
                        context_id VARCHAR,
                        fiscal_year INTEGER,
                        fiscal_period VARCHAR,
                        session_id VARCHAR,
                        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (doc_id, item_name, context_id)
                    )
                """
            }
        }
    },
    "narr_db": {
        "description": "Narratives Database - Unstructured Text Storage",
        "tables": {
            "narratives": {
                "description": "Extracted text blocks (Business Risks, etc.)",
                "ddl": """
                    CREATE TABLE IF NOT EXISTS narratives (
                        doc_id VARCHAR,
                        section_name VARCHAR,
                        content_md VARCHAR,
                        session_id VARCHAR,
                        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (doc_id, section_name)
                    )
                """
            }
        }
    }
}
