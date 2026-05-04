import json
from pathlib import Path

import duckdb
from loguru import logger
from src.config import DEFAULT_DB_PATH, DUCKDB_MEMORY_LIMIT


class FinancialNarrativeStorage:
    """
    抽出された定性情報をDuckDBに永続化するクラス
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        # データベースファイルの親ディレクトリを確実に作成
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """テーブルの初期化とリソース制限の設定"""
        with duckdb.connect(self.db_path) as conn:
            # RAM使用効率の向上のため制限を設定
            conn.execute(f"SET memory_limit='{DUCKDB_MEMORY_LIMIT}'")
            conn.execute("SET threads=4")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS filings (
                    accession_number VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    cik VARCHAR,
                    form VARCHAR,
                    filing_date DATE,
                    sections JSON,
                    metadata JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS structured_data (
                    accession_number VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    structured_facts JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info(f"Initialized DuckDB at {self.db_path} with {DUCKDB_MEMORY_LIMIT} limit")

    def save_filing(self, metadata: dict, sections: dict):
        """
        パースされた開示情報を保存する
        """
        acc_no = metadata.get("accessionNumber")
        ticker = metadata.get("ticker", "UNKNOWN").upper()
        cik = metadata.get("cik")
        form = metadata.get("form")
        filing_date = metadata.get("filingDate")
        
        sections_json = json.dumps(sections)
        metadata_json = json.dumps(metadata)

        with duckdb.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO filings (
                    accession_number, ticker, cik, form, filing_date, sections, metadata, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (acc_no, ticker, cik, form, filing_date, sections_json, metadata_json),
            )
            logger.success(f"Saved filing for {ticker} ({acc_no}) to DuckDB")

    def save_structuring(self, accession_number: str, ticker: str, structured_facts: dict):
        """
        AIによって構造化された事実情報を保存する
        """
        facts_json = json.dumps(structured_facts)
        with duckdb.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO structured_data (
                    accession_number, ticker, structured_facts, updated_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (accession_number, ticker.upper(), facts_json),
            )
            logger.success(f"Saved structured facts for {ticker} ({accession_number})")

    def get_structuring_by_ticker(self, ticker: str):
        """特定銘柄の構造化事実を取得"""
        with duckdb.connect(self.db_path) as conn:
            query = """
                SELECT structured_facts, updated_at
                FROM structured_data WHERE ticker = ? ORDER BY updated_at DESC
            """
            res = conn.execute(query, (ticker.upper(),)).fetchone()
            if res:
                return json.loads(res[0])
            return None

    def filing_exists(self, accession_number: str) -> bool:
        """指定された受付番号のデータが既に存在するか確認"""
        with duckdb.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT 1 FROM filings WHERE accession_number = ?", (accession_number,)
            ).fetchone()
            return res is not None

    def get_filings_by_ticker(self, ticker: str):
        """特定銘柄の全書類を取得"""
        with duckdb.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT * FROM filings WHERE ticker = ? ORDER BY filing_date DESC",
                (ticker.upper(),),
            ).fetchall()

    def get_summary(self):
        """各銘柄の取得済み件数を集計"""
        with duckdb.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT ticker, COUNT(*) as count FROM filings GROUP BY ticker"
            ).fetchall()
