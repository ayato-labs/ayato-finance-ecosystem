import logging
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from src.core.config import settings

logger = logging.getLogger(__name__)


class AuditManager:
    def __init__(self, db_path: Path | None = None):
        # Use provided path or default from standardized settings (lazy evaluation suggested)
        self._db_path_override = db_path
        self._lock = threading.Lock()

    def _get_conn(self):
        """Resilient connection helper for Windows file locks with Exponential Backoff."""
        max_retries = 10
        base_delay = 0.1  # 100ms

        # Avoid potential circular imports or overhead by importing random here
        import random

        for i in range(max_retries):
            try:
                # Use a shared lock hint if possible (DuckDB doesn't have a direct 'shared' mode
                # for connect, but read_only=True helps on some OSs)
                conn = duckdb.connect(str(self.db_path), read_only=settings.db_read_only)
                if i > 0:
                    logger.info(f"Database connection re-established after {i} retries.")
                return conn
            except Exception as e:
                err_str = str(e).lower()
                is_lock_err = any(
                    kw in err_str for kw in ["io error", "locked", "permission", "used by another"]
                )

                if is_lock_err and i < max_retries - 1:
                    # Exponential backoff with jitter: (2^i * base_delay) + random jitter
                    delay = (base_delay * (2**i)) + (random.random() * 0.1)
                    logger.warning(
                        f"Database lock detected (attempt {i + 1}/{max_retries}). "
                        f"Retrying in {delay:.2f}s... Error: {err_str[:100]}"
                    )
                    time.sleep(delay)
                    continue

                if not is_lock_err:
                    logger.error(f"Fatal database attachment error: {e}", exc_info=True)
                raise e

        # Last resort attempt
        return duckdb.connect(str(self.db_path), read_only=settings.db_read_only)

    @property
    def db_path(self) -> Path:
        return self._db_path_override or settings.DB_PATH_TRACEABILITY

    def _init_db(self):
        """Initialize the traceability database in a thread-safe manner."""
        if settings.db_read_only:
            logger.debug("Skipping Audit DB initialization in READ_ONLY mode.")
            return

        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_conn() as conn:
                # Table for Sync Sessions (Process Level)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sync_sessions (
                        session_id VARCHAR PRIMARY KEY,
                        market VARCHAR,
                        status VARCHAR,
                        started_at TIMESTAMP,
                        ended_at TIMESTAMP,
                        records_processed INTEGER,
                        errors_count INTEGER,
                        error_log VARCHAR,
                        git_commit_hash VARCHAR
                    )
                """)

                # Table for AI Mapping Audits (Logic Level)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mapping_audit (
                        mapping_id VARCHAR PRIMARY KEY,
                        session_id VARCHAR,
                        source_tag VARCHAR,
                        mapped_label VARCHAR,
                        reasoning VARCHAR,
                        confidence_score DOUBLE,
                        mapped_at TIMESTAMP,
                        llm_model_version VARCHAR
                    )
                """)

                # Table for Last Sync States (Delta Level)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sync_progress (
                        market VARCHAR,
                        symbol VARCHAR,
                        last_synced_at TIMESTAMP,
                        records_in_last_sync INTEGER,
                        status VARCHAR,
                        PRIMARY KEY(market, symbol)
                    )
                """)

    def start_session(self, market: str) -> str:
        """Start a new sync session and return the ID."""
        self._init_db()
        session_id = str(uuid.uuid4())
        started_at = datetime.now()

        git_hash = "dev-local"

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO sync_sessions (session_id, market, status, started_at, git_commit_hash)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    [session_id, market, "RUNNING", started_at, git_hash],
                )

        logger.info(f"Starting new sync session for market '{market}': {session_id}")
        return session_id

    def end_session(
        self, session_id: str, status: str, processed: int, errors: int, log: str | None = None
    ):
        """Close a sync session with final stats."""
        self._init_db()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE sync_sessions 
                    SET status = ?, ended_at = ?, records_processed = ?, errors_count = ?, error_log = ?
                    WHERE session_id = ?
                """,
                    [status, datetime.now(), processed, errors, log, session_id],
                )
        logger.info(
            f"Session {session_id} ended with status '{status}'. "
            f"Processed: {processed}, Errors: {errors}"
        )

    def log_mapping(
        self,
        session_id: str,
        source_tag: str,
        mapped_label: str,
        reasoning: str,
        confidence: float = 1.0,
        model: str = "default",
    ):
        """Log an AI mapping decision."""
        self._init_db()
        mapping_id = str(uuid.uuid4())
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO mapping_audit (
                        mapping_id, session_id, source_tag, mapped_label, 
                        reasoning, confidence_score, mapped_at, llm_model_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        mapping_id,
                        session_id,
                        source_tag,
                        mapped_label,
                        reasoning,
                        confidence,
                        datetime.now(),
                        model,
                    ],
                )

    def log_ticker_sync(self, market: str, symbol: str, record_count: int, status: str = "SUCCESS"):
        """Update the last sync state for a specific ticker."""
        self._init_db()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sync_progress (
                        market, symbol, last_synced_at, records_in_last_sync, status
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    [market, symbol, datetime.now(), record_count, status],
                )

    def get_synced_symbols(self, market: str, days: int = 7) -> list[str]:
        """Fetch symbols that have been synced recently."""
        self._init_db()
        with self._lock:
            with self._get_conn() as conn:
                res = conn.execute(
                    """
                    SELECT symbol FROM sync_progress 
                    WHERE market = ? AND last_synced_at >= (CURRENT_TIMESTAMP - INTERVAL 1 DAY * ?)
                    AND status IN ('SUCCESS', 'SKIPPED_NOT_FOUND')
                    """,
                    [market, days],
                ).fetchall()
                return [r[0] for r in res]

    def get_unmapped_tags(self, market: str, source_tags: list[str]) -> list[str]:
        """Given a list of tags (with market prefix), return those that don't have a mapping yet."""
        if not source_tags:
            return []
        self._init_db()
        with self._lock:
            with self._get_conn() as conn:
                placeholders = ",".join(["?"] * len(source_tags))
                res = conn.execute(
                    f"SELECT source_tag FROM mapping_audit WHERE source_tag IN ({placeholders})",
                    source_tags,
                ).fetchall()
                found = set(r[0] for r in res)
                return [t for t in source_tags if t not in found]

    def get_recent_sessions(self, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve the most recent sync sessions for status reporting."""
        self._init_db()
        with self._lock:
            with self._get_conn() as conn:
                res = conn.execute(
                    """
                    SELECT * FROM sync_sessions ORDER BY started_at DESC LIMIT ?
                    """,
                    [limit],
                ).fetchall()
                return res


# Global instance for easy use
audit_manager = AuditManager()
