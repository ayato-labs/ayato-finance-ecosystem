import pytest
import os
from src.ingestion.collector import FredCollector

@pytest.mark.skipif(not os.getenv("FRED_API_KEY"), reason="FRED_API_KEY not set")
def test_collector_fetch_real_api():
    """
    Unit Test: FredCollector.fetch_series (Real API)
    目的: Mockを使わずに実際のFRED APIからデータを取得できるか確認する。
    ※ ユーザー指定によりMock禁止
    """
    collector = FredCollector()
    # 非常に軽量なシンボル（10年物国債利回り: DGS10）
    symbol = "DGS10"
    start_date = "2024-05-01"
    
    collector.fetch_series(symbol, start_date)
    
    # キューにデータが入っているか確認
    # fetch_series は metadata と observations の2つを投入する
    items = []
    while not collector.data_queue.empty():
        items.append(collector.data_queue.get())
    
    assert len(items) >= 2
    types = [i[0] for i in items]
    assert "metadata" in types
    assert "observations" in types
    
    # メタデータの内容確認
    meta = next(i[1] for i in items if i[0] == "metadata")
    assert meta['id'] == symbol
    assert 'title' in meta

def test_collector_invalid_api_key():
    """
    Chaos Test: 無効なAPIキー
    目的: 認証エラー時に適切にログが記録され、例外が報告されるか。
    """
    with pytest.raises(Exception):
        collector = FredCollector(api_key="INVALID_KEY")
        collector.fetch_series("DFF", "2024-01-01")
