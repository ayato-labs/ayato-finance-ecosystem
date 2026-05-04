
import pytest


@pytest.fixture
def temp_db_path(tmp_path):
    """テスト用の一時DuckDBパスを生成"""
    db_file = tmp_path / "test_finance.duckdb"
    return str(db_file)


@pytest.fixture
def sample_html():
    """パーステスト用の最小限のHTMLサンプル"""
    return """
    <html>
        <body>
            <div id="item1">Item 1. Business</div>
            <p>This is the business section content.</p>
            <div id="item1a">Item 1A. Risk Factors</div>
            <p>This is the risk factors content.</p>
            <div id="item7">Item 7. Management's Discussion and Analysis</div>
            <p>This is the MD&A content.</p>
        </body>
    </html>
    """


@pytest.fixture
def mock_filing_metadata():
    """テスト用のファイリングメタデータ"""
    return {
        "accessionNumber": "0001234567-24-000001",
        "ticker": "TEST",
        "cik": "0001234567",
        "form": "10-K",
        "filingDate": "2024-04-27",
        "primaryDocument": "test.htm",
    }
