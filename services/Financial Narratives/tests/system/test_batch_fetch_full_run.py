from unittest.mock import AsyncMock, patch

import pytest

from src.batch_fetch import batch_fetch


@pytest.fixture
def mock_dependencies():
    with patch("src.batch_fetch.EdgarFetcher") as mock_edgar_cls, patch(
        "src.batch_fetch.EdinetFetcher"
    ) as mock_edinet_cls, patch(
        "src.batch_fetch.FinancialNarrativeStorage"
    ) as mock_storage_cls, patch(
        "src.batch_fetch.run_structuring_for_filing", new_callable=AsyncMock
    ) as mock_struct:
        yield {
            "edgar": mock_edgar_cls.return_value,
            "edinet": mock_edinet_cls.return_value,
            "storage": mock_storage_cls.return_value,
            "struct": mock_struct,
            "storage_cls": mock_storage_cls,
        }


@pytest.mark.asyncio
async def test_batch_fetch_tickers_flow(mock_dependencies):
    """
    【総合テスト】指定したティッカー（日米混在）に対して、
    データの取得から構造化のトリガーまで一貫して実行されることを確認。
    """
    tickers = ["AAPL", "7203"]
    deps = mock_dependencies

    # US mock returns
    deps["edgar"].get_latest_submissions.return_value = {"filings": {"recent": {}}}
    deps["edgar"].filter_relevant_filings.return_value = [
        {
            "accessionNumber": "US-ACC-1",
            "filingDate": "2026-05-01",
            "primaryDocument": "doc.htm",
            "form": "10-Q",
        }
    ]
    deps["edgar"].get_cik.return_value = "0000320193"

    # JP mock returns
    deps["edinet"].get_edinet_code.return_value = "E02144"
    deps["edinet"].list_documents.return_value = [
        {
            "docID": "JP-DOC-1",
            "docTypeCode": "120",
            "filingDate": "2026-05-01",
            "filerName": "Toyota",
        }
    ]
    deps["edinet"].download_document.return_value = b"fake-zip-content"

    deps["storage"].filing_exists.return_value = False

    # Execute
    await batch_fetch(tickers=tickers, run_structuring=True, days=7)

    # Verify
    assert deps["edgar"].get_latest_submissions.called
    assert deps["edinet"].get_edinet_code.called

    # Storage should have saved twice
    assert deps["storage"].save_filing.call_count == 2

    # Structuring should have been triggered twice
    assert deps["struct"].call_count == 2
