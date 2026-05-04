import os
from datetime import date

import pandas as pd
from loguru import logger

from src.core.config import settings
from src.core.db import db_manager


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
        """Initialize the EDINET database using MigrationManager."""
        if settings.db_read_only:
            logger.info("Skipping EDINET DB initialization in READ_ONLY mode.")
            return

        from src.core.migrations import MigrationManager

        MigrationManager.apply_migrations(self.db_path, "edinet")

    def save_document(self, doc_data: dict):
        """Saves document metadata with conflict handling."""
        logger.info(f"[DB] Saving document metadata: doc_id={doc_data['docID']}")
        try:
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as con:
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
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as con:
                res = con.execute("SELECT 1 FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
                return res is not None
        except Exception as e:
            logger.error(f"Error checking document existence for {doc_id}: {e}")
            return False

    def get_last_sync_date(self) -> date | None:
        """Retrieves the most recent submission date stored in the database."""
        try:
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as con:
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
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as con:
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
        """Saves AI-mapped facts into WIDE-FORMAT company_facts table."""
        if not facts:
            return

        logger.info(f"[DB] Saving {len(facts)} normalized records to company_facts (WIDE)...")
        try:
            ingest_df = pd.DataFrame(facts)
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
                # Dynamically build columns to match schema
                columns = [c for c in ingest_df.columns if c != "ingested_at"]
                col_list = ", ".join(columns)
                val_list = ", ".join([f"source.{c}" for c in columns])

                conn.register("ingest_df", ingest_df)
                conn.execute(f"""
                    INSERT OR IGNORE INTO company_facts ({col_list})
                    SELECT {val_list} FROM ingest_df AS source
                """)  # nosec S608
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
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
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
