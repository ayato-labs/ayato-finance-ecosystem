import os
import pytest
import shutil
from pathlib import Path

@pytest.fixture
def test_data_dir():
    """テスト用の一時ディレクトリ"""
    path = Path("tests/temp_data")
    path.mkdir(parents=True, exist_ok=True)
    yield path
    # テスト後に削除
    if path.exists():
        shutil.rmtree(path)

@pytest.fixture
def mock_env(test_data_dir):
    """環境変数をテスト用に上書き"""
    old_jp = os.getenv("JP_DB_PATH")
    old_us = os.getenv("US_DB_PATH")
    old_master = os.getenv("MASTER_DB_PATH")
    
    os.environ["JP_DB_PATH"] = str(test_data_dir / "test_jp.duckdb")
    os.environ["US_DB_PATH"] = str(test_data_dir / "test_us.duckdb")
    os.environ["MASTER_DB_PATH"] = str(test_data_dir / "test_master.db")
    
    yield
    
    if old_jp: os.environ["JP_DB_PATH"] = old_jp
    if old_us: os.environ["US_DB_PATH"] = old_us
    if old_master: os.environ["MASTER_DB_PATH"] = old_master
