from loguru import logger

from src.core.config import settings
from src.core.db import db_manager
from src.core.generated_schema import TABLE_SCHEMAS


class MasterDBManager:
    """Manages the control plane database for routing and metadata."""

    def __init__(self):
        self.master_db_path = settings.MASTER_DB_PATH
        self.master_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_master_schema()

    def _init_master_schema(self):
        """Initializes the schema for the master DB (databases and data_catalog)."""
        logger.info(f"Initializing Master DB at {self.master_db_path}")
        with db_manager.connect(self.master_db_path) as conn:
            # We use the DDL generated from contracts for 'databases' and 'data_catalog'
            for table in ["databases", "data_catalog"]:
                if table in TABLE_SCHEMAS:
                    conn.execute(TABLE_SCHEMAS[table]["v1"])

    def register_shard(self, db_id: str, file_path: str, role: str, schema_version: str):
        """Registers a new database shard in the master DB."""
        with db_manager.connect(self.master_db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO databases (db_id, file_path, role, schema_version, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                [db_id, file_path, role, schema_version],
            )
        logger.info(f"Registered shard {db_id} at {file_path} (role: {role})")

    def register_partition(self, partition_key: str, db_id: str, description: str = None):
        """Maps a partition (e.g. 'AAPL_2024') to a database shard."""
        with db_manager.connect(self.master_db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO data_catalog (partition_key, db_id, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                [partition_key, db_id, description],
            )
        logger.info(f"Mapped partition {partition_key} to shard {db_id}")

    def get_shard_path(self, db_id: str) -> str | None:
        """Retrieves the file path for a given shard ID."""
        with db_manager.connect(self.master_db_path) as conn:
            res = conn.execute(
                "SELECT file_path FROM databases WHERE db_id = ?", [db_id]
            ).fetchone()
            return res[0] if res else None

    def get_connection_with_attachments(self, read_only: bool = False):
        """Returns a DuckDB connection with all registered shards ATTACHED."""
        conn = None
        # Use direct connect for master first
        import duckdb

        conn = duckdb.connect(str(self.master_db_path), read_only=read_only)

        # Get all shards
        shards = conn.execute("SELECT db_id, file_path FROM databases").fetchall()
        for db_id, file_path in shards:
            try:
                # Use db_id as alias
                conn.execute(f"ATTACH '{file_path}' AS {db_id}")
                logger.debug(f"Attached shard {db_id} from {file_path}")
            except Exception as e:
                logger.warning(f"Could not attach shard {db_id}: {e}")

        return conn


# Singleton instance
master_db = MasterDBManager()
