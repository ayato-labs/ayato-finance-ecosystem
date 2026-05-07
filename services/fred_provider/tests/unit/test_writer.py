import pytest
import os
import duckdb
from src.ingestion.writer import FredWriter

def test_writer_init_db_schema(tmp_path):
    """
    Unit Test: FredWriter._init_db
    目的: 正しいスキーマ（テーブルとカラム）が作成されることを確認する。
    """
    db_file = tmp_path / "test_fred.duckdb"
    writer = FredWriter(str(db_file))
    
    conn = duckdb.connect(str(db_file))
    
    # series_metadata テーブルの確認
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    assert "series_metadata" in table_names
    assert "observations" in table_names
    
    # カラムの確認
    columns = conn.execute("PRAGMA table_info('series_metadata')").fetchall()
    col_names = [c[1] for c in columns]
    assert "series_id" in col_names
    assert "title" in col_names
    
    conn.close()

def test_writer_invalid_db_path():
    """
    Chaos Test: 無効なパスでの初期化
    目的: 異常なパスが与えられた際に適切に例外が発生し、ログに記録されるか。
    """
    with pytest.raises(Exception):
        FredWriter("/non/existent/path/db.duckdb")
