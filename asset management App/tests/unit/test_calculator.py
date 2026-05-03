import pytest
from src.backend.core.calculator import PortfolioCalculator


def test_calculate_risk_metrics_normal():
    # 正常系: 2銘柄の安定した上昇
    prices_map = {
        "AAPL": [100.0, 101.0, 102.0, 103.0, 104.0],
        "TSLA": [200.0, 202.0, 204.0, 206.0, 208.0],
    }
    holdings = {"AAPL": 10, "TSLA": 5}

    vol, sharpe, max_dd = PortfolioCalculator.calculate_risk_metrics(prices_map, holdings)

    assert vol > 0
    assert sharpe > 0
    assert max_dd <= 0
    assert isinstance(vol, float)


def test_calculate_risk_metrics_empty():
    # 異常系: データが空
    vol, sharpe, max_dd = PortfolioCalculator.calculate_risk_metrics({}, {})
    assert vol is None
    assert sharpe is None
    assert max_dd is None


def test_calculate_risk_metrics_single_day():
    # 異常系: 1日分しかデータがない(変化率が計算できない)
    prices_map = {"AAPL": [100.0]}
    holdings = {"AAPL": 10}
    vol, sharpe, max_dd = PortfolioCalculator.calculate_risk_metrics(prices_map, holdings)
    assert vol is None


def test_calculate_risk_metrics_zero_volatility():
    # 特殊系: 価格が全く動かない(ボラティリティ 0)
    prices_map = {"AAPL": [100.0, 100.0, 100.0]}
    holdings = {"AAPL": 10}
    vol, sharpe, max_dd = PortfolioCalculator.calculate_risk_metrics(prices_map, holdings)
    assert vol == 0
    assert sharpe == 0  # 0/0 回避
    assert max_dd == 0


def test_calculate_risk_metrics_max_drawdown():
    # 厳しいテスト: 50%の下落
    prices_map = {"AAPL": [100.0, 110.0, 55.0, 60.0]}  # 110 -> 55 は 50% 下落
    holdings = {"AAPL": 1}
    vol, sharpe, max_dd = PortfolioCalculator.calculate_risk_metrics(prices_map, holdings)

    # 期待値: 110から55への下落なので -50%
    assert pytest.approx(max_dd, 0.1) == -50.0


def test_calculate_risk_metrics_mismatch_length():
    # 異常系: 銘柄間でデータ数が異なる(最小公約数で計算されるか)
    prices_map = {"AAPL": [100.0, 101.0, 102.0], "TSLA": [200.0, 202.0]}
    holdings = {"AAPL": 1, "TSLA": 1}
    vol, sharpe, max_dd = PortfolioCalculator.calculate_risk_metrics(prices_map, holdings)
    # 2日間(変化率は1日分)で計算されるはず
    assert vol is not None
