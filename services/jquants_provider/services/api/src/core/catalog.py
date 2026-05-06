from datetime import datetime
from pathlib import Path

from loguru import logger

from src.core.config import settings
from src.core.db import db_manager
from src.core.schema import CATALOG_SCHEMA


class CatalogManager:
    """
    Manages the master metadata catalog for all database shards.
    """

    def __init__(self, master_db_path: Path | None = None):
        self.master_db_path = master_db_path or settings.MASTER_DB_PATH
        self._init_catalog()

    def _init_catalog(self):
        """Initialize the master catalog database and its tables."""
        self.master_db_path.parent.mkdir(parents=True, exist_ok=True)
        with db_manager.connect(self.master_db_path) as conn:
            for table_name, schema in CATALOG_SCHEMA.items():
                logger.debug(f"Ensuring catalog table: {table_name}")
                conn.execute(schema["sql"])

    def update_shard_status(
        self,
        shard_name: str,
        file_path: str | Path,
        version: int,
        status: str = "active",
        records_count: int = 0,
    ):
        """Update or register a shard's status in the catalog."""
        now = datetime.now()
        with db_manager.connect(self.master_db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO shard_catalog
                (shard_name, file_path, schema_version, last_sync_at, status,
                 records_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (shard_name, str(file_path), version, now, status, records_count, now),
            )
        logger.info(
            f"Catalog updated for shard: {shard_name} (status={status}, records={records_count})"
        )

    def get_shard_info(self, shard_name: str) -> dict | None:
        """Retrieve metadata for a specific shard."""
        with db_manager.connect(self.master_db_path) as conn:
            res = conn.execute(
                "SELECT * FROM shard_catalog WHERE shard_name = ?", (shard_name,)
            ).fetchone()
            if res:
                # DuckDB fetchone returns a tuple, we map it back to dict
                cols = [d[0] for d in conn.description]
                return dict(zip(cols, res, strict=False))
        return None

    def list_shards(self) -> list[dict]:
        """List all registered shards in the catalog."""
        with db_manager.connect(self.master_db_path) as conn:
            res = conn.execute("SELECT * FROM shard_catalog").fetchall()
            cols = [d[0] for d in conn.description]
            return [dict(zip(cols, row, strict=False)) for row in res]


catalog_manager = CatalogManager()
