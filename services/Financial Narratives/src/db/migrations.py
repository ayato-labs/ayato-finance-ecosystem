import duckdb
from loguru import logger
from src.db.schema import TABLES, CURRENT_SCHEMA_VERSION, get_create_table_sql

class MigrationManager:
    """ DuckDBのスキーマバージョン管理と初期化を行うクラス """

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def apply_migrations(self):
        """ 必要に応じてマイグレーションを適用し、テーブルを初期化する """
        self._ensure_migration_table()
        current_v = self._get_current_version()
        
        logger.info(f"Current schema version: {current_v}, Target version: {CURRENT_SCHEMA_VERSION}")

        if current_v < 1:
            self._initialize_v1()
        
        # 将来のバージョンアップはここに elif current_v < 2: ... と追加していく

    def _ensure_migration_table(self):
        """ マイグレーション管理用テーブルが存在することを確認する """
        sql = get_create_table_sql("schema_migrations")
        self.conn.execute(sql)

    def _get_current_version(self) -> int:
        """ 現在のDBのバージョンを取得する """
        res = self.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return res[0] if res and res[0] is not None else 0

    def _initialize_v1(self):
        """ バージョン1: 初期テーブルの作成 """
        logger.info("Applying migration v1: Initial schema setup")
        
        # filings, structured_data テーブルの作成
        self.conn.execute(get_create_table_sql("filings"))
        self.conn.execute(get_create_table_sql("structured_data"))
        
        # バージョン記録
        self.conn.execute(
            "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
            [1, "Initial schema with filings and structured_data"]
        )
        logger.info("Successfully applied migration v1")
