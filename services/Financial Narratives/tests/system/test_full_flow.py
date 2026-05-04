import pytest
import subprocess
import sys
import os
from src.storage import FinancialNarrativeStorage

def test_system_batch_fetch_cli(tmp_path):
    """CLIを介した全工程の実行テスト (モック環境下)"""
    db_path = str(tmp_path / "system.duckdb")
    # 環境変数を上書きしてテスト用DBを使用するように設定
    env = os.environ.copy()
    env["DEFAULT_DB_PATH"] = db_path
    
    # 実際には外部APIを叩かないよう、内部を一部パッチしたラッパースクリプトで実行するか、
    # あるいはモックを差し込んだ python -m src.batch_fetch を実行する。
    # ここではシンプルに、コマンドが正常終了し、DBファイルが生成されることを確認。
    
    # --days 0 で実行して、初期化だけ正常に行われるかを確認
    cmd = [
        sys.executable, "-m", "src.batch_fetch",
        "--days", "0"
    ]
    
    # 外部通信が発生するため、ここでは「コマンドの起動と基本引数の処理」までをテスト。
    # 完全に外部通信を遮断したE2Eは、テスト用のスタブサーバーが必要になる。
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    
    # ログが出力され、致命的なエラー（ImportError等）で落ちていないこと
    assert "Starting batch_fetch" in result.stderr or "Starting batch_fetch" in result.stdout
    # DBが生成されていること
    assert os.path.exists(db_path)
