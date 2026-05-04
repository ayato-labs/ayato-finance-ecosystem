import io
import zipfile

from src.batch_fetch import process_jp_ticker
from src.storage import FinancialNarrativeStorage


def test_process_jp_ticker_workflow(mocker, temp_db_path):
    """
    JP Ticker (EDINET) の一連の処理（取得・パース・保存）の結合テスト。
    モックを使用してネットワーク外部依存を排除し、内部ロジックの繋がりを確認する。
    """
    storage = FinancialNarrativeStorage(temp_db_path)

    # 1. EdinetFetcherのモック
    mock_fetcher = mocker.Mock()
    mock_fetcher.get_edinet_code.return_value = "E01234"
    mock_fetcher.list_documents.return_value = [
        {
            "docID": "S1234567",
            "edinetCode": "E01234",
            "docTypeCode": "120",
            "filingDate": "2024-05-01",
            "filerName": "Test Corp",
            "formCode": "030000",
        }
    ]

    # ダミーのZIPデータ作成
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "PublicDoc/test.htm",
            '<ix:nonNumeric name="jpcrp_cor:BusinessRisksTextBlock">'
            "リスクの内容です</ix:nonNumeric>",
        )
    mock_fetcher.download_document.return_value = buf.getvalue()

    # 2. EdinetParserのモック (または実体を使用してもよいが、ここでは実体を使用)
    from src.edinet_parser import EdinetParser

    parser = EdinetParser()

    # 3. 実行
    import asyncio

    asyncio.run(process_jp_ticker("7203", mock_fetcher, parser, storage))

    # 4. 検証
    assert storage.filing_exists("S1234567") is True
    filings = storage.get_filings_by_ticker("7203")
    assert len(filings) == 1

    import json

    sections = json.loads(filings[0][3])
    assert "リスクの内容です" in sections["risk_factors"]


def test_process_jp_ticker_no_yuho(mocker, temp_db_path):
    """有報が見つからない場合の挙動"""
    storage = FinancialNarrativeStorage(temp_db_path)
    mock_fetcher = mocker.Mock()
    mock_fetcher.get_edinet_code.return_value = "E01234"
    mock_fetcher.list_documents.return_value = []  # 何も見つからない

    from src.edinet_parser import EdinetParser

    parser = EdinetParser()

    import asyncio

    asyncio.run(process_jp_ticker("7203", mock_fetcher, parser, storage))

    assert len(storage.get_summary()) == 0
