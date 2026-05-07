"""
Schema-as-Code: The authoritative definition of the EDINET Provider database.
This file serves as the Single Source of Truth (SSoT) for DDL and documentation.
"""
from typing import Dict, Any, Type
from src.domain.contracts import FilingMetadata, CompanyFact, NarrativeBlock, DataContract

TABLE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "master": {
        "description": "Master Control Database - State Management & Governance",
        "tables": {
            "schema_version": {
                "description": "Migration tracking for all database shards",
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
                        status ingestion_status_t, -- 'PENDING', 'SUCCESS', 'PARTIAL_FAIL'
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
                "model": FilingMetadata,
                "ddl": """
                    CREATE TABLE IF NOT EXISTS filings (
                        doc_id VARCHAR PRIMARY KEY,
                        edinet_code VARCHAR,
                        sec_code VARCHAR, -- Normalized 4-digit code
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
                "description": "Parsed numerical facts (Type 5 CSV) mapped to standard items",
                "model": CompanyFact,
                "ddl": """
                    CREATE TABLE IF NOT EXISTS company_facts (
                        doc_id VARCHAR NOT NULL,
                        item_name VARCHAR NOT NULL,
                        item_value DOUBLE,
                        unit VARCHAR,
                        context_id VARCHAR NOT NULL,
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
                "description": "Extracted text blocks (Business Risks, etc.) using ZSTD compression",
                "model": NarrativeBlock,
                "ddl": """
                    CREATE TABLE IF NOT EXISTS narratives (
                        doc_id VARCHAR NOT NULL,
                        section_name VARCHAR NOT NULL,
                        content_md VARCHAR NOT NULL USING COMPRESSION ZSTD,
                        session_id VARCHAR,
                        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (doc_id, section_name)
                    )
                """
            }
        }
    }
}


def get_model_for_table(db_name: str, table_name: str) -> Type[DataContract] | None:
    """Helper to retrieve the Pydantic model associated with a table."""
    return TABLE_DEFINITIONS.get(db_name, {}).get("tables", {}).get(table_name, {}).get("model")
