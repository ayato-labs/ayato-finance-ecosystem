import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

class CatalogManager:
    def __init__(self, db_path: str = "./data/catalog.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the catalog database and tables using SQLite."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticker_index (
                    ticker TEXT,
                    file_path TEXT,
                    data_type TEXT,
                    PRIMARY KEY (ticker, file_path, data_type)
                ) WITHOUT ROWID
            """)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON ticker_index (ticker)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON ticker_index (data_type)")

    def register_many(self, mappings: list[tuple[str, str, str]]):
        """
        Register many ticker-file mappings in one transaction.
        Uses SQLite's robust INSERT OR IGNORE.
        """
        if not mappings:
            return

        processed_data = []
        for ticker, file_path, data_type in mappings:
            p = Path(file_path)
            if p.is_absolute():
                try:
                    rel_path = str(p.relative_to(Path.cwd())).replace("\\", "/")
                except ValueError:
                    rel_path = str(p).replace("\\", "/")
            else:
                rel_path = str(p).replace("\\", "/")
            processed_data.append((ticker, rel_path, data_type))

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executemany("""
                INSERT OR IGNORE INTO ticker_index (ticker, file_path, data_type)
                VALUES (?, ?, ?)
            """, processed_data)

    def get_paths(self, ticker: str, data_type: str = "price") -> list[str]:
        """Retrieve list of file paths containing the specific ticker."""
        with sqlite3.connect(str(self.db_path), timeout=5.0) as conn:
            res = conn.execute("""
                SELECT file_path FROM ticker_index
                WHERE ticker = ? AND data_type = ?
            """, (ticker, data_type)).fetchall()
            return [r[0] for r in res]

    def get_stats(self) -> dict:
        """Get summary statistics of the catalog."""
        with sqlite3.connect(str(self.db_path)) as conn:
            total_mappings = conn.execute(
                "SELECT COUNT(*) FROM ticker_index"
            ).fetchone()[0]
            unique_tickers = conn.execute(
                "SELECT COUNT(DISTINCT ticker) FROM ticker_index"
            ).fetchone()[0]
            unique_files = conn.execute(
                "SELECT COUNT(DISTINCT file_path) FROM ticker_index"
            ).fetchone()[0]
            return {
                "total_mappings": total_mappings,
                "unique_tickers": unique_tickers,
                "unique_files": unique_files
            }

    def clear(self):
        """Clear the catalog."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM ticker_index")

        # VACUUM must be outside a transaction
        conn = sqlite3.connect(str(self.db_path))
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.close()
