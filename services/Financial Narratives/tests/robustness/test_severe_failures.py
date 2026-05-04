import pytest
import concurrent.futures
from src.storage import FinancialNarrativeStorage
from src.structurer import FilingStructurer

def test_concurrent_db_writes(temp_db_path):
    """
    複数スレッドからの同時書き込みテスト。
    DuckDBの接続管理とロックが適切に処理されるかを確認する。
    """
    storage = FinancialNarrativeStorage(temp_db_path)
    
    def write_task(i):
        metadata = {
            "accessionNumber": f"ACC-{i}",
            "ticker": "AAPL",
            "form": "10-K",
            "filingDate": "2024-01-01"
        }
        storage.save_filing(metadata, {"content": f"data-{i}"})
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(write_task, i) for i in range(50)]
        results = [f.result() for f in futures]
    
    assert all(results)
    assert storage.get_stats()["total_filings"] == 50

@pytest.mark.asyncio
async def test_llm_json_garbage_recovery():
    """
    LLMがJSONの前後に余計なテキストを含めた場合の耐性テスト。
    リファクタリングにより、markdownコードブロック内から抽出できるはず。
    """
    structurer = FilingStructurer(api_key="dummy")
    garbage_json = (
        "Here is the result: ```json\n"
        "{\"capex\": {\"intent\": \"recovered\"}, \"rd\": null, \"governance\": null}\n"
        "``` hope this helps!"
    )
    
    result = structurer._parse_response(garbage_json)
    assert result["capex"]["intent"] == "recovered"

def test_storage_sql_injection_attempt(temp_db_path):
    """SQLインジェクションのような文字列に対する耐性テスト"""
    storage = FinancialNarrativeStorage(temp_db_path)
    malicious_ticker = "AAPL'; DROP TABLE filings; --"
    metadata = {
        "accessionNumber": "ACC-MALICIOUS",
        "ticker": malicious_ticker,
        "form": "10-K",
        "filingDate": "2024-01-01"
    }
    # パラメータ化クエリを使用していれば安全
    storage.save_filing(metadata, {"mda": "safe"})
    
    # テーブルが削除されていないことを確認
    assert storage.filing_exists("ACC-MALICIOUS")
    assert storage.get_stats()["total_filings"] > 0
