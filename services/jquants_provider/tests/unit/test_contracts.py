import pytest
from src.core.contracts import JPTickerContract, JPPriceContract, JPFactContract


def test_ticker_contract_validation():
    """Unit test for Ticker Contract validation."""
    data = {
        "code": "13010",
        "name": "Test Co",
        "market_section": "Prime",
        "sector": "Fishery",
        "last_session_id": "test-session",
    }
    contract = JPTickerContract(**data)
    assert contract.code == "13010"
    assert contract.name == "Test Co"


def test_price_contract_invalid_data():
    """Unit test to ensure price contract fails on bad data."""
    bad_data = {"Date": "not-a-date", "Code": "1301", "session_id": "test"}
    with pytest.raises(Exception):
        JPPriceContract(**bad_data)


def test_fact_contract_numeric_coercion():
    """Unit test for Fact Contract numeric handling."""
    data = {
        "DisclosedDate": "2026-05-05",
        "DisclosedTime": "15:00",
        "LocalCode": "1301",
        "DisclosureNumber": "123",
        "Type": "Summary",
        "FiscalYear": "2026",
        "FiscalPeriod": "Q1",
        "NetSales": "1000.50",  # String that should be coerced to float
        "session_id": "test",
    }
    contract = JPFactContract(**data)
    assert contract.NetSales == 1000.50


def test_engine_ticker_mapping_logic():
    """
    Unit test for ticker mapping logic placeholder.
    """
    pass
