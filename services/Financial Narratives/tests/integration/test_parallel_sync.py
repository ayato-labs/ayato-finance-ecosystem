import pytest
import asyncio
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from src.storage import FinancialNarrativeStorage


@pytest.mark.asyncio
async def test_parallel_market_sync_execution(tmp_path):
    """日米の市場が並列で処理されているかを擬似的に検証"""
    db_path = str(tmp_path / "parallel.duckdb")
    storage = FinancialNarrativeStorage(db_path)

    # テスト対象のモジュールをリロードせずにパッチを当てるために、
    # 関数のローカルスコープでパッチを当てる
    with (
        patch("src.batch_fetch.EdinetFetcher") as MockEdinetFetcher,
        patch("src.batch_fetch.EdgarFetcher") as MockEdgarFetcher,
        patch("src.batch_fetch.EdinetParser") as MockEdinetParser,
        patch("src.batch_fetch.EdgarParser") as MockEdgarParser,
        patch("src.batch_fetch.FinancialNarrativeStorage") as MockStorageClass,
        patch("src.batch_fetch.SEC_TICKERS", ["AAPL"]),
        patch("src.batch_fetch.asyncio.sleep", return_value=None),
    ):
        # ストレージのインスタンスを固定
        MockStorageClass.return_value = storage

        # EDINET 側のモック
        edinet_instance = MockEdinetFetcher.return_value
        edinet_instance.list_documents.return_value = [
            {
                "docID": "JP1",
                "secCode": "7203",
                "docTypeCode": "120",
                "formCode": "120",
                "edinetCode": "E00001",
                "filingDate": date.today().isoformat(),
                "filerName": "TOYOTA",
            }
        ]
        edinet_instance.download_document.return_value = b"zip_content"
        MockEdinetParser.return_value.parse_zip.return_value = {"mda": "JP content"}

        # EDGAR 側のモック
        edgar_instance = MockEdgarFetcher.return_value
        edgar_instance.get_all_tickers.return_value = ["AAPL"]
        edgar_instance.get_latest_submissions.return_value = {"dummy": "data"}
        edgar_instance.filter_relevant_filings.return_value = [
            {
                "accessionNumber": "US1",
                "filingDate": date.today().isoformat(),
                "form": "10-K",
                "primaryDocument": "doc.html",
            }
        ]
        edgar_instance.get_cik.return_value = "320193"
        MockEdgarParser.return_value.extract_all_sections.return_value = {"mda": "US content"}

        # ネットワークリクエストのモック (USのダウンロード用)
        with patch("src.batch_fetch.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.content = b"html_content"

            # ここでインポートすることでパッチを確実に反映させる
            from src.batch_fetch import batch_fetch

            # batch_fetchを実行 (1日分)
            await batch_fetch(days=1)

            # 1. 両方のFetcherが呼ばれたことを確認
            assert edinet_instance.list_documents.called
            assert edgar_instance.get_latest_submissions.called

            # 2. ストレージに両方のデータが保存されたことを確認
            assert storage.filing_exists("JP1")
            assert storage.filing_exists("US1")
