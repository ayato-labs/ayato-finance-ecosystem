import pytest
from src.core.db_manager import DatabaseManager


@pytest.fixture
def test_db_path(tmp_path):
    """テストごとにクリーンな一時DBパスを提供"""
    db_file = tmp_path / "test_yfinance.duckdb"
    return str(db_file)


@pytest.fixture
def db_manager(test_db_path):
    """初期化済みのDatabaseManagerを提供"""
    manager = DatabaseManager(test_db_path)
    conn = manager.get_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS ticker_master (ticker VARCHAR PRIMARY KEY)")
    conn.execute("INSERT OR IGNORE INTO ticker_master (ticker) VALUES ('AAPL'), ('9119.T')")
    conn.close()
    return manager



@pytest.fixture
def sample_tickers():
    """テスト用の実在銘柄リスト (日米混在)"""
    return ["AAPL", "9119.T"]
