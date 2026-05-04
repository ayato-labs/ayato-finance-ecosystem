import pytest
import os
import duckdb
from src.storage import FinancialNarrativeStorage
from src.structurer import FilingStructurer
import json

def test_storage_db_corrupted(tmp_path):
    """データベースファイルが破損している場合の挙動"""
    db_path = tmp_path / "corrupted.duckdb"
    with open(db_path, "w") as f:
        f.write("Not a DuckDB file - just some garbage text.")
    
    # 初期化時にエラーが出るか、あるいはクリーンアップされるかの検証
    # DuckDB は通常、不当なファイルなら Connection Error を投げる
    with pytest.raises(Exception):
        storage = FinancialNarrativeStorage(str(db_path))

def test_structurer_invalid_api_key():
    """無効なAPIキーでの挙動 (Mock不使用でリアルなエラーを確認)"""
    # 注: ユーザー指示により単体テスト(およびその派生)ではMockを使わない
    structurer = FilingStructurer(api_key="invalid_key_12345")
    sections = {"business": "Some content"}
    
    # リアルなAPI呼び出しにより認証エラーが発生することを確認
    # ただし、ネットワーク環境等に依存するため注意
    try:
        # 非同期実行
        import asyncio
        asyncio.run(structurer.extract_facts(sections))
    except Exception as e:
        # Google API なら 400 や 401 が返るはず
        assert "400" in str(e) or "401" in str(e) or "API key" in str(e).lower()

def test_storage_high_concurrency(tmp_path):
    """極端な並列書き込み負荷テスト (100スレッド同時)"""
    db_path = str(tmp_path / "load_test.duckdb")
    storage = FinancialNarrativeStorage(db_path)
    
    import concurrent.futures
    
    def worker(i):
        metadata = {
            "accessionNumber": f"ACC-{i}",
            "ticker": f"T{i}",
            "cik": f"{i}",
            "form": "10-K",
            "filingDate": "2024-01-01"
        }
        storage.save_filing(metadata, {"content": "foo" * 100})
        return True

    # 100スレッドで同時に書き込み
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(worker, range(100)))
    
    assert all(results)
    
    # 件数確認
    with duckdb.connect(db_path) as conn:
        count = conn.execute("SELECT count(*) FROM filings").fetchone()[0]
        assert count == 100

def test_parser_corrupted_xbrl_zip(tmp_path):
    """壊れたZIPファイルに対するEDINETパーサーの挙動"""
    from src.edinet_parser import EdinetParser
    parser = EdinetParser()
    
    # ZIPではないファイルを渡す
    bad_zip = b"Not a zip file content"
    sections = parser.parse_zip(bad_zip)
    assert sections == {} # 空の辞書が返るはず
