from datetime import date

from dotenv import load_dotenv

from src.edinet_fetcher import EdinetFetcher

# Load .env for EDINET_API_KEY
load_dotenv()


def test_edinet_fetcher_init():
    fetcher = EdinetFetcher()
    assert fetcher.api_key is not None


def test_edinet_fetcher_get_edinet_code():
    fetcher = EdinetFetcher()
    # 7203 is Toyota
    code = fetcher.get_edinet_code("7203")
    assert code == "E02144"


def test_edinet_fetcher_list_documents_real_api():
    """
    Real API call test for list_documents.
    Requirement: Do NOT mock API calls in Unit Tests.
    """
    fetcher = EdinetFetcher()
    # Use a known date
    target_date = date(2026, 5, 1)
    docs = fetcher.list_documents(target_date)

    assert isinstance(docs, list)
    # On 2026-05-01 (Friday), there should be documents.
    assert len(docs) > 0
    assert "docID" in docs[0]


def test_edinet_fetcher_download_document_real_api():
    """
    Real API call test for download_document.
    """
    fetcher = EdinetFetcher()
    # A known DocID from 2026-05-01 (e.g., S100Y1TB)
    doc_id = "S100Y1TB"
    content = fetcher.download_document(doc_id)

    assert content is not None
    assert len(content) > 0
    # ZIP magic bytes
    assert content.startswith(b"PK")


def test_edinet_fetcher_invalid_key():
    """バグやエラーを引き起こす厳しいテスト"""
    fetcher = EdinetFetcher(api_key="INVALID_KEY_12345")
    target_date = date(2026, 5, 1)
    docs = fetcher.list_documents(target_date)
    # Invalid key should result in empty list (due to our error handling logging but returning [])
    assert docs == []
