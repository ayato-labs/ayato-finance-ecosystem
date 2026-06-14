"""
Schema Definitions & Model Mapping
"""

from typing import Any

from src.datalake.shared.domain.contracts import (
    CompanyFact,
    DataContract,
    FilingMetadata,
    NarrativeBlock,
)

TABLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "master": {
        "description": "Master Control Database - State Management & Governance",
        "tables": {},
    },
    "registry_db": {
        "description": "Filing Registry & Taxonomy Metadata",
        "tables": {
            "filings": {"model": FilingMetadata},
        },
    },
    "facts_db": {
        "description": "Numerical Facts & Financial Statement Data",
        "tables": {
            "facts": {"model": CompanyFact},
        },
    },
    "narr_db": {
        "description": "Textual Narratives & Qualitative Analysis",
        "tables": {
            "narratives": {"model": NarrativeBlock},
        },
    },
}


def get_model_for_table(db_name: str, table_name: str) -> type[DataContract] | None:
    """Helper to retrieve the Pydantic model associated with a table."""
    return TABLE_DEFINITIONS.get(db_name, {}).get("tables", {}).get(table_name, {}).get("model")
