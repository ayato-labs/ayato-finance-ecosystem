from src.core.contracts import (
    JPDividendContract,
    JPFactContract,
    JPIndexContract,
    JPPriceContract,
    JPTickerContract,
)

def test_ticker_contract_validation():
    """Unit test for Ticker Contract validation."""
    data = {
        "code": "13010",
        "name": "Test Co",
        "market_section_id": 1,
        "sector_id": 10,
        "last_session_id": "test-session",
    }
    contract = JPTickerContract(**data)
    assert contract.code == "13010"
    assert contract.market_section_id == 1

def test_price_contract_coercion():
    """Unit test for Price Contract numeric coercion."""
    data = {
        "Date": "2026-05-05",
        "Code": "1301",
        "Open": "100.5",
        "Volume": "1000.0",
        "session_id": "test"
    }
    contract = JPPriceContract(**data)
    assert isinstance(contract.Open, Decimal)
    assert contract.Open == Decimal("100.5")
    assert contract.Volume == 1000

def test_fact_contract_validation():
    """Unit test for Fact Contract."""
    data = {
        "DisclosedDate": "2026-05-05",
        "DisclosedTime": "15:00",
        "LocalCode": "1301",
        "DisclosureNumber": "123",
        "Type": "Summary",
        "FiscalYear": "2026",
        "FiscalPeriod": "Q1",
        "NetSales": "1234567890.1",
        "session_id": "test",
    }
    contract = JPFactContract(**data)
    assert contract.NetSales == Decimal("1234567890.1")

def test_index_contract():
    """Unit test for Index Contract."""
    data = {
        "Date": "2026-05-05",
        "Code": "0000",
        "Close": "38000.50",
        "session_id": "test"
    }
    contract = JPIndexContract(**data)
    assert contract.Close == Decimal("38000.50")

def test_dividend_contract():
    """Unit test for Dividend Contract."""
    data = {
        "AnnouncementDate": "2026-05-05",
        "Code": "1301",
        "RecordDate": "2026-03-31",
        "DividendValue": "50.0",
        "session_id": "test"
    }
    contract = JPDividendContract(**data)
    assert contract.DividendValue == Decimal("50.0")
    assert contract.RecordDate == date(2026, 3, 31)
