import pandas as pd
import pytest
from loguru import logger
from src.validator import DataValidator


@pytest.fixture
def caplog_handler(caplog):
    handler_id = logger.add(caplog.handler, format="{message}")
    yield caplog
    logger.remove(handler_id)


@pytest.fixture
def validator():
    return DataValidator(spike_threshold=0.5)


def test_validate_logical_valid(validator):
    df = pd.DataFrame(
        {
            "Ticker": ["AAPL"],
            "Date": [pd.Timestamp("2023-01-01")],
            "Open": [150.0],
            "High": [155.0],
            "Low": [149.0],
            "Close": [152.0],
            "Volume": [1000000],
            "StockSplits": [0.0],
        }
    )
    result = validator.validate(df)
    assert len(result) == 1
    assert result.iloc[0]["Ticker"] == "AAPL"


def test_validate_logical_invalid_high_low(validator):
    df = pd.DataFrame(
        {
            "Ticker": ["AAPL"],
            "Date": [pd.Timestamp("2023-01-01")],
            "Open": [150.0],
            "High": [140.0],  # High < Low
            "Low": [149.0],
            "Close": [152.0],
            "Volume": [1000000],
            "StockSplits": [0.0],
        }
    )
    result = validator.validate(df)
    assert len(result) == 0


def test_validate_logical_negative_price(validator):
    df = pd.DataFrame(
        {
            "Ticker": ["AAPL"],
            "Date": [pd.Timestamp("2023-01-01")],
            "Open": [-150.0],
            "High": [155.0],
            "Low": [149.0],
            "Close": [152.0],
            "Volume": [1000000],
            "StockSplits": [0.0],
        }
    )
    result = validator.validate(df)
    assert len(result) == 0


def test_validate_statistical_spike_warning(validator, caplog_handler):
    # 50%以上の急落をシミュレート
    df = pd.DataFrame(
        {
            "Ticker": ["FAKE", "FAKE"],
            "Date": [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")],
            "Open": [100.0, 40.0],
            "High": [105.0, 45.0],
            "Low": [95.0, 35.0],
            "Close": [100.0, 40.0],  # 60% drop
            "Volume": [1000, 1000],
            "StockSplits": [0.0, 0.0],
        }
    )
    result = validator.validate(df)
    assert len(result) == 2
    # Warningログが出ているか確認
    assert "Price spike detected for FAKE" in caplog_handler.text
    assert "WITHOUT split info" in caplog_handler.text


def test_validate_statistical_spike_with_split(validator, caplog_handler):
    # 50%以上の急落だが、分割情報がある場合
    df = pd.DataFrame(
        {
            "Ticker": ["FAKE", "FAKE"],
            "Date": [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")],
            "Open": [100.0, 40.0],
            "High": [105.0, 45.0],
            "Low": [95.0, 35.0],
            "Close": [100.0, 40.0],  # 60% drop
            "Volume": [1000, 1000],
            "StockSplits": [0.0, 0.5],  # 1:2 split
        }
    )
    result = validator.validate(df)
    assert len(result) == 2
    # Infoログ（分割あり）が出ているか確認
    assert "WITH split info (0.5)" in caplog_handler.text
