from pathlib import Path

import pandas as pd
import pytest

from src.engine.db_engine import CryptoDBEngine

# Constants for testing
EXPECTED_COUNT_2 = 2
EXPECTED_COUNT_1 = 1
BTC_CLOSE_INITIAL = 102.0
BTC_CLOSE_UPDATED = 105.0
BTC_SUPPLY = 19000000.0
PARTIAL_SUPPLY = 1000.0


@pytest.fixture
def temp_db():
    db_path = "tests/test_crypto.duckdb"
    path = Path(db_path)
    if path.exists():
        path.unlink()
    engine = CryptoDBEngine(db_path=db_path)
    yield engine
    if path.exists():
        path.unlink()


def test_engine_initialization(temp_db):
    assert Path(temp_db.db_path).exists()


def test_engine_save_and_get_prices(temp_db):
    data = {
        "Date": ["2023-01-01", "2023-01-02"],
        "Open": [100.0, 110.0],
        "High": [105.0, 115.0],
        "Low": [95.0, 105.0],
        "Close": [102.0, 112.0],
        "Volume": [1000, 1100],
    }
    df = pd.DataFrame(data)
    temp_db.save_prices("TESTBTC", df)

    results = temp_db.get_prices("TESTBTC")
    assert len(results) == EXPECTED_COUNT_2
    assert results[0]["ticker"] == "TESTBTC"
    assert results[0]["Close"] == BTC_CLOSE_INITIAL


def test_engine_upsert_behavior(temp_db):
    # First save
    df1 = pd.DataFrame(
        {
            "Date": ["2023-01-01"],
            "Open": [100.0],
            "High": [105.0],
            "Low": [95.0],
            "Close": [102.0],
            "Volume": [1000],
        }
    )
    temp_db.save_prices("UPSERT_TEST", df1)

    # Update same date
    df2 = pd.DataFrame(
        {
            "Date": ["2023-01-01"],
            "Open": [100.0],
            "High": [105.0],
            "Low": [95.0],
            "Close": [BTC_CLOSE_UPDATED],
            "Volume": [1000],
        }
    )
    temp_db.save_prices("UPSERT_TEST", df2)

    results = temp_db.get_prices("UPSERT_TEST")
    assert len(results) == EXPECTED_COUNT_1
    assert results[0]["Close"] == BTC_CLOSE_UPDATED  # Should be updated


def test_engine_save_and_get_metadata(temp_db):
    meta = {
        "circulating_supply": 19000000.0,
        "total_supply": 21000000.0,
        "max_supply": 21000000.0,
        "market_cap": 400000000000.0,
        "description": "Test Bitcoin Description",
    }
    temp_db.save_metadata("BTC", meta)

    result = temp_db.get_metadata("BTC")
    assert result is not None
    assert result["circulating_supply"] == BTC_SUPPLY
    assert result["description"] == "Test Bitcoin Description"
    assert "last_updated" in result


def test_engine_metadata_overwrite(temp_db):
    # Initial save
    temp_db.save_metadata("OVERWRITE", {"description": "First"})
    # Overwrite
    temp_db.save_metadata("OVERWRITE", {"description": "Second"})

    result = temp_db.get_metadata("OVERWRITE")
    assert result["description"] == "Second"


def test_engine_missing_metadata(temp_db):
    result = temp_db.get_metadata("UNKNOWN")
    assert result is None


def test_engine_partial_metadata(temp_db):
    # Only supply provided
    temp_db.save_metadata("PARTIAL", {"circulating_supply": PARTIAL_SUPPLY})
    result = temp_db.get_metadata("PARTIAL")
    assert result["circulating_supply"] == PARTIAL_SUPPLY
    assert result["max_supply"] is None
    assert result["description"] is None
