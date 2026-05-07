import pytest
import subprocess
import duckdb
import os
import shutil
from pathlib import Path

def test_full_user_flow_sync_command(tmp_path):
    """
    E2E Test: main.py sync コマンド
    目的: ユーザーがCLIからsyncコマンドを実行し、データがDBに永続化されるまでの一連の流れをテストする。
    """
    # テスト用環境のセットアップ
    test_dir = tmp_path / "e2e_test"
    test_dir.mkdir()
    data_dir = test_dir / "data"
    data_dir.mkdir()
    
    # 既存の環境変数を引き継ぎつつ、テスト用のDBパスを設定（もし設定可能なら）
    # 今回はカレントディレクトリの data/fred.duckdb を見に行くので、
    # サブプロセス実行時のカレントディレクトリを調整する。
    
    # 実行
    # 本来は実APIを叩くべきだが、CI環境などの制約を考慮し、ここでは正常終了を確認
    # ※ 実運用では all_fetch.bat などの動作確認に相当
    
    result = subprocess.run(
        [".venv/Scripts/python", "main.py", "sync", "--symbols", "DFF"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "Synchronization process completed successfully" in result.stdout or "Synchronization process completed successfully" in result.stderr

    # --- データベースの裏取り調査 ---
    db_path = Path("data/fred.duckdb")
    if db_path.exists():
        conn = duckdb.connect(str(db_path))
        
        # DFFのデータが存在するか確認
        exists = conn.execute("SELECT COUNT(*) FROM series_metadata WHERE series_id = 'DFF'").fetchone()[0]
        assert exists > 0
        
        obs_count = conn.execute("SELECT COUNT(*) FROM observations WHERE series_id = 'DFF'").fetchone()[0]
        assert obs_count > 0
        
        conn.close()
    else:
        pytest.fail("Database file was not created in E2E test.")

def test_full_user_flow_explore_command():
    """
    E2E Test: main.py explore コマンド
    目的: 探索コマンドが正常に動作し、シリーズIDが取得できるかを確認する。
    """
    result = subprocess.run(
        [".venv/Scripts/python", "main.py", "explore", "--category", "10"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "Found" in result.stdout
    assert "series:" in result.stdout
