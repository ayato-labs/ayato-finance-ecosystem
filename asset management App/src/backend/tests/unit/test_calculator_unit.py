from __future__ import annotations

from datetime import datetime

import pytest

from core.calculator import BenchmarkCalculator
from core.models import Transaction, TransactionType


def test_shadow_performance_basic_usd():
    # Scenario: Buy 1 unit of stock for 100 USD
    txs = [
        Transaction(
            ticker="AAPL",
            type=TransactionType.BUY,
            quantity=1.0,
            price=100.0,
            currency="USD",
            timestamp=datetime(2023, 1, 1),
        )
    ]
    sp500_map = {"2023-01-01": 4000.0}
    current_sp500 = 4400.0  # 10% gain

    # Shadow units = 100 / 4000 = 0.025
    # Shadow value = 0.025 * 4400 = 110.0
    cost, val, units = BenchmarkCalculator.create_shadow_performance(txs, sp500_map, current_sp500)

    assert cost == 100.0
    assert val == 110.0
    assert units == 0.025


def test_shadow_performance_with_jpy_conversion():
    # Scenario: Buy stock in JPY
    txs = [
        Transaction(
            ticker="SONY",
            type=TransactionType.BUY,
            quantity=10.0,
            price=10000.0,  # 100,000 JPY total
            currency="JPY",
            timestamp=datetime(2023, 1, 1),
        )
    ]
    # Rate: 1 JPY = 0.007 USD -> 100,000 JPY = 700 USD
    forex_rates = {"JPY": 0.007, "USD": 1.0}
    sp500_map = {"2023-01-01": 4000.0}
    current_sp500 = 4000.0

    cost, val, units = BenchmarkCalculator.create_shadow_performance(
        txs, sp500_map, current_sp500, forex_rates=forex_rates
    )

    assert cost == 700.0
    assert val == 700.0
    assert units == 700 / 4000


def test_shadow_performance_edge_cases():
    # Zero quantity or price
    txs = [Transaction(ticker="Z", type=TransactionType.BUY, quantity=0, price=10, currency="USD")]
    cost, val, units = BenchmarkCalculator.create_shadow_performance(txs, {}, 4000)
    assert cost == 0
    assert val == 0

    # Missing date in map
    txs = [
        Transaction(
            ticker="M",
            type=TransactionType.BUY,
            quantity=1,
            price=100,
            currency="USD",
            timestamp=datetime(2000, 1, 1),
        )
    ]
    cost, val, units = BenchmarkCalculator.create_shadow_performance(
        txs, {"2023-01-01": 4000}, 4400
    )
    # Should skip transaction if date not found
    assert cost == 0


def test_alpha_calculation_strict():
    # Port: 100 -> 150 (50% gain)
    # Bench: 100 -> 120 (20% gain)
    metrics = BenchmarkCalculator.calculate_alpha_metrics(150, 100, 120, 100)
    assert metrics["alpha_percent"] == 25.0
    assert metrics["alpha_value_usd"] == 30.0

    # Case with zero cost (should not crash)
    metrics_zero = BenchmarkCalculator.calculate_alpha_metrics(100, 0, 100, 0)
    assert metrics_zero["portfolio_return"] == 0
    assert metrics_zero["alpha_percent"] == 0


def test_risk_metrics_calculation():
    from core.calculator import PortfolioCalculator

    # Scenario: Prices staying flat (0 volatility)
    prices = [100.0, 100.0, 100.0]
    vol, sharpe, max_dd, returns = PortfolioCalculator.calculate_risk_metrics(prices, 0.05)
    # The current implementation returns 0 if volatility is 0
    assert vol == 0
    assert sharpe == 0
    assert max_dd == 0

    # Scenario: Prices dropping then recovering
    prices_dd = [100.0, 80.0, 100.0]  # 20% drop
    vol_dd, _, max_dd_val, _ = PortfolioCalculator.calculate_risk_metrics(prices_dd, 0.0)
    # The implementation returns drawdown as a negative percentage
    assert max_dd_val == -20.0
    assert vol_dd is not None and vol_dd > 0


def test_risk_metrics_hard_cases():
    from core.calculator import PortfolioCalculator

    # Empty prices
    vol, sharpe, max_dd, returns = PortfolioCalculator.calculate_risk_metrics([], 0.05)
    assert vol is None
    assert sharpe is None
    assert max_dd is None
    assert returns is None

    # Single price
    vol, sharpe, max_dd, returns = PortfolioCalculator.calculate_risk_metrics([100.0], 0.05)
    assert vol is None

    # All zeros
    vol, sharpe, max_dd, returns = PortfolioCalculator.calculate_risk_metrics([0.0, 0.0], 0.05)
    assert vol is None


def test_advanced_metrics_calculation():
    from core.calculator import PortfolioCalculator

    # Matching returns (Correlation = 1.0, Beta = 1.0)
    p_returns = [0.01, 0.02, -0.01]
    b_returns = [0.01, 0.02, -0.01]
    sortino, beta, corr = PortfolioCalculator.calculate_advanced_metrics(p_returns, b_returns, 0.0)
    assert corr == pytest.approx(1.0)
    assert beta == pytest.approx(1.0)

    # Empty returns
    sortino, beta, corr = PortfolioCalculator.calculate_advanced_metrics([], [], 0.0)
    assert sortino is None
    assert beta is None
    assert corr is None
