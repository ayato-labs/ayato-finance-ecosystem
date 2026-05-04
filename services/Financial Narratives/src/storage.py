import json
from pathlib import Path

import duckdb
from loguru import logger


class FinancialNarrativeStorage:
    """
    抽出された定性情報をDuckDBに永続化するクラス
    """

    def __init__(self, db_path: str = "data/financial_narratives.duckdb"):
        self.db_path = db_path
        # データベースファイルの親ディレクトリを確実に作成
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """テーブルの初期化とリソース制限の設定"""
        with duckdb.connect(self.db_path) as conn:
            # RAM使用効率の向上のため制限を設定
            conn.execute("SET memory_limit='2GB'")
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
            logger.info(f"Initialized DuckDB at {self.db_path} with 2GB limit")

    def save_filing(self, metadata: dict, sections: dict):
        """
        メタデータとセクション情報をDuckDBにUPSERTする
        """
        # バリデーション
        required_keys = ["accessionNumber", "ticker", "form", "filingDate"]
        missing = [k for k in required_keys if not metadata.get(k)]
        if missing:
            raise ValueError(f"Missing required metadata fields: {', '.join(missing)}")

        acc_no = metadata.get("accessionNumber")
        ticker = metadata.get("ticker")

        # セクションとメタデータをJSON文字列に変換
        sections_json = json.dumps(sections)
        metadata_json = json.dumps(metadata)

        with duckdb.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO filings (
                    accession_number, ticker, cik, form, filing_date, sections, metadata, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    acc_no,
                    ticker,
                    metadata.get("cik"),
                    metadata.get("form"),
                    metadata.get("filingDate"),
                    sections_json,
                    metadata_json,
                ),
            )
            logger.success(f"Saved filing for {ticker} ({acc_no}) to DuckDB")



    def filing_exists(self, accession_number: str) -> bool:
        """
        指定された書類が既にDBに存在するか確認する
        """
        with duckdb.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT COUNT(*) FROM filings WHERE accession_number = ?", (accession_number,)
            ).fetchone()
            return res[0] > 0

    def get_summary(self):
        """保存されているデータの統計を取得"""
        with duckdb.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT ticker, form, filing_date FROM filings ORDER BY ticker, filing_date DESC"
            ).fetchall()
            return res

    def get_filings_by_ticker(self, ticker: str):
        """特定銘柄の提出書類を全て取得"""
        with duckdb.connect(self.db_path) as conn:
            query = """
                SELECT ticker, form, filing_date, sections, metadata, updated_at
                FROM filings WHERE ticker = ? ORDER BY filing_date DESC
            """
            res = conn.execute(query, (ticker.upper(),)).fetchall()
            return res



    def get_stats(self):
        """データベース全体の統計情報を取得"""
        with duckdb.connect(self.db_path) as conn:
            query = """
                SELECT ticker, COUNT(*) as count, MAX(filing_date) as latest
                FROM filings GROUP BY ticker ORDER BY count DESC
            """
            counts = conn.execute(query).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
            return {
                "total_filings": total,
                "ticker_stats": [
                    {"ticker": r[0], "count": r[1], "latest_filing": str(r[2])} for r in counts
                ],
            }
