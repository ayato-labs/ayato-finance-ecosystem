"""Unit tests for EdgarStorage class."""

import tempfile
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from src.storage import DataIntegrityError, EdgarStorage


class TestEdgarStorage:
    """EdgarStorage クラスのユニットテスト。"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ。"""
        # 一時的なディレクトリにテスト用DBを作成
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test.duckdb")
        self.storage = EdgarStorage(db_path=self.db_path)

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ。"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_creates_database(self):
        """データベース作成のテスト。"""
        assert Path(self.db_path).exists()

    def test_init_creates_tables(self):
        """テーブル作成のテスト。"""
        with duckdb.connect(self.db_path) as conn:
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert "filings" in table_names
            assert "filing_sections" in table_names
            assert "company_facts" in table_names

    def test_validate_filing_success(self):
        """メタデータバリデーション成功テスト。"""
        metadata = {
            "accessionNumber": "0001234567-26-000001",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2026-01-01",
        }
        sections = {"business": "Business content here." * 10}
        # 例外が発生しなければ成功
        self.storage._validate_filing(metadata, sections)

    def test_validate_filing_missing_fields(self):
        """必須フィールド欠落時のバリデーションエラーテスト。"""
        metadata = {"accessionNumber": "0001234567-26-000001"}
        sections = {"business": "Content"}

        with pytest.raises(DataIntegrityError) as excinfo:
            self.storage._validate_filing(metadata, sections)
        assert "Missing metadata fields" in str(excinfo.value)

    def test_validate_filing_empty_sections(self):
        """空セクション時のバリデーションエラーテスト。"""
        metadata = {
            "accessionNumber": "0001234567-26-000001",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2026-01-01",
        }
        sections = {}

        with pytest.raises(DataIntegrityError) as excinfo:
            self.storage._validate_filing(metadata, sections)
        assert "Sections are empty" in str(excinfo.value)

    def test_validate_filing_sparse_content(self):
        """内容が薄すぎる場合のバリデーションエラーテスト。"""
        metadata = {
            "accessionNumber": "0001234567-26-000001",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2026-01-01",
        }
        sections = {"business": "Short"}

        with pytest.raises(DataIntegrityError) as excinfo:
            self.storage._validate_filing(metadata, sections)
        assert "too sparse" in str(excinfo.value)

    def test_validate_facts_success(self):
        """ファクトDataFrameバリデーション成功テスト。"""
        df = pd.DataFrame(
            {
                "concept": ["Revenue", "NetIncome"],
                "numeric_value": [1000000, 200000],
            }
        )
        # 例外が発生しなければ成功
        self.storage._validate_facts("AAPL", "0001234567-26-000001", df)

    def test_validate_facts_empty_dataframe(self):
        """空DataFrame時のバリデーションエラーテスト。"""
        df = pd.DataFrame()

        with pytest.raises(DataIntegrityError) as excinfo:
            self.storage._validate_facts("AAPL", "0001234567-26-000001", df)
        assert "empty" in str(excinfo.value)

    def test_validate_facts_none_dataframe(self):
        """None DataFrame時のバリデーションエラーテスト。"""
        with pytest.raises(DataIntegrityError) as excinfo:
            self.storage._validate_facts("AAPL", "0001234567-26-000001", None)
        assert "empty" in str(excinfo.value)

    def test_validate_facts_missing_columns(self):
        """必須カラム欠落時のバリデーションエラーテスト。"""
        df = pd.DataFrame({"wrong_column": [1, 2, 3]})

        with pytest.raises(DataIntegrityError) as excinfo:
            self.storage._validate_facts("AAPL", "0001234567-26-000001", df)
        assert "Missing columns" in str(excinfo.value)

    def test_save_filing(self):
        """提出書類保存のテスト。"""
        metadata = {
            "accessionNumber": "0001234567-26-000001",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2026-01-01",
            "cik": "0000320193",
        }
        sections = {
            "business": "Apple Inc. designs, manufactures, and markets smartphones." * 5,
            "risk_factors": "The company faces various risks including market competition." * 5,
        }

        self.storage.save_filing(metadata, sections)

        # 保存されたことを確認
        assert self.storage.filing_exists("0001234567-26-000001")

    def test_filing_exists(self):
        """提出書類存在チェックのテスト。"""
        # 存在しない場合
        assert not self.storage.filing_exists("nonexistent")

        # 保存後に存在する場合
        metadata = {
            "accessionNumber": "0001234567-26-000002",
            "ticker": "MSFT",
            "form": "10-Q",
            "filingDate": "2026-03-01",
        }
        sections = {"mda": "Management discussion and analysis content." * 10}
        self.storage.save_filing(metadata, sections)

        assert self.storage.filing_exists("0001234567-26-000002")

    def test_facts_exist(self):
        """ファクト存在チェックのテスト。"""
        # 存在しない場合
        assert not self.storage.facts_exist("nonexistent")

        # ファクトを保存
        metadata = {
            "accessionNumber": "0001234567-26-000003",
            "ticker": "GOOGL",
            "form": "10-K",
            "filingDate": "2026-01-01",
        }
        sections = {"business": "Alphabet Inc. business description." * 10}
        self.storage.save_filing(metadata, sections)

        facts_df = pd.DataFrame(
            {
                "concept": ["Revenue", "NetIncome"],
                "label": ["Revenue", "Net Income"],
                "numeric_value": [300000000, 50000000],
                "unit": ["USD", "USD"],
                "fiscal_year": [2025, 2025],
                "fiscal_period": ["FY", "FY"],
                "period_start": ["2025-01-01", "2025-01-01"],
                "period_end": ["2025-12-31", "2025-12-31"],
                "period_instant": [None, None],
            }
        )
        self.storage.save_facts("GOOGL", "0001234567-26-000003", facts_df)

        assert self.storage.facts_exist("0001234567-26-000003")

    def test_get_stats(self):
        """統計情報取得のテスト。"""
        # データを保存
        for i in range(3):
            metadata = {
                "accessionNumber": f"0001234567-26-0000{i+10}",
                "ticker": "TEST",
                "form": "10-K",
                "filingDate": f"2026-0{i+1}-01",
            }
            sections = {"business": f"Business content for filing {i}." * 10}
            self.storage.save_filing(metadata, sections)

        stats = self.storage.get_stats()
        assert stats["total_filings"] == 3
        assert len(stats["ticker_stats"]) == 1
        assert stats["ticker_stats"][0]["ticker"] == "TEST"
        assert stats["ticker_stats"][0]["count"] == 3

    def test_get_filings_by_ticker(self):
        """ティッカー別提出書類取得のテスト。"""
        # データを保存
        metadata = {
            "accessionNumber": "0001234567-26-000020",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2026-01-01",
        }
        sections = {"business": "Apple business content." * 10}
        self.storage.save_filing(metadata, sections)

        result = self.storage.get_filings_by_ticker("AAPL")
        assert len(result) == 1
        assert result[0][0] == "AAPL"  # ticker

    def test_get_accession_numbers_needing_repair(self):
        """修復が必要な受付番号取得のテスト。"""
        # メタデータのみ保存（ファクトなし）
        metadata = {
            "accessionNumber": "0001234567-26-000030",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2026-01-01",
        }
        sections = {"business": "Business content." * 10}
        self.storage.save_filing(metadata, sections)

        targets = self.storage.get_accession_numbers_needing_repair()
        assert len(targets) == 1
        assert targets[0][0] == "0001234567-26-000030"
        assert targets[0][1] == "AAPL"

    def test_save_filings_batch(self):
        """提出書類バッチ保存のテスト。"""
        filings_data = [
            (
                {
                    "accessionNumber": "0001234567-26-000040",
                    "ticker": "AAPL",
                    "form": "10-K",
                    "filingDate": "2026-01-01",
                    "cik": "0000320193",
                },
                {"business": "Apple Inc. business content." * 10},
            ),
            (
                {
                    "accessionNumber": "0001234567-26-000041",
                    "ticker": "MSFT",
                    "form": "10-Q",
                    "filingDate": "2026-03-01",
                    "cik": "0000789019",
                },
                {"mda": "Microsoft management discussion." * 10},
            ),
        ]

        saved_count = self.storage.save_filings_batch(filings_data)
        assert saved_count == 2
        assert self.storage.filing_exists("0001234567-26-000040")
        assert self.storage.filing_exists("0001234567-26-000041")

    def test_save_filings_batch_empty(self):
        """空のバッチ保存のテスト。"""
        saved_count = self.storage.save_filings_batch([])
        assert saved_count == 0

    def test_save_facts_batch(self):
        """ファクトバッチ保存のテスト。"""
        # まずメタデータを保存
        metadata = {
            "accessionNumber": "0001234567-26-000050",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2026-01-01",
        }
        sections = {"business": "Apple business content." * 10}
        self.storage.save_filing(metadata, sections)

        facts_data = [
            (
                "AAPL",
                "0001234567-26-000050",
                pd.DataFrame(
                    {
                        "concept": ["Revenue", "NetIncome"],
                        "label": ["Revenue", "Net Income"],
                        "numeric_value": [400000000, 100000000],
                        "unit": ["USD", "USD"],
                        "fiscal_year": [2025, 2025],
                        "fiscal_period": ["FY", "FY"],
                        "period_start": ["2025-01-01", "2025-01-01"],
                        "period_end": ["2025-12-31", "2025-12-31"],
                        "period_instant": [None, None],
                    }
                ),
            ),
        ]

        saved_count = self.storage.save_facts_batch(facts_data)
        assert saved_count == 1
        assert self.storage.facts_exist("0001234567-26-000050")

    def test_save_facts_batch_empty(self):
        """空のファクトバッチ保存のテスト。"""
        saved_count = self.storage.save_facts_batch([])
        assert saved_count == 0

    def test_save_filings_batch_with_invalid_data(self):
        """無効なデータを含むバッチ保存のテスト。"""
        filings_data = [
            (
                {
                    "accessionNumber": "0001234567-26-000060",
                    "ticker": "AAPL",
                    "form": "10-K",
                    "filingDate": "2026-01-01",
                },
                {"business": "Valid content." * 10},
            ),
            (
                {
                    "accessionNumber": "0001234567-26-000061",
                    # ticker が欠落している
                    "form": "10-K",
                    "filingDate": "2026-01-01",
                },
                {"business": "Invalid content." * 10},
            ),
        ]

        # 無効なデータはスキップされ、有効なデータのみ保存される
        saved_count = self.storage.save_filings_batch(filings_data)
        assert saved_count == 1
        assert self.storage.filing_exists("0001234567-26-000060")

    def test_save_facts_does_not_mutate_input_df(self):
        """save_facts が呼び出し元の DataFrame を破壊的に変更しないことを検証。"""
        metadata = {
            "accessionNumber": "0001234567-26-000070",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2026-01-01",
        }
        sections = {"business": "Apple business content." * 10}
        self.storage.save_filing(metadata, sections)

        facts_df = pd.DataFrame(
            {
                "concept": ["Revenue"],
                "label": ["Revenue"],
                "numeric_value": [1000.0],
                "unit": ["USD"],
                "fiscal_year": [2025],
                "fiscal_period": ["FY"],
                "period_start": ["2025-01-01"],
                "period_end": ["2025-12-31"],
                "period_instant": [None],
            }
        )

        original_cols = list(facts_df.columns)
        self.storage.save_facts("AAPL", "0001234567-26-000070", facts_df)
        assert list(facts_df.columns) == original_cols
        assert "ticker" not in facts_df.columns
        assert "accession_number" not in facts_df.columns

    def test_filing_and_facts_exists_batch(self):
        """一括存在チェックメソッドのテスト。"""
        metadata = {
            "accessionNumber": "0001234567-26-000080",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2026-01-01",
        }
        sections = {"business": "Business content." * 10}
        self.storage.save_filing(metadata, sections)

        facts_df = pd.DataFrame(
            {
                "concept": ["Revenue"],
                "label": ["Revenue"],
                "numeric_value": [100.0],
                "unit": ["USD"],
                "fiscal_year": [2025],
                "fiscal_period": ["FY"],
                "period_start": ["2025-01-01"],
                "period_end": ["2025-12-31"],
                "period_instant": [None],
            }
        )
        self.storage.save_facts("AAPL", "0001234567-26-000080", facts_df)

        existing_filings = self.storage.filing_exists_batch(["0001234567-26-000080", "nonexistent"])
        assert existing_filings == {"0001234567-26-000080"}

        existing_facts = self.storage.facts_exist_batch(["0001234567-26-000080", "nonexistent"])
        assert existing_facts == {"0001234567-26-000080"}

        assert self.storage.filing_exists_batch([]) == set()
        assert self.storage.facts_exist_batch([]) == set()

    def test_checkpoint_and_vacuum(self):
        """checkpoint および vacuum メソッドの実行テスト。"""
        # 例外が発生せずに正常終了することを検証
        self.storage.checkpoint()
        self.storage.vacuum()

    def test_migrate_db_schema(self):
        """旧スキーマからのマイグレーション動作テスト。"""
        old_db_path = str(Path(self.temp_dir) / "old.duckdb")
        with duckdb.connect(old_db_path) as conn:
            # metadata カラムがない旧 filings テーブルを作成
            conn.execute("""
                CREATE TABLE filings (
                    accession_number VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    cik VARCHAR,
                    form VARCHAR,
                    filing_date DATE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        # EdgarStorage で初期化を行うことで自動マイグレーションが走る
        old_storage = EdgarStorage(db_path=old_db_path)
        with duckdb.connect(old_db_path) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info('filings')").fetchall()}
            assert "metadata" in cols



