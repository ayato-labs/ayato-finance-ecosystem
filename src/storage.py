import json
import os
import time
from pathlib import Path

import duckdb
from loguru import logger

from src.config import DEFAULT_DB_PATH, DUCKDB_MEMORY_LIMIT, JP_DB_PATH, US_DB_PATH
from src.db.migrations import MigrationManager


class CrossProcessLock:
    """
    Windows環境等でDuckDBのマルチプロセス競合（already open）を防ぐための
    シンプルなファイルベースのロック機構。
    """
    def __init__(self, db_path: str, timeout: int = 60):
        self.lock_path = f"{db_path}.lock"
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                # O_CREAT | O_EXCL はアトミックな作成を保証する
                self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except (FileExistsError, OSError):
                if time.time() - start_time > self.timeout:
                    # タイムアウト時に既存のロックファイルが古い（5分以上前）なら強制削除を試みる
                    if os.path.exists(self.lock_path):
                        mtime = os.path.getmtime(self.lock_path)
                        if time.time() - mtime > 300:
                            try:
                                os.remove(self.lock_path)
                                continue
                            except: pass
                    raise TimeoutError(f"Could not acquire lock on {self.lock_path} after {self.timeout}s")
                time.sleep(0.5)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None:
            try:
                os.close(self.fd)
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
            except:
                pass


class FinancialNarrativeStorage:
    """
    抽出された定性情報をDuckDBに永続化するクラス
    """

    def __init__(self, db_path: str | None = None, market: str | None = None):
        if db_path:
            self.db_path = db_path
        elif market:
            if market.lower() == "jp":
                self.db_path = JP_DB_PATH
            elif market.lower() == "us":
                self.db_path = US_DB_PATH
            else:
                self.db_path = DEFAULT_DB_PATH
        else:
            self.db_path = DEFAULT_DB_PATH

        # データベースファイルの親ディレクトリを確実に作成
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """テーブルの初期化とリソース制限の設定"""
        with CrossProcessLock(self.db_path):
            with duckdb.connect(self.db_path) as conn:
                # RAM使用効率の向上のため制限を設定
                conn.execute(f"SET memory_limit='{DUCKDB_MEMORY_LIMIT}'")
                conn.execute("SET threads=4")

                # 並列書き込み時のパフォーマンスと整合性のための設定
                conn.execute("SET checkpoint_threshold='1GB'")

                # マイグレーションマネージャーを使用して初期化
                manager = MigrationManager(conn)
                manager.apply_migrations()

                logger.info(f"Initialized DuckDB at {self.db_path} with {DUCKDB_MEMORY_LIMIT} limit")

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

        with CrossProcessLock(self.db_path):
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

    def save_structuring(self, accession_number: str, ticker: str, structured_facts: dict):
        """
        AIによって構造化された事実情報を保存する
        """
        facts_json = json.dumps(structured_facts)
        with CrossProcessLock(self.db_path):
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
