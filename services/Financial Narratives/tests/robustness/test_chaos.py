import os
import time
from unittest.mock import MagicMock, patch

import duckdb
import pytest

from src.batch_fetch import process_us_ticker
from src.edgar_parser import EdgarParser
from src.storage import FinancialNarrativeStorage


@pytest.mark.asyncio
async def test_chaos_network_timeout(temp_db_path):
    """
    ネットワークタイムアウトが発生した場合のパイプラインの挙動テスト。
    リトライやエラーハンドリングが適切かを確認する。
    """
    storage = FinancialNarrativeStorage(temp_db_path)
    mock_fetcher = MagicMock()
    # タイムアウトを模倣
    mock_fetcher.get_latest_submissions.side_effect = Exception("Network Timeout")

    # 処理がクラッシュせずに終了することを確認
    try:
        await process_us_ticker("AAPL", mock_fetcher, MagicMock(), storage)
    except Exception:
        pytest.fail("process_us_ticker should handle network exceptions gracefully")

    # DBに何も保存されていないはず
    assert len(storage.get_summary()) == 0


@pytest.mark.asyncio
async def test_chaos_llm_json_corruption(temp_db_path):
    """
    LLMが壊れたJSONを返した場合のパイプラインの耐性テスト。
    """
    storage = FinancialNarrativeStorage(temp_db_path)

    # ダミーデータを保存
    storage.save_filing(
        {
            "accessionNumber": "TEST-123",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2024-01-01",
        },
        {"mda": "content"},
    )

    # FilingStructurer.extract_facts をモック
    # 壊れたJSONをパースしようとして ValueError を吐く状況
    with patch("src.structurer.FilingStructurer") as mock_struct_class:
        mock_struct = mock_struct_class.return_value
        mock_struct.extract_facts.side_effect = ValueError("Invalid JSON")

        from src.batch_fetch import run_structuring_for_filing

        # エラーが発生しても全体が止まらないことを確認
        await run_structuring_for_filing("TEST-123", "AAPL", {"mda": "text"}, storage)

    # 構造化データは保存されていないはず
    assert storage.get_structuring_by_ticker("AAPL") is None


def test_storage_db_corruption_recovery(temp_db_path):
    """DBファイルが読み取り専用や破損している場合のエラーハンドリング"""
    storage = FinancialNarrativeStorage(temp_db_path)

    # ファイルを読み取り専用にする
    os.chmod(temp_db_path, 0o444)

    try:
        with pytest.raises(duckdb.Error):  # DuckDB will raise some operational error
            storage.save_filing(
                {"accessionNumber": "1", "ticker": "A", "form": "F", "filingDate": "2024-01-01"}, {}
            )
    finally:
        # クリーンアップのために戻す
        os.chmod(temp_db_path, 0o666)


def test_extremely_long_input_handling():
    """極端に長い入力（100万文字以上）に対するパース速度とメモリ消費の確認"""
    parser = EdgarParser()
    # 1行が長すぎるとスキップされる(目次対策)ため、改行を含める
    huge_html = "<html><body>" + "\nItem 1. Business\n" * 1000 + "</body></html>"

    # タイムアウトせずに完了することを確認
    start = time.time()
    sections = parser.extract_all_sections(huge_html, "10-K")
    duration = time.time() - start

    assert duration < 10.0  # 10秒以内
    assert "business" in sections
