import duckdb
from loguru import logger

class FredWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS series_metadata (
                series_id VARCHAR PRIMARY KEY,
                title VARCHAR,
                units VARCHAR,
                frequency VARCHAR,
                seasonal_adjustment VARCHAR,
                last_updated TIMESTAMP,
                notes VARCHAR
            );
            CREATE TABLE IF NOT EXISTS observations (
                series_id VARCHAR,
                date DATE,
                value DOUBLE,
                PRIMARY KEY (series_id, date),
                FOREIGN KEY (series_id) REFERENCES series_metadata(series_id)
            )
        """)

    def write_loop(self, data_queue):
        while True:
            item = data_queue.get()
            if item is None:
                break
            
            data_type, data = item
            try:
                if data_type == "metadata":
                    self.conn.execute("""
                        INSERT OR REPLACE INTO series_metadata VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data['id'], data.get('title'), data.get('units'), 
                        data.get('frequency'), data.get('seasonal_adjustment'), 
                        data.get('last_updated'), data.get('notes')
                    ))
                elif data_type == "observations":
                    self.conn.execute("INSERT OR REPLACE INTO observations SELECT * FROM data")
                logger.debug(f"Successfully wrote {data_type} to DuckDB")
            except Exception as e:
                logger.error(f"Failed to write to DuckDB: {e}", extra={"error": str(e)})
            data_queue.task_done()
        self.conn.close()
        logger.info("Writer thread stopped.")
