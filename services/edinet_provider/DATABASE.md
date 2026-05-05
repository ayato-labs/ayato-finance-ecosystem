# EDINET Provider Database Documentation
*Generated on: 2026-05-06 07:26:50*

This document is automatically generated from `src/core/schema.py` (Schema-as-Code).

## Architecture: The Quad-Split (Master Governance)
The system uses a Master database to orchestrate three specialized storage databases.

### Database: `master`
**Description**: Master Control Database - State Management & Governance

#### Table: `schema_version`
Migration tracking

```sql
CREATE TABLE schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
```

#### Table: `ingestion_log`
Tracks sync status and self-healing progress

```sql
CREATE TABLE ingestion_log (
                        doc_id VARCHAR PRIMARY KEY,
                        status VARCHAR, -- 'PENDING', 'SUCCESS', 'PARTIAL_FAIL'
                        last_attempt TIMESTAMP,
                        retry_count INTEGER DEFAULT 0,
                        error_message TEXT
                    )
```

### Database: `registry_db`
**Description**: Registry Database - Document Catalog & Metadata

#### Table: `filings`
Metadata for every filed document

```sql
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
```

### Database: `facts_db`
**Description**: Facts Database - Numerical Financial Data

#### Table: `company_facts`
Parsed CSV data (Type 5) mapped to standard items

```sql
CREATE TABLE company_facts (
                        doc_id VARCHAR,
                        item_name VARCHAR,
                        item_value DOUBLE,
                        unit VARCHAR,
                        context_id VARCHAR,
                        fiscal_year INTEGER,
                        fiscal_period VARCHAR,
                        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (doc_id, item_name, context_id)
                    )
```

### Database: `narr_db`
**Description**: Narratives Database - Unstructured Text Storage

#### Table: `narratives`
Extracted text blocks (Business Risks, etc.) with ZSTD optimization

```sql
CREATE TABLE narratives (
                        doc_id VARCHAR,
                        section_name VARCHAR,
                        content_md VARCHAR,
                        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (doc_id, section_name)
                    )
```