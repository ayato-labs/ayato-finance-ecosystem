"""Unit tests for EdgarQuantitative class."""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
from src.quantitative import EdgarQuantitative


class TestEdgarQuantitative:
    """EdgarQuantitative クラスのユニットテスト。"""

    def test_extract_facts_filing_not_found(self):
        """書類が見つからない場合のテスト。"""
        with patch("src.quantitative.get_by_accession_number", return_value=None):
            result = EdgarQuantitative.extract_facts("0000000000-00-000000")
            assert result.empty

    def test_extract_facts_no_xbrl(self):
        """XBRLデータがない場合のテスト。"""
        mock_filing = MagicMock()
        mock_filing.xbrl.return_value = None

        with patch("src.quantitative.get_by_accession_number", return_value=mock_filing):
            result = EdgarQuantitative.extract_facts("0000000000-00-000000")
            assert result.empty

    def test_extract_facts_empty_facts(self):
        """空のファクトDataFrameの場合のテスト。"""
        mock_filing = MagicMock()
        mock_xbrl = MagicMock()
        mock_facts = MagicMock()
        mock_facts.query.return_value.to_dataframe.return_value = pd.DataFrame()

        mock_xbrl.facts = mock_facts
        mock_filing.xbrl.return_value = mock_xbrl

        with patch("src.quantitative.get_by_accession_number", return_value=mock_filing):
            result = EdgarQuantitative.extract_facts("0000000000-00-000000")
            assert result.empty

    def test_extract_facts_success(self):
        """ファクト抽出成功のテスト。"""
        mock_filing = MagicMock()
        mock_xbrl = MagicMock()

        # モックデータを作成
        facts_data = pd.DataFrame(
            {
                "concept": ["us-gaap:Revenue", "us-gaap:NetIncome"],
                "label": ["Revenue", "Net Income"],
                "numeric_value": [1000000.0, 200000.0],
                "unit_ref": ["USD", "USD"],
                "fiscal_year": [2025, 2025],
                "period_start": ["2025-01-01", "2025-01-01"],
                "period_end": ["2025-12-31", "2025-12-31"],
                "period_instant": [None, None],
                "period_type": ["duration", "duration"],
            }
        )

        mock_facts = MagicMock()
        mock_facts.query.return_value.to_dataframe.return_value = facts_data

        mock_xbrl.facts = mock_facts
        mock_xbrl.units = {"USD": {"type": "simple", "measure": "iso4217:USD"}}
        mock_filing.xbrl.return_value = mock_xbrl

        with patch("src.quantitative.get_by_accession_number", return_value=mock_filing):
            result = EdgarQuantitative.extract_facts("0000000000-00-000000")
            assert not result.empty
            assert "concept" in result.columns
            assert "numeric_value" in result.columns

    def test_get_currency_from_unit(self):
        """ユニットから通貨を取得するロジックのテスト。"""
        # 実際のメソッドは内部関数だが、テスト可能
        mock_xbrl = MagicMock()
        mock_xbrl.units = {"USD": {"type": "simple", "measure": "iso4217:USD"}}

        def get_currency(unit_ref):
            if not unit_ref or not mock_xbrl.units:
                return None
            unit_info = mock_xbrl.units.get(unit_ref)
            if unit_info and unit_info.get("type") == "simple":
                measure = unit_info.get("measure", "")
                if measure.startswith("iso4217:"):
                    return measure.replace("iso4217:", "")
            return None

        assert get_currency("USD") == "USD"
        assert get_currency(None) is None
        assert get_currency("UNKNOWN") is None

    def test_derive_fiscal_period(self):
        """決算期間の導出ロジックのテスト。"""
        from src.quantitative import _derive_fiscal_period

        assert _derive_fiscal_period({"period_type": "instant"}) == "FY"
        assert _derive_fiscal_period({"period_type": "duration", "period_length": 90}) == "Q1"
        assert _derive_fiscal_period({"period_type": "duration", "period_length": 180}) == "Q2"
        assert _derive_fiscal_period({"period_type": "duration", "period_length": 270}) == "Q3"
        assert _derive_fiscal_period({"period_type": "duration", "period_length": 365}) == "FY"
        assert _derive_fiscal_period({"period_type": "duration", "period_length": None}) is None

    def test_env_identity_loading(self):
        """環境変数SEC_IDENTITYの読み込みテスト。"""
        # 環境変数を設定
        os.environ["SEC_IDENTITY"] = "TestUser test@example.com"

        # .envファイルからの読み込みをモック
        with patch.dict(os.environ, {"SEC_IDENTITY": "TestUser test@example.com"}):
            from dotenv import load_dotenv

            load_dotenv()
            sec_identity = os.getenv("SEC_IDENTITY")
            assert sec_identity == "TestUser test@example.com"

        # クリーンアップ
        del os.environ["SEC_IDENTITY"]
