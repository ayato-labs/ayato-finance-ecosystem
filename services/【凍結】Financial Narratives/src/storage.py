import json
import os
import random
import re
import time
from pathlib import Path

import duckdb
import zstandard as zstd
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
                                logger.warning(f"Removed stale lock file: {self.lock_path}")
                                continue
                            except Exception as e:
                                logger.warning(f"Failed to remove stale lock file: {e}")
                    raise TimeoutError(
                        f"Could not acquire lock on {self.lock_path} after {self.timeout}s"
                    )
                time.sleep(0.5)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None:
            try:
                os.close(self.fd)
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
            except Exception as e:
                logger.warning(f"Error during lock release: {e}")


class FinancialNarrativeStorage:
    """
    抽出された定性情報をDuckDBに永続化するクラス
    """

    def __init__(self, db_path: str | None = None, market: str | None = None):
        if db_path:
            self.db_path = db_path
        elif market:
            market_l = market.lower()
            if market_l == "jp":
                self.db_path = JP_DB_PATH
            elif market_l == "us":
                self.db_path = US_DB_PATH
            else:
                self.db_path = DEFAULT_DB_PATH
        else:
            self.db_path = DEFAULT_DB_PATH

        # データベースファイルの親ディレクトリを確実に作成
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self, read_only: bool = False):
        """Windows環境でのファイルロック競合を回避しながらDuckDBに接続する"""
        for attempt in range(15):  # 並列度が高いので試行回数を多めに設定
            try:
                return duckdb.connect(self.db_path, read_only=read_only)
            except Exception as e:
                err_str = str(e).lower()
                # Windows特有のロックエラーやIOエラーを捕捉
                lock_msgs = [
                    "cannot open file",
                    "already open",
                    "lock",
                    "io error",
                    "process cannot access",
                ]
                if any(msg in err_str for msg in lock_msgs):
                    wait_time = (2**attempt) * 0.1 + random.uniform(0, 0.5)
                    if attempt > 3:
                        logger.warning(
                            f"DB {self.db_path} locked (read_only={read_only}), "
                            f"retrying in {wait_time:.2f}s... ({attempt + 1}/15)"
                        )
                    time.sleep(wait_time)
                    continue
                raise e
        raise RuntimeError(f"Failed to connect to DuckDB after maximum retries: {self.db_path}")

    def _init_db(self):
        """テーブルの初期化とリソース制限の設定"""
        with self._connect(read_only=False) as conn:
            # RAM使用効率の向上のため制限を設定
            conn.execute(f"SET memory_limit='{DUCKDB_MEMORY_LIMIT}'")
            conn.execute("SET threads=4")
            conn.execute("SET checkpoint_threshold='1GB'")

            manager = MigrationManager(conn)
            manager.apply_migrations()
            logger.info(f"Initialized DuckDB at {self.db_path} with {DUCKDB_MEMORY_LIMIT} limit")

    def save_filing(self, metadata: dict, sections: dict):
        """メタデータとセクション情報をDuckDBにUPSERTする"""
        required_keys = ["accessionNumber", "ticker", "form", "filingDate"]
        missing = [k for k in required_keys if not metadata.get(k)]
        if missing:
            raise ValueError(f"Missing required metadata fields: {', '.join(missing)}")

        acc_no = metadata.get("accessionNumber")
        ticker = metadata.get("ticker")

        # 保存前のテキストクレンジング（定型文の削除）
        # 金融開示特有の長い免責事項などを正規表現で除去（ストレージ節約）
        boilerplate_patterns = [
            r"本資料に含まれる将来の予想に関する記述は.*?(?=。|$)",
            r"Forward-looking statements involve risks and uncertainties.*?(?=\.|$)",
            r"実際の業績等は様々な要因により大きく異なる可能性があります.*?(?=。|$)",
        ]

        cleaned_sections = {}
        for k, v in sections.items():
            if isinstance(v, str):
                text = v
                for pattern in boilerplate_patterns:
                    text = re.sub(pattern, "", text, flags=re.DOTALL)
                cleaned_sections[k] = text
            else:
                cleaned_sections[k] = v

        # 金融ドキュメント用ヒント辞書（圧縮率向上のため）
        financial_dict_raw = (
            "当連結会計年度 経営成績 財政状態 キャッシュ・フロー 設備投資 研究開発 従業員 "
            "ガバナンス 有価証券報告書 四半期 役員報酬 政策保有株式 投資計画 事業等のリスク "
            "経営方針 Item Business Risk Factors Management's Discussion and Analysis "
            "Financial Statements Executive Compensation Corporate Governance Common Stock "
            "Operations Revenue Net Income"
        )
        financial_dict = financial_dict_raw.encode("utf-8")

        # テキストデータの高圧縮 (zstd level 9 + 辞書ヒント)
        sections_json = json.dumps(cleaned_sections).encode("utf-8")

        # 辞書を使用して圧縮
        zdict = zstd.ZstdCompressionDict(financial_dict)
        cctx = zstd.ZstdCompressor(level=9, dict_data=zdict)
        compressed_sections = cctx.compress(sections_json)

        metadata_json = json.dumps(metadata)

        with self._connect(read_only=False) as conn:
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
                    compressed_sections,
                    metadata_json,
                ),
            )
        logger.success(f"Saved filing for {ticker} ({acc_no}) to DuckDB (Compressed)")

    def save_structuring_batch(self, batch_data: list[tuple[str, str, dict]]):
        """AIによって構造化された複数の事実情報を一括保存する"""
        if not batch_data:
            return

        with self._connect(read_only=False) as conn:
            # executemany を使って一括挿入
            records = [
                (acc_no, ticker.upper(), json.dumps(facts)) for acc_no, ticker, facts in batch_data
            ]
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO structured_data (
                        accession_number, ticker, structured_facts, updated_at
                    ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    records,
                )
                conn.execute("COMMIT")
            except Exception as e:
                conn.execute("ROLLBACK")
                raise e
            logger.success(f"Bulk saved {len(batch_data)} structured facts to DuckDB")

    def get_structuring_by_ticker(self, ticker: str):
        """特定銘柄の構造化事実を取得"""
        with self._connect(read_only=True) as conn:
            query = """
                SELECT structured_facts, updated_at
                FROM structured_data WHERE ticker = ? ORDER BY updated_at DESC
            """
            res = conn.execute(query, (ticker.upper(),)).fetchone()
            if res:
                return json.loads(res[0])
            return None

    def get_sections(self, acc_no: str) -> dict:
        """指定された受付番号のセクション情報を取得する（解凍対応）"""
        with self._connect(read_only=True) as conn:
            res = conn.execute(
                "SELECT sections FROM filings WHERE accession_number = ?", (acc_no,)
            ).fetchone()
            if not res:
                return {}

            raw_data = res[0]
            if not raw_data:
                return {}

            # DuckDBからBLOBが文字列（エスケープ表現）として返ってくるケースへの対応
            if isinstance(raw_data, str):
                if raw_data.startswith("{"):
                    # 平文JSONの場合
                    try:
                        return json.loads(raw_data)
                    except Exception:
                        return {}
                else:
                    # 圧縮バイナリが文字列（バックスラッシュ・エスケープ等）として化けている場合
                    try:
                        # 1. 直接的なunicode_escape試行
                        # もし '( \x...' のような形式なら、エスケープを解除
                        if raw_data.startswith("(\\x") or raw_data.startswith("\\x"):
                             import ast
                             # literal_eval で bytes リテラルとして解釈を試みる
                             # 例: "b'\x01\x02'" -> b'\x01\x02'
                             # 先頭の '(' と末尾の ')' を除去し、b'' で囲む
                             clean_raw = raw_data.strip("()")
                             if not clean_raw.startswith("b'"):
                                 clean_raw = f"b'{clean_raw}'"
                             raw_data = ast.literal_eval(clean_raw)
                        else:
                            raw_data = raw_data.encode("latin-1")
                    except Exception as e:
                        logger.warning(f"Failed to re-encode potential binary string: {e}")

            if isinstance(raw_data, (bytes, bytearray)):
                # 圧縮されている場合は解凍
                try:
                    # 共通辞書を使用して解凍を試行
                    dict_data_raw = (
                        "当連結会計年度 経営成績 財政状態 キャッシュ・フロー 設備投資 研究開発 "
                        "従業員 ガバナンス 有価証券報告書 四半期 役員報酬 政策保有株式 "
                        "投資計画 事業等のリスク 経営方針 Item Business Risk Factors "
                        "Management's Discussion and Analysis Financial Statements "
                        "Executive Compensation Corporate Governance Common Stock "
                        "Operations Revenue Net Income"
                    )
                    dict_data = dict_data_raw.encode("utf-8")
                    zdict = zstd.ZstdCompressionDict(dict_data)
                    dctx = zstd.ZstdDecompressor(dict_data=zdict)
                    decompressed = dctx.decompress(raw_data)
                    return json.loads(decompressed.decode("utf-8"))
                except Exception as e:
                    logger.debug(f"Zstd dictionary decompression failed, trying without dict: {e}")
                    try:
                        dctx = zstd.ZstdDecompressor()
                        decompressed = dctx.decompress(raw_data)
                        return json.loads(decompressed.decode("utf-8"))
                    except Exception as e2:
                        logger.error(f"Critical decompression failure for {acc_no}: {e2}")

                        try:
                            return json.loads(raw_data.decode("utf-8"))
                        except Exception:
                            return {}
            elif isinstance(raw_data, str):
                # プレーンな文字列（JSON）の場合
                try:
                    return json.loads(raw_data)
                except Exception:
                    return {}

            return {}

    def filing_exists(self, accession_number: str) -> bool:
        with self._connect(read_only=True) as conn:
            res = conn.execute(
                "SELECT 1 FROM filings WHERE accession_number = ?", (accession_number,)
            ).fetchone()
            return res is not None
        """指定された書類が既にDBに存在するか確認する"""
        with self._connect(read_only=True) as conn:
            res = conn.execute(
                "SELECT COUNT(*) FROM filings WHERE accession_number = ?", (accession_number,)
            ).fetchone()
            return res[0] > 0

    def get_summary(self):
        """保存されているデータの統計を取得"""
        with self._connect(read_only=True) as conn:
            res = conn.execute(
                "SELECT ticker, form, filing_date FROM filings ORDER BY ticker, filing_date DESC"
            ).fetchall()
            return res

    def get_filings_by_ticker(self, ticker: str):
        """特定銘柄の提出書類を全て取得"""
        with self._connect(read_only=True) as conn:
            query = """
                SELECT ticker, form, filing_date, sections, metadata, updated_at
                FROM filings WHERE ticker = ? ORDER BY filing_date DESC
            """
            res = conn.execute(query, (ticker.upper(),)).fetchall()
            return res

    def get_stats(self):
        """データベース全体の統計情報を取得"""
        with self._connect(read_only=True) as conn:
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
