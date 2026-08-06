import hashlib
import json
import os
from pathlib import Path

import duckdb
import pandas as pd
from loguru import logger


class DataIntegrityError(Exception):
    """データ整合性バリデーション（空チェック、文字数チェック等）に失敗した際に投げられる例外"""

    pass


class EdgarStorage:
    """
    SEC EDGAR 提出書類のパース結果を DuckDB に保存・管理するストレージ層クラス。
    3テーブルに正規化されたリレーショナルデータベース構造を管理します。
    """

    def __init__(self, db_path: str | None = None):
        """
        EdgarStorageの初期化。
        環境変数 'EDGAR_DATA_DIR' が存在する場合はそこから優先的にパスを解決し、
        ない場合はデフォルトの共有ディレクトリ（finance/data/edgar/edgar.duckdb）を参照します。
        """
        if db_path is None:
            # プロジェクトルートディレクトリ（finance/）を取得し、データベースの既定パスを設定
            # __file__ は src/storage.py にあるため、parents[3] は finance/ ディレクトリになります
            _finance_root = Path(__file__).resolve().parents[3]
            _default_path = _finance_root / "data" / "edgar" / "edgar.duckdb"
            self.db_path = os.environ.get("EDGAR_DATA_DIR", str(_default_path))
        else:
            self.db_path = db_path

        # データベースを配置する親ディレクトリが存在しない場合は自動作成
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """
        データベースの初期化、Schema-as-Code に基づくスキーマファイルの自動出力、
        およびテーブル・インデックスの作成を実行します。
        """
        from .db_schema import generate_schema_files

        # データベースと同じディレクトリに SQL 定義ファイルおよび設計書 markdown を自動生成出力
        generate_schema_files(Path(self.db_path).parent)

        with duckdb.connect(self.db_path) as conn:
            # DuckDB の接続最適化オプション（メモリ制限、マルチスレッド並列処理等）を設定
            # 環境変数から設定値を読み込み、デフォルト値を使用
            memory_limit = os.getenv("DUCKDB_MEMORY_LIMIT", "2GB")
            threads = int(os.getenv("DUCKDB_THREADS", "4"))
            checkpoint_threshold = os.getenv("DUCKDB_CHECKPOINT_THRESHOLD", "1GB")

            conn.execute(f"SET memory_limit='{memory_limit}'")
            conn.execute(f"SET threads={threads}")
            conn.execute(f"SET checkpoint_threshold='{checkpoint_threshold}'")

            # 1. filings テーブル（書類の基本メタデータ）の定義
            conn.execute("""
                CREATE TABLE IF NOT EXISTS filings (
                    accession_number VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    cik VARCHAR,
                    form VARCHAR,
                    filing_date DATE,
                    metadata JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. filing_sections テーブル（定性テキスト本文のセクション分割保存用）の定義
            conn.execute("""
                CREATE TABLE IF NOT EXISTS filing_sections (
                    section_id VARCHAR PRIMARY KEY,
                    accession_number VARCHAR,
                    section_name VARCHAR,
                    content_md VARCHAR,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. company_facts テーブル（抽出された定量数値データ）の定義
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

            # 財務データの照会速度向上のための複合インデックスの作成
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_edgar_facts_lookup
                ON company_facts (ticker, concept, period_end)
            """)

            # 受付番号とセクション名での検索を高速化するための複合インデックスの作成
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_edgar_sections_lookup
                ON filing_sections (accession_number, section_name)
            """)
            logger.info(f"Initialized DuckDB at {self.db_path}")

    def _validate_filing(self, metadata: dict, sections: dict):
        """
        保存処理を実行する前に、受け取ったメタデータおよび定性テキストセクションの最小限の整合性検証を行います。
        必須項目の欠損やテキストが極端に少ない場合は、パース失敗として例外を投げます。
        """
        required_keys = ["accessionNumber", "ticker", "form", "filingDate"]
        missing = [k for k in required_keys if not metadata.get(k)]
        if missing:
            raise DataIntegrityError(f"Missing metadata fields: {', '.join(missing)}")

        if not sections:
            raise DataIntegrityError(f"Sections are empty for {metadata.get('accessionNumber')}")

        # 各セクションの合計文字数が極端に少ない場合は、ダウンロード・パース異常とみなして検証エラー
        total_len = sum(len(content) for content in sections.values())
        if total_len < 100:
            raise DataIntegrityError(
                f"Sections content too sparse ({total_len} chars) for {metadata.get('accessionNumber')}"
            )

    def _validate_facts(self, ticker: str, accession_number: str, df: pd.DataFrame):
        """保存処理を実行する前に、定量データ DataFrame の妥当性チェックを行います。"""
        if df is None or df.empty:
            raise DataIntegrityError(f"Facts DataFrame is empty for {ticker} ({accession_number})")

        required_cols = ["concept", "numeric_value"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise DataIntegrityError(
                f"Missing columns in facts DataFrame: {', '.join(missing_cols)}"
            )

    def _insert_single_filing(self, conn: duckdb.DuckDBPyConnection, metadata: dict, sections: dict):
        """単一の提出書類（メタデータおよび各セクション本文）を DB に保存します。"""
        self._validate_filing(metadata, sections)

        acc_no = metadata.get("accessionNumber")
        ticker = metadata.get("ticker")
        metadata_json = json.dumps(metadata)

        conn.execute(
            """
            INSERT OR REPLACE INTO filings (
                accession_number, ticker, cik, form, filing_date, metadata, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                acc_no,
                ticker,
                metadata.get("cik"),
                metadata.get("form"),
                metadata.get("filingDate"),
                metadata_json,
            ),
        )

        for section_name, content in sections.items():
            if not content:
                continue
            # 受付番号と章名から一意なプライマリキー MD5 ハッシュ値を生成（非暗号用途）
            section_id = hashlib.md5(f"{acc_no}|{section_name}".encode(), usedforsecurity=False).hexdigest()
            conn.execute(
                """
                INSERT OR REPLACE INTO filing_sections (
                    section_id, accession_number, section_name, content_md, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (section_id, acc_no, section_name, content),
            )

    def save_filing(self, metadata: dict, sections: dict):
        """
        パースされた定性情報をデータベースの「filings」と「filing_sections」に分割保存（UPSERT）します。
        """
        with duckdb.connect(self.db_path) as conn:
            self._insert_single_filing(conn, metadata, sections)
            ticker = metadata.get("ticker")
            acc_no = metadata.get("accessionNumber")
            logger.success(f"Saved filing and sections for {ticker} ({acc_no}) to DuckDB")

    def save_facts(self, ticker: str, accession_number: str, df: pd.DataFrame):
        """
        XBRLデータから抽出された企業の財務数値データ（定量Facts）を保存します。
        """
        self._validate_facts(ticker, accession_number, df)

        # 結合識別用の一時カラム追加
        df["ticker"] = ticker
        df["accession_number"] = accession_number

        with duckdb.connect(self.db_path) as conn:
            # 各数値データ項目に対し、一意のハッシュキー（MD5）を生成して登録
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
                    unit as unit,
                    CAST(fiscal_year AS INTEGER) as fiscal_year,
                    fiscal_period,
                    CAST(period_start AS DATE) as period_start,
                    CAST(period_end AS DATE) as period_end,
                    CAST(period_instant AS DATE) as period_instant
                FROM df
                WHERE numeric_value IS NOT NULL
            """)
            logger.info(f"Ingested {len(df)} financial facts for {ticker}")

    def save_filings_batch(self, filings_data: list[tuple[dict, dict]]) -> int:
        """
        複数の提出書類を一括で保存します。

        Args:
            filings_data: (metadata, sections) のタプルのリスト

        Returns:
            保存に成功した件数
        """
        if not filings_data:
            return 0

        saved_count = 0
        total = len(filings_data)
        progress_interval = max(1, total // 10)  # 10%ごとに進捗ログ

        with duckdb.connect(self.db_path) as conn:
            for i, (metadata, sections) in enumerate(filings_data, 1):
                try:
                    self._insert_single_filing(conn, metadata, sections)
                    saved_count += 1

                    if i % progress_interval == 0 or i == total:
                        logger.info(f"Saving filings progress | {i}/{total} ({i*100//total}%)")

                except DataIntegrityError as e:
                    logger.warning(f"Skipping filing due to validation error: {e}")
                except Exception as e:
                    logger.error(f"Error saving filing {metadata.get('accessionNumber')}: {e}")

        logger.info(f"Batch saved {saved_count}/{total} filings")
        return saved_count

    def save_facts_batch(self, facts_data: list[tuple[str, str, pd.DataFrame]]) -> int:
        """
        複数のファクトを一括で保存します。

        Args:
            facts_data: (ticker, accession_number, facts_df) のタプルのリスト

        Returns:
            保存に成功した件数
        """
        if not facts_data:
            return 0

        saved_count = 0
        total = len(facts_data)
        progress_interval = max(1, total // 10)  # 10%ごとに進捗ログ

        with duckdb.connect(self.db_path) as conn:
            for i, (ticker, accession_number, df) in enumerate(facts_data, 1):
                try:
                    self._validate_facts(ticker, accession_number, df)

                    # 結合識別用の一時カラム追加
                    df["ticker"] = ticker
                    df["accession_number"] = accession_number

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
                            unit as unit,
                            CAST(fiscal_year AS INTEGER) as fiscal_year,
                            fiscal_period,
                            CAST(period_start AS DATE) as period_start,
                            CAST(period_end AS DATE) as period_end,
                            CAST(period_instant AS DATE) as period_instant
                        FROM df
                        WHERE numeric_value IS NOT NULL
                    """)
                    saved_count += 1

                    # 進捗ログ（10%ごと）
                    if i % progress_interval == 0 or i == total:
                        logger.info(f"Saving facts progress | {i}/{total} ({i*100//total}%)")

                except DataIntegrityError as e:
                    logger.warning(f"Skipping facts due to validation error: {e}")
                except Exception as e:
                    logger.error(f"Error saving facts for {ticker} ({accession_number}): {e}")

        logger.info(f"Batch saved facts for {saved_count}/{total} filings")
        return saved_count

    def filing_exists(self, accession_number: str) -> bool:
        """指定された受付番号の書類メタデータが、すでにデータベースに登録されているか確認します。"""
        with duckdb.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT COUNT(*) FROM filings WHERE accession_number = ?", (accession_number,)
            ).fetchone()
            return res[0] > 0

    def facts_exist(self, accession_number: str) -> bool:
        """指定された受付番号に対応する財務数値（定量データ）が、すでに登録されているか確認します。"""
        with duckdb.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT COUNT(*) FROM company_facts WHERE accession_number = ?", (accession_number,)
            ).fetchone()
            return res[0] > 0

    def get_accession_numbers_needing_repair(self) -> list[tuple[str, str]]:
        """
        スマートリペア機能（データ不完全性の修復）用メソッド。
        定性テキストは保存されているが、対応する定量Facts数値が欠落している受付番号の一覧を返します。
        """
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
        """
        特定のティッカーの書類一覧を取得します。
        後方互換性を保つため、内部で filing_sections テーブルと JOIN し、
        旧スキーマと同じように sections（JSONオブジェクト）型をシミュレート構成して結果を返します。
        """
        with duckdb.connect(self.db_path) as conn:
            query = """
                SELECT f.ticker, f.form, f.filing_date,
                       (
                           SELECT json_group_object(s.section_name, s.content_md)
                           FROM filing_sections s
                           WHERE s.accession_number = f.accession_number
                       ) as sections,
                       f.metadata, f.updated_at
                FROM filings f WHERE f.ticker = ? ORDER BY f.filing_date DESC
            """
            res = conn.execute(query, (ticker.upper(),)).fetchall()
            return res

    def get_stats(self):
        """保存されている全データの統計情報（総書類数、銘柄ごとの書類取得数など）を取得します。"""
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
