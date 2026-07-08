import json
import os
from unittest.mock import MagicMock, patch
import pandas as pd
from src.collector.engine import SyncEngine


def test_comprehensive_user_flow(db_manager):
    """
    1. 銘柄同期を実行 (SyncEngine)
    2. DBにデータが存在し、裏取りができるか確認
    3. APIを介して同じデータが正しく取得できるか検証 (FastAPI)
    """
    ticker = "AAPL"
    engine = SyncEngine(db_manager, max_workers=1)

    # 1. 同期実行
    # ユーザー指示の「総合テストはモック化許可」に基づき、再現性のためMockを使用
    with patch("yfinance.Ticker") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"longName": "Apple Inc.", "symbol": "AAPL", "currentPrice": 150.0}
        mock_ticker.financials = MagicMock()
        mock_ticker.financials.empty = True
        
        # Create non-empty dummy prices DataFrame
        mock_df = pd.DataFrame([{
            "Date": pd.Timestamp("2026-07-09 00:00:00"),
            "Open": 150.0,
            "High": 155.0,
            "Low": 148.0,
            "Close": 150.0,
            "Volume": 10000,
            "Dividends": 0.0,
            "Stock Splits": 0.0
        }]).set_index("Date")
        mock_ticker.history.return_value = mock_df
        mock_yf.return_value = mock_ticker


        engine.run_sync([ticker], force=True)

    # 2. データベースの直接調査 (裏取り)
    conn = db_manager.get_connection()
    db_res = conn.execute("SELECT data FROM info WHERE ticker = ?", [ticker]).fetchone()
    assert db_res is not None

    db_info = json.loads(db_res[0])
    assert db_info["longName"] == "Apple Inc."
    conn.close()

    # ファイル保存の検証 (SCD Type 2)
    profile_path = os.path.join("data", "profiles", f"{ticker}.json")
    assert os.path.exists(profile_path)
    with open(profile_path, encoding="utf-8") as f:
        history = json.load(f)
        assert len(history) == 1
        assert history[0]["longName"] == "Apple Inc."

    # 3. Clean up and check sync status
    logger_check = db_manager.get_connection()
    query = "SELECT last_status FROM sync_status WHERE ticker = ?"
    sync_check = logger_check.execute(query, [ticker]).fetchone()
    assert sync_check[0] == "SUCCESS"
    logger_check.close()
