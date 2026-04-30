import os
from datetime import date

import duckdb
import pandas as pd
from loguru import logger

from src.core.config import settings


class EDINETStorage:
    """
    DuckDB-based storage for EDINET statutory data.
    Ensures data integrity and full audit trail for all operations.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(settings.DB_PATH_EDINET)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        logger.info(f"Initializing EDINETStorage at {self.db_path}")
        try:
            self._init_db()
        except Exception as e:
            logger.error(f"Failed to initialize EDINET database: {e}", exc_info=True)
            raise RuntimeError("Database Initialization Failure") from e

    def _init_db(self):
        """Schema definition with performance and traceability indexes."""
        if settings.db_read_only:
            logger.info("Skipping EDINET DB initialization in READ_ONLY mode.")
            return
        with duckdb.connect(self.db_path) as con:
            # Document Metadata
            con.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    filer_name VARCHAR,
                    doc_description VARCHAR,
                    submission_date DATE,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Raw Facts from CSV (Audit trail of original data)
            con.execute("""
                CREATE TABLE IF NOT EXISTS raw_facts (
                    doc_id VARCHAR,
                    element_id VARCHAR,
                    element_name VARCHAR,
                    context_id VARCHAR,
                    amount_value DOUBLE,
                    unit_name VARCHAR,
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                )
            """)

            # Normalized Facts (Mirrors J-Quants schema)
            con.execute("""
                CREATE TABLE IF NOT EXISTS company_facts (
                    fact_id VARCHAR PRIMARY KEY,
                    code VARCHAR,
                    disclosed_date DATE,
                    fiscal_year INTEGER,
                    fiscal_period VARCHAR,
                    taxonomy VARCHAR,
                    tag VARCHAR,
                    label VARCHAR,
                    value DOUBLE,
                    unit VARCHAR,
                    accession_number VARCHAR,
                    session_id VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Reconciliation Audit Log (Who won and why)
            con.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation_audit (
                    audit_id VARCHAR PRIMARY KEY,
                    code VARCHAR,
                    disclosed_date DATE,
                    label VARCHAR,
                    jquants_val DOUBLE,
                    edinet_val DOUBLE,
                    merged_val DOUBLE,
                    strategy VARCHAR,
                    reasoning VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            con.execute("CREATE INDEX IF NOT EXISTS idx_facts_doc ON raw_facts(doc_id)")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_edinet_facts_lookup "
                "ON company_facts (code, tag, disclosed_date)"
            )
            logger.info("EDINET database schema verified and indexes created.")

    def save_document(self, doc_data: dict):
        """Saves document metadata with conflict handling."""
        logger.info(f"[DB] Saving document metadata: doc_id={doc_data['docID']}")
        try:
            with duckdb.connect(self.db_path, read_only=settings.db_read_only) as con:
                con.execute(
                    """
                    INSERT OR IGNORE INTO documents (
                        doc_id, ticker, filer_name, doc_description, submission_date
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        doc_data["docID"],
                        doc_data.get("secCode"),
                        doc_data.get("filerName"),
                        doc_data.get("docDescription"),
                        doc_data.get("submissionPeriod"),
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to save document {doc_data['docID']}: {e}", exc_info=True)
            raise

    def is_document_exists(self, doc_id: str) -> bool:
        """Checks if a document has already been processed."""
        try:
            with duckdb.connect(self.db_path, read_only=settings.db_read_only) as con:
                res = con.execute("SELECT 1 FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
                return res is not None
        except Exception as e:
            logger.error(f"Error checking document existence for {doc_id}: {e}")
            return False

    def get_last_sync_date(self) -> date | None:
        """Retrieves the most recent submission date stored in the database."""
        try:
            with duckdb.connect(self.db_path, read_only=settings.db_read_only) as con:
                res = con.execute("SELECT MAX(submission_date) FROM documents").fetchone()
                if res and res[0]:
                    return res[0]
                return None
        except Exception as e:
            logger.error(f"Error retrieving last sync date: {e}")
            return None

    def save_facts(self, doc_id: str, facts: list[dict]):
        """Saves raw facts for auditability."""
        if not facts:
            logger.warning(f"No facts to save for doc_id={doc_id}")
            return

        logger.info(f"[DB] Bulk inserting {len(facts)} raw facts for doc_id={doc_id}")
        try:
            with duckdb.connect(self.db_path, read_only=settings.db_read_only) as con:
                con.executemany(
                    """
                    INSERT INTO raw_facts (
                        doc_id, element_id, element_name, context_id, amount_value, unit_name
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (doc_id, f["id"], f["name"], f["context"], f["value"], f["unit"])
                        for f in facts
                    ],
                )
        except Exception as e:
            logger.error(f"Failed to bulk insert raw facts for {doc_id}: {e}", exc_info=True)
            raise

    def save_normalized_facts(self, facts: list[dict]):
        """Saves AI-mapped facts into company_facts table."""
        if not facts:
            return

        logger.info(f"[DB] Saving {len(facts)} normalized facts to company_facts...")
        try:
            ingest_df = pd.DataFrame(facts)
            with duckdb.connect(self.db_path, read_only=settings.db_read_only) as conn:
                # Use register to ensure DuckDB sees the dataframe reliably
                conn.register("ingest_df", ingest_df)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO company_facts (
                        fact_id, code, disclosed_date, fiscal_year, fiscal_period,
                        taxonomy, tag, label, value, unit, accession_number, session_id
                    )
                    SELECT
                        md5(concat_ws('|', code, disclosed_date, tag, accession_number)) as fact_id,
                        code, disclosed_date, fiscal_year, fiscal_period,
                        taxonomy, tag, label, value, unit, accession_number, session_id
                    FROM ingest_df
                    """
                )
        except Exception as e:
            logger.error(f"Critical error saving normalized facts: {e}", exc_info=True)
            raise

    def save_reconciliation_audit(self, audit_records: list[dict]):
        """Saves Stage 2 reconciliation choices for auditability."""
        if not audit_records:
            return

        logger.info(f"[DB] Logging {len(audit_records)} reconciliation decisions for audit.")
        try:
            audit_df = pd.DataFrame(audit_records)
            with duckdb.connect(self.db_path, read_only=settings.db_read_only) as conn:
                conn.register("audit_df", audit_df)
                conn.execute(
                    """
                    INSERT INTO reconciliation_audit (
                        audit_id, code, disclosed_date, label,
                        jquants_val, edinet_val, merged_val, strategy, reasoning
                    )
                    SELECT
                        md5(concat_ws('|', code, disclosed_date, label, strategy)) as audit_id,
                        code, disclosed_date, label,
                        jquants_val, edinet_val, merged_val, strategy, reasoning
                    FROM audit_df
                    """
                )
        except Exception as e:
            logger.error(f"Failed to save reconciliation audit log: {e}", exc_info=True)
            raise
