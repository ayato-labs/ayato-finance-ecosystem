import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from src.batch_fetch import batch_fetch
from src.storage import FinancialNarrativeStorage

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "system_test.duckdb"
    return str(db_file)

@pytest.mark.asyncio
async def test_batch_fetch_full_system_run(temp_db):
    """
    システム全体のフルランテスト。
    外部I/Oはすべてモックするが、DBへの永続化と構造化タスクのフローを確認する。
    """
    tickers = ["AAPL", "7203"]
    
    # Mock EdgarFetcher & EdinetFetcher
    with patch("src.batch_fetch.EdgarFetcher") as mock_edgar_cls, \
         patch("src.batch_fetch.EdinetFetcher") as mock_edinet_cls, \
         patch("src.batch_fetch.FinancialNarrativeStorage") as mock_storage_cls, \
         patch("src.batch_fetch.run_structuring_for_filing", new_callable=AsyncMock) as mock_struct:
        
        # Configure mocks
        mock_edgar = mock_edgar_cls.return_value
        mock_edinet = mock_edinet_cls.return_value
        
        # US mock returns
        mock_edgar.get_latest_submissions.return_value = {"filings": {"recent": {}}}
        mock_edgar.filter_relevant_filings.return_value = [
            {"accessionNumber": "US-ACC-1", "filingDate": "2026-05-01", "primaryDocument": "doc.htm", "form": "10-Q"}
        ]
        mock_edgar.get_cik.return_value = "0000320193"
        
        # JP mock returns (for process_jp_ticker)
        mock_edinet.get_edinet_code.return_value = "E02144"
        mock_edinet.list_documents.return_value = [
            {"docID": "JP-DOC-1", "docTypeCode": "120", "filingDate": "2026-05-01", "filerName": "Toyota"}
        ]
        mock_edinet.download_document.return_value = b"fake-zip-content"
        
        # Storage mock should allow checking exists
        mock_storage = MagicMock()
        mock_storage.filing_exists.return_value = False
        mock_storage_cls.return_value = mock_storage
        
        # Execute
        await batch_fetch(tickers=tickers, run_structuring=True, days=7)
        
        # Verify
        # US and JP processing should have been called
        assert mock_edgar.get_latest_submissions.called
        assert mock_edinet.get_edinet_code.called
        
        # Storage should have saved twice (one for each ticker)
        assert mock_storage.save_filing.call_count == 2
        
        # Structuring should have been triggered twice
        assert mock_struct.call_count == 2
