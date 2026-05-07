import duckdb
from loguru import logger


class FredWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        try:
            self.conn = duckdb.connect(db_path)
            logger.debug(f"Connected to DuckDB at {db_path}")
            self._init_db()
        except Exception:
            logger.exception(f"Failed to connect to DuckDB at {db_path}")
            raise

    def _init_db(self):
        """データベースの初期化とスキーマ構築"""
        try:
            logger.debug("Initializing database schema...")
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
            logger.debug("Database schema initialized successfully.")
        except Exception:
            logger.exception("Failed to initialize database schema")
            raise

    def write_loop(self, data_queue):
        """キューからデータを読み取り、DBに書き込むメインループ"""
        logger.info("Writer thread started.")
        while True:
            item = data_queue.get()
            if item is None:
                logger.debug("Sentinel received. Closing writer thread.")
                break

            data_type, data = item
            try:
                if data_type == "metadata":
                    logger.debug(f"Writing metadata for series: {data.get('id')}")
                    self.conn.execute(
                        """
                        INSERT OR REPLACE INTO series_metadata VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            data["id"],
                            data.get("title"),
                            data.get("units"),
                            data.get("frequency"),
                            data.get("seasonal_adjustment"),
                            data.get("last_updated"),
                            data.get("notes"),
                        ),
                    )
                elif data_type == "observations":
                    logger.debug(f"Writing observations for series: {data['series_id'].iloc[0]}")
                    # Ensure column order matches schema: series_id, date, value
                    df_to_write = data[["series_id", "date", "value"]]
                    self.conn.execute("INSERT OR REPLACE INTO observations SELECT * FROM df_to_write")

                logger.info(f"Successfully wrote {data_type} to DuckDB.")
            except Exception:
                logger.exception(f"Error writing {data_type} to DuckDB")
                # Do not pass - the exception is logged with full traceback
            finally:
                data_queue.task_done()

        try:
            self.conn.close()
            logger.info("DuckDB connection closed. Writer thread stopped.")
        except Exception:
            logger.exception("Error while closing DuckDB connection")
