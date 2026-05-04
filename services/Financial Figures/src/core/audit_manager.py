import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.core.db import db_manager

logger = logging.getLogger(__name__)


class AuditManager:
    def __init__(self, db_path: Path | None = None):
        # Use provided path or default from standardized settings
        self._db_path_override = db_path
        self._lock = threading.Lock()

    @property
    def db_path(self) -> Path:
        return self._db_path_override or settings.DB_PATH_TRACEABILITY

    def _init_db(self):
        """Initialize the traceability database using centralized migration manager."""
        if settings.db_read_only:
            logger.debug("Skipping Audit DB initialization in READ_ONLY mode.")
            return

        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            from src.core.migrations import MigrationManager

            MigrationManager.apply_migrations(self.db_path, "traceability")

    def start_session(self, market: str) -> str:
        """Start a new sync session and return the ID."""
        self._init_db()
        session_id = str(uuid.uuid4())
        started_at = datetime.now()

        git_hash = "dev-local"

        with self._lock:
            with db_manager.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO sync_sessions (
                        session_id, market, status, started_at, git_commit_hash
                    )
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
            with db_manager.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE sync_sessions
                    SET status = ?, ended_at = ?, records_processed = ?,
                        errors_count = ?, error_log = ?
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
            with db_manager.connect(self.db_path) as conn:
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
            with db_manager.connect(self.db_path) as conn:
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
            with db_manager.connect(self.db_path, read_only=True) as conn:
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
            with db_manager.connect(self.db_path, read_only=True) as conn:
                placeholders = ",".join(["?"] * len(source_tags))
                query = f"SELECT source_tag FROM mapping_audit WHERE source_tag IN ({placeholders})"  # nosec S608
                res = conn.execute(query, source_tags).fetchall()
                found = set(r[0] for r in res)
                return [t for t in source_tags if t not in found]

    def get_recent_sessions(self, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve the most recent sync sessions for status reporting."""
        self._init_db()
        with self._lock:
            with db_manager.connect(self.db_path, read_only=True) as conn:
                res = conn.execute(
                    """
                    SELECT session_id, market, status, started_at FROM sync_sessions
                    ORDER BY started_at DESC LIMIT ?
                    """,
                    [limit],
                ).fetchall()

                return [
                    {"id": r[0], "market": r[1], "status": r[2], "start_time": r[3]} for r in res
                ]


# Global instance for easy use
audit_manager = AuditManager()
