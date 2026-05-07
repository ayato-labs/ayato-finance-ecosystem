import pytest
import threading
import duckdb
import pandas as pd
from unittest.mock import MagicMock, patch
from src.ingestion.collector import FredCollector
from src.ingestion.writer import FredWriter

def test_collector_writer_integration(tmp_path):
    """
    Integration Test: Collector -> Queue -> Writer
    目的: 複数のコンポーネントが連携して、最終的にDBに正しいデータが書き込まれるかを確認する。
    ※ 結合テスト以降のため、API部分はモック化を許可
    """
    db_file = tmp_path / "integration_test.duckdb"
    writer = FredWriter(str(db_file))
    
    # Fredクラス自体をパッチして、__init__時のバリデーションコールを回避
    with patch('src.ingestion.collector.Fred') as mock_fred_class:
        mock_fred_instance = mock_fred_class.return_value
        
        # モックデータの設定
        mock_meta = {
            'id': 'TEST_ID',
            'title': 'Test Series',
            'units': 'Units',
            'frequency': 'D',
            'seasonal_adjustment': 'NSA',
            'last_updated': '2024-05-01 00:00:00',
            'notes': 'Test notes'
        }
        mock_series = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-05-01", "2024-05-02"]))
        
        mock_fred_instance.get_series_info.return_value = mock_meta
        mock_fred_instance.get_series.return_value = mock_series
        
        collector = FredCollector(api_key="mock_key")
        
        # 実行
        writer_thread = threading.Thread(
            target=writer.write_loop, 
            args=(collector.data_queue,),
            daemon=True
        )
        writer_thread.start()
        
        collector.fetch_series("TEST_ID", "2024-05-01")
        collector.data_queue.put(None) # 終了シグナル
        
        writer_thread.join(timeout=10)
    
    # --- 裏取り調査 (Data Audit) ---
    conn = duckdb.connect(str(db_file))
    
    # メタデータの確認
    meta_row = conn.execute("SELECT title, units FROM series_metadata WHERE series_id = 'TEST_ID'").fetchone()
    assert meta_row[0] == 'Test Series'
    assert meta_row[1] == 'Units'
    
    # 観測データの確認
    obs_count = conn.execute("SELECT COUNT(*) FROM observations WHERE series_id = 'TEST_ID'").fetchone()[0]
    assert obs_count == 2
    
    avg_value = conn.execute("SELECT AVG(value) FROM observations WHERE series_id = 'TEST_ID'").fetchone()[0]
    assert avg_value == 1.5
    
    conn.close()
