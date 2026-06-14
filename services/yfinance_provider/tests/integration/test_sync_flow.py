from unittest.mock import MagicMock, patch

import duckdb
from fastapi.testclient import TestClient

from src.api.main import app
from src.collector.engine import SyncEngine


def test_sync_engine_full_flow(db_manager):
    """[MOCK ALLOWED] SyncEngineが正しくワーカーを起動し、DBに書き込むか"""
    engine = SyncEngine(db_manager, max_workers=1)

    # yf.Tickerをモック化
    with patch("yfinance.Ticker") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"longName": "Test Co", "symbol": "TEST"}
        mock_ticker.financials = MagicMock()
        mock_ticker.financials.empty = True
        mock_ticker.history.return_value = MagicMock()
        mock_ticker.history.return_value.empty = True
        mock_yf.return_value = mock_ticker

        engine.run_sync(["TEST"], force=True)

        # DBにステータスが書き込まれたか確認
        conn = db_manager.get_connection()
        query = "SELECT last_status FROM sync_status WHERE ticker = 'TEST'"
        status = conn.execute(query).fetchone()
        assert status[0] == "SUCCESS"

        # infoテーブルにデータがあるか
        info = conn.execute("SELECT ticker FROM info WHERE ticker = 'TEST'").fetchone()
        assert info[0] == "TEST"
        conn.close()


def test_api_server_integration(db_manager):
    """APIサーバーがDBから正しく情報を引き出せるか"""
    # データを手動で注入
    conn = db_manager.get_connection()
    conn.execute("INSERT INTO info (ticker, data) VALUES ('AAPL', '{\"longName\": \"Apple Inc\"}')")
    conn.close()

    # APIのDB参照先をテスト用DBに向ける (実際の実装に合わせて修正が必要な場合あり)
    with patch("src.api.main.db_manager", db_manager):
        client = TestClient(app)
        response = client.get("/tickers/AAPL/info")
        assert response.status_code == 200
        assert response.json()["longName"] == "Apple Inc"


def test_negative_invalid_ticker(db_manager):
    """存在しない銘柄が指定された場合に、適切にFAILEDステータスが記録されるか"""
    engine = SyncEngine(db_manager, max_workers=1)

    with patch("yfinance.Ticker") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {}  # 空のデータを返す
        mock_yf.return_value = mock_ticker

        engine.run_sync(["INVALID"], force=True)

        conn = db_manager.get_connection()
        query = "SELECT last_status, error_message FROM sync_status WHERE ticker = 'INVALID'"
        status = conn.execute(query).fetchone()
        assert status[0] == "FAILED"
        assert "Crucial data missing" in status[1]
        conn.close()


def test_chaos_db_lock(db_manager):
    """DB書き込み時にエラーが発生しても、エンジンがハングせずにエラーを記録するか"""
    import time

    engine = SyncEngine(db_manager, max_workers=1)

    with patch("yfinance.Ticker") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"symbol": "CHAOS", "longName": "Chaos Co"}
        mock_ticker.financials = MagicMock()
        mock_ticker.financials.empty = True
        mock_ticker.history.return_value = MagicMock()
        mock_ticker.history.return_value.empty = True
        mock_yf.return_value = mock_ticker

        # 無限再帰を避けるため、オリジナルのメソッドを保持
        original_get_conn = db_manager.get_connection

        def get_mock_conn():
            conn = original_get_conn()
            m = MagicMock(wraps=conn)

            def conditional_execute(query, *args, **kwargs):
                query_up = query.upper()
                if "INSERT" in query_up and "SYNC_STATUS" not in query_up:
                    raise Exception("DB Locked")
                return conn.execute(query, *args, **kwargs)

            m.execute.side_effect = conditional_execute
            return m

        with patch.object(db_manager, "get_connection", side_effect=get_mock_conn):
            engine.run_sync(["CHAOS"], force=True)

            # 非同期処理の完了を待機 (少し長めに待つ)
            time.sleep(2.0)

            # 裏取り調査: ステータスが FAILED になっているか
            # 注意: DuckDBの同じファイルに別プロセス/スレッドからアクセスするため、
            # 新しい接続を確立する
            real_conn = duckdb.connect(db_manager.db_path)
            query = "SELECT last_status FROM sync_status WHERE ticker = 'CHAOS'"
            status = real_conn.execute(query).fetchone()
            assert status is not None
            assert status[0] == "FAILED"
            real_conn.close()
