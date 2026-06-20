import json
from pathlib import Path

import duckdb
import pandas as pd
from loguru import logger


class DataIntegrityError(Exception):
    """データ整合性バリデーションに失敗した際に投げられる例外"""
    pass


class EdgarStorage:
    """
    SEC EDGAR 提出書類のパース結果を DuckDB に保存・管理するクラス
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            # Resolve project root and set database path
            # Now inside libs/core/src/edgar_core/storage.py
            # 5 levels up: edgar_core -> src -> core -> libs -> root
            project_root = Path(__file__).resolve().parents[4]
            self.db_path = str(project_root / "data" / "edgar" / "edgar.duckdb")
        else:
            self.db_path = db_path
            
        # データベースファイルのディレクトリ作成
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """データベースの初期化とテーブル作成"""
        with duckdb.connect(self.db_path) as conn:
            conn.execute("SET memory_limit='2GB'")
            conn.execute("SET threads=4")
            conn.execute("SET checkpoint_threshold='1GB'")

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
                CREATE TABLE IF NOT EXISTS company_facts (
                    fact_id VARCHAR PRIMARY KEY,
                    accession_number VARCHAR,
                    ticker VARCHAR,
                    concept VARCHAR,
                    label VARCHAR,
                    value DOUBLE,
                    unit VARCHAR,
                    fiscal_year INTEGER,
                    fiscal_period VARCHAR,
                    period_start DATE,
                    period_end DATE,
                    period_instant DATE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_edgar_facts_lookup "
                "ON company_facts (ticker, concept, period_end)"
            )
            logger.info(f"Initialized DuckDB at {self.db_path}")

    def _validate_filing(self, metadata: dict, sections: dict):
        """保存前に定性データの最小限の妥当性をチェック"""
        required_keys = ["accessionNumber", "ticker", "form", "filingDate"]
        missing = [k for k in required_keys if not metadata.get(k)]
        if missing:
            raise DataIntegrityError(f"Missing metadata fields: {', '.join(missing)}")

        if not sections:
            raise DataIntegrityError(f"Sections are empty for {metadata.get('accessionNumber')}")
        
        # 合計文字数が極端に少ない場合はパース失敗とみなす (例: 100文字未満)
        total_len = sum(len(content) for content in sections.values())
        if total_len < 100:
            raise DataIntegrityError(f"Sections content too sparse ({total_len} chars) for {metadata.get('accessionNumber')}")

    def _validate_facts(self, ticker: str, accession_number: str, df: pd.DataFrame):
        """保存前に定量データの最小限の妥当性をチェック"""
        if df is None or df.empty:
            raise DataIntegrityError(f"Facts DataFrame is empty for {ticker} ({accession_number})")
        
        required_cols = ["concept", "numeric_value"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise DataIntegrityError(f"Missing columns in facts DataFrame: {', '.join(missing_cols)}")

    def save_filing(self, metadata: dict, sections: dict):
        """
        メタデータとパースされたセクションを DuckDB に保存（UPSERT）
        """
        self._validate_filing(metadata, sections)

        acc_no = metadata.get("accessionNumber")
        ticker = metadata.get("ticker")

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

    def save_facts(self, ticker: str, accession_number: str, df: pd.DataFrame):
        """
        XBRLから抽出された財務数値を保存
        """
        self._validate_facts(ticker, accession_number, df)

        # カラム名の正規化と一意IDの生成
        df["ticker"] = ticker
        df["accession_number"] = accession_number
        
        # DuckDBへのインジェスト
        with duckdb.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO company_facts (
                    fact_id, accession_number, ticker, concept, label, value, unit,
                    fiscal_year, fiscal_period, period_start, period_end, period_instant
                )
                SELECT
                    md5(concat_ws('|', ticker, accession_number, concept, period_start, period_end, period_instant)) as fact_id,
                    accession_number,
                    ticker,
                    concept,
                    label,
                    CAST(numeric_value AS DOUBLE) as value,
                    unit_ref as unit,
                    CAST(fiscal_year AS INTEGER) as fiscal_year,
                    fiscal_period,
                    CAST(period_start AS DATE) as period_start,
                    CAST(period_end AS DATE) as period_end,
                    CAST(period_instant AS DATE) as period_instant
                FROM df
                WHERE numeric_value IS NOT NULL
            """)
            logger.info(f"Ingested {len(df)} financial facts for {ticker}")

    def filing_exists(self, accession_number: str) -> bool:
        """指定された受理番号の書類が既に存在するか確認"""
        with duckdb.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT COUNT(*) FROM filings WHERE accession_number = ?", (accession_number,)
            ).fetchone()
            return res[0] > 0

    def facts_exist(self, accession_number: str) -> bool:
        """指定された受理番号の財務数値（定量データ）が既に存在するか確認"""
        with duckdb.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT COUNT(*) FROM company_facts WHERE accession_number = ?", (accession_number,)
            ).fetchone()
            return res[0] > 0

    def get_accession_numbers_needing_repair(self) -> list[tuple[str, str]]:
        """定性データはあるが定量データが欠けている受理番号とティッカーのリストを取得"""
        with duckdb.connect(self.db_path) as conn:
            query = """
                SELECT f.accession_number, f.ticker 
                FROM filings f
                LEFT JOIN (SELECT DISTINCT accession_number FROM company_facts) c 
                ON f.accession_number = c.accession_number
                WHERE c.accession_number IS NULL
            """
            return conn.execute(query).fetchall()

    def get_filings_by_ticker(self, ticker: str):
        """特定のティッカーの書類一覧を取得"""
        with duckdb.connect(self.db_path) as conn:
            query = """
                SELECT ticker, form, filing_date, sections, metadata, updated_at
                FROM filings WHERE ticker = ? ORDER BY filing_date DESC
            """
            res = conn.execute(query, (ticker.upper(),)).fetchall()
            return res

    def get_stats(self):
        """保存されているデータの統計情報を取得"""
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
