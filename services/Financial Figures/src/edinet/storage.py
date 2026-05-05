import os
from datetime import date

import pandas as pd
from loguru import logger

from src.core.config import settings
from src.core.db import db_manager


class EDINETStorage:
    """
    DuckDB-based storage for EDINET statutory data.
    Ensures physical separation between Raw Data Lake (Bronze) and Normalized Data (Silver).
    """

    def __init__(self, raw_db_path: str | None = None, norm_db_path: str | None = None):
        self.raw_db_path = raw_db_path or str(settings.DB_PATH_EDINET_RAW)
        self.norm_db_path = norm_db_path or str(settings.DB_PATH_EDINET_NORM)

        os.makedirs(os.path.dirname(self.raw_db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.norm_db_path), exist_ok=True)
        logger.info(
            f"Initializing EDINETStorage (Raw: {self.raw_db_path}, Norm: {self.norm_db_path})"
        )
        try:
            self._init_db()
        except Exception as e:
            logger.error(f"Failed to initialize EDINET databases: {e}", exc_info=True)
            raise RuntimeError("Database Initialization Failure") from e

    def _init_db(self):
        """Initialize both EDINET databases using MigrationManager."""
        if settings.db_read_only:
            logger.info("Skipping EDINET DB initialization in READ_ONLY mode.")
            return

        from src.core.migrations import MigrationManager

        # Initialize Raw DB (Documents, Raw Facts)
        MigrationManager.apply_migrations(self.raw_db_path, "edinet_raw")
        # Initialize Norm DB (Normalized company_facts)
        MigrationManager.apply_migrations(self.norm_db_path, "edinet_norm")

    def save_document(self, doc_data: dict):
        """Saves document metadata to the RAW database."""
        logger.info(f"[DB-RAW] Saving document metadata: doc_id={doc_data['docID']}")
        try:
            with db_manager.connect(self.raw_db_path, read_only=settings.db_read_only) as con:
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
                        doc_data.get("submitDateTime"),
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to save document {doc_data['docID']}: {e}", exc_info=True)
            raise

    def get_existing_doc_ids(self, doc_ids: list[str]) -> set[str]:
        """Checks multiple doc_ids existence in the RAW database in a single query."""
        if not doc_ids:
            return set()
        try:
            with db_manager.connect(self.raw_db_path, read_only=True) as con:
                # Use a temp table or a join if doc_ids is very large,
                # but for ~200-1000 items, WHERE IN (?) is fine.
                placeholders = ",".join(["?"] * len(doc_ids))
                query = f"SELECT doc_id FROM documents WHERE doc_id IN ({placeholders})"  # noqa: S608
                res = con.execute(query, doc_ids).fetchall()
                return {r[0] for r in res}
        except Exception as e:
            logger.error(f"Error checking bulk document existence: {e}")
            raise

    def get_last_sync_date(self) -> date | None:
        """Retrieves most recent date from the RAW database."""
        try:
            with db_manager.connect(self.raw_db_path, read_only=settings.db_read_only) as con:
                res = con.execute("SELECT MAX(submission_date) FROM documents").fetchone()
                if res and res[0]:
                    return res[0]
                return None
        except Exception as e:
            logger.error(f"Error retrieving last sync date: {e}")
            return None

    def get_existing_norm_ids(self, doc_ids: list[str]) -> set[str]:
        """Checks multiple doc_ids existence in the NORMALIZED database in bulk."""
        if not doc_ids:
            return set()
        try:
            with db_manager.connect(self.norm_db_path, read_only=True) as con:
                placeholders = ",".join(["?"] * len(doc_ids))
                query = (
                    "SELECT DISTINCT accession_number FROM company_facts "  # noqa: S608
                    f"WHERE accession_number IN ({placeholders})"
                )
                res = con.execute(query, doc_ids).fetchall()
                return {r[0] for r in res}
        except Exception as e:
            logger.error(f"Error checking bulk normalized existence: {e}")
            return set()

    def save_facts(self, doc_id: str, facts: list[dict]):
        """Saves raw facts to the RAW database."""
        if not facts:
            logger.warning(f"No facts to save for doc_id={doc_id}")
            return

        logger.info(f"[DB-RAW] Bulk inserting {len(facts)} raw facts for doc_id={doc_id}")
        try:
            with db_manager.connect(self.raw_db_path, read_only=settings.db_read_only) as con:
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

    def get_facts_by_doc(self, doc_id: str) -> list[dict]:
        """Retrieves raw facts for a specific document from the RAW database."""
        try:
            with db_manager.connect(self.raw_db_path, read_only=True) as con:
                res = con.execute(
                    """
                    SELECT element_id, element_name, amount_value
                    FROM raw_facts
                    WHERE doc_id = ?
                    """,
                    [doc_id],
                ).fetchall()
                return [{"id": r[0], "name": r[1], "value": r[2]} for r in res]
        except Exception as e:
            logger.error(f"Failed to fetch facts for {doc_id}: {e}")
            return []

    def save_normalized_facts(self, facts: list[dict]):
        """Saves AI-mapped facts into the NORMALIZED database (Silver)."""
        if not facts:
            return

        logger.info(f"[DB-NORM] Saving {len(facts)} normalized records to company_facts...")
        try:
            ingest_df = pd.DataFrame(facts)
            with db_manager.connect(self.norm_db_path, read_only=settings.db_read_only) as conn:
                # Dynamically build columns to match schema
                columns = [c for c in ingest_df.columns if c != "ingested_at"]
                col_list = ", ".join(columns)
                val_list = ", ".join([f"source.{c}" for c in columns])

                conn.register("ingest_df", ingest_df)
                query = f"""
                    INSERT OR IGNORE INTO company_facts ({col_list})
                    SELECT {val_list} FROM ingest_df AS source
                """  # noqa: S608
                conn.execute(query)
        except Exception as e:
            logger.error(f"Critical error saving normalized facts: {e}", exc_info=True)
            raise

    def save_reconciliation_audit(self, audit_records: list[dict]):
        """Saves Stage 2 reconciliation choices for auditability in the NORMALIZED DB."""
        if not audit_records:
            return

        logger.info(f"[DB-NORM] Logging {len(audit_records)} reconciliation decisions for audit.")
        try:
            audit_df = pd.DataFrame(audit_records)
            with db_manager.connect(self.norm_db_path, read_only=settings.db_read_only) as conn:
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

    def get_tag_mappings(self, source_tags: list[str]) -> dict[str, dict]:
        """Retrieves cached AI mappings from the NORM database."""
        if not source_tags:
            return {}
        try:
            with db_manager.connect(self.norm_db_path, read_only=True) as con:
                placeholders = ",".join(["?"] * len(source_tags))
                query = (
                    "SELECT source_tag, mapped_label, confidence, reasoning, model_name "  # noqa: S608
                    f"FROM tag_mappings WHERE source_tag IN ({placeholders})"
                )
                res = con.execute(query, source_tags).fetchall()
                return {
                    r[0]: {
                        "mapped_label": r[1],
                        "confidence": r[2],
                        "reasoning": r[3],
                        "model": r[4],
                    }
                    for r in res
                }
        except Exception as e:
            logger.error(f"Error fetching cached mappings: {e}")
            return {}

    def save_tag_mappings(self, mappings: list[dict]):
        """Persists new AI mappings to the NORM database cache."""
        if not mappings:
            return
        try:
            with db_manager.connect(self.norm_db_path, read_only=settings.db_read_only) as con:
                con.executemany(
                    """
                    INSERT OR REPLACE INTO tag_mappings (
                        source_tag, mapped_label, confidence, reasoning, model_name
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            m["source_tag"],
                            m["mapped_label"],
                            m.get("confidence", 0.0),
                            m.get("reasoning", ""),
                            m.get("model", "unknown"),
                        )
                        for m in mappings
                    ]
                )
        except Exception as e:
            logger.error(f"Failed to cache tag mappings: {e}")
