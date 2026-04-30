import os
from datetime import datetime, timedelta

import pytest
from src.backend.core.calculator import PortfolioCalculator
from src.backend.core.database import DatabaseManager
from src.backend.core.models import Transaction


@pytest.fixture
def db():
    # テスト用のDBファイルを作成
    test_db_path = "test_assets.duckdb"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    manager = DatabaseManager(db_path=test_db_path)
    yield manager

    # テスト後に削除
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_full_calculation_flow(db):
    # 1. 取引を追加
    tx = Transaction(
        ticker="AAPL",
        type="BUY",
        asset_type="STOCK",
        quantity=10.0,
        price=150.0,
        timestamp=datetime.now() - timedelta(days=10),
    )
    db.add_transaction(tx)

    # 2. 現在のポジションを取得
    positions = db.get_positions()
    assert len(positions) == 1
    holdings = {pos[0]: pos[2] for pos in positions}

    # 3. 擬似的なヒストリカルデータを用意
    # 150 -> 155 -> 160 -> 140 (下落を混ぜる)
    price_map = {"AAPL": [150.0, 155.0, 160.0, 140.0]}

    # 4. 分析実行
    vol, sharpe, max_dd = PortfolioCalculator.calculate_risk_metrics(price_map, holdings)

    assert vol > 0
    assert max_dd < 0  # 下落があるのでマイナス
    # 160から140への下落は約 -12.5%
    assert max_dd < -10


def test_mismatch_db_and_calculator(db):
    # 意地悪なテスト: DBに銘柄はあるが、価格データが取得できなかった場合
    tx = Transaction(
        ticker="UNKNOWN",
        type="BUY",
        asset_type="STOCK",
        quantity=1.0,
        price=100.0,
        timestamp=datetime.now(),
    )
    db.add_transaction(tx)
    positions = db.get_positions()
    holdings = {pos[0]: pos[2] for pos in positions}

    # 価格データが空のマップ
    vol, sharpe, max_dd = PortfolioCalculator.calculate_risk_metrics({}, holdings)

    assert vol is None  # クラッシュせずに None を返すことを確認
