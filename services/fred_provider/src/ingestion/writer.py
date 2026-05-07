import duckdb
from loguru import logger
import pandas as pd

class FredWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                series_id VARCHAR,
                date DATE,
                value DOUBLE,
                PRIMARY KEY (series_id, date)
            )
        """)

    def write_loop(self, data_queue):
        while True:
            data = data_queue.get()
            if data is None:
                break
            try:
                self.conn.execute("INSERT OR REPLACE INTO observations SELECT * FROM data")
                logger.debug("Successfully wrote data to DuckDB")
            except Exception as e:
                logger.error(f"Failed to write to DuckDB: {e}", extra={"error": str(e)})
            data_queue.task_done()
        self.conn.close()
        logger.info("Writer thread stopped.")
