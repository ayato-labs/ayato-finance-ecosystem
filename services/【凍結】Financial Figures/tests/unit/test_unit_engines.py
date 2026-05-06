import duckdb
import pandas as pd
import pytest

from src.core.config import settings
from src.providers.jquants.engine import JPEngine
from src.providers.sec_edgar.engine import USEngine


@pytest.fixture
def us_engine(test_settings):
    return USEngine()


@pytest.fixture
def jp_engine(test_settings):
    return JPEngine()


def test_us_engine_ingest_facts_empty(us_engine):
    """Ensure no crash or error when empty data is passed."""
    us_engine.ingest_facts("TSLA", {}, "session-empty")
    # If no exception, pass


def test_us_engine_ingest_facts_normal(us_engine):
    facts_data = {
        "cik": "1318605",
        "facts": {
            "us-gaap": {
                "NetSales": {
                    "units": {
                        "USD": [
                            {
                                "val": 1000,
                                "end": "2023-12-31",
                                "fy": 2023,
                                "fp": "FY",
                                "accn": "001-TEST",
                            }
                        ]
                    }
                }
            }
        },
    }
    us_engine.ingest_facts("TSLA", facts_data, "session-unit")

    with duckdb.connect(str(settings.DB_PATH_US)) as conn:
        res = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        assert res == 1


def test_jp_engine_ingest_facts_numeric_parsing(jp_engine):
    """Test that JP engine correctly handles non-numeric columns and missing values."""
    df = pd.DataFrame(
        [
            {
                "LocalCode": "7203",
                "DisclosedDate": "2023-12-31",
                "DisclosedTime": "15:00:00",
                "DisclosureNumber": "2023001",
                "Type": "Quarterly",
                "FiscalYear": "2023",
                "FiscalPeriod": "FY",
                "NetSales": "1234.56",
                "Note": "This is a string",
                "Empty": None,
            }
        ]
    )

    with duckdb.connect(str(settings.DB_PATH_JP)) as conn:
        # ENSURE CLEAN STATE
        conn.execute("DELETE FROM company_facts")
        jp_engine.ingest_facts("7203", df, "session-jp-unit")

        # In WIDE FORMAT, NetSales is a column.
        res = conn.execute("SELECT NetSales FROM company_facts").fetchone()
        assert res[0] == 1234.56
        
        # Check that metadata columns exist
        cols = [c[1] for c in conn.execute("PRAGMA table_info('company_facts')").fetchall()]
        assert "LocalCode" in cols
        assert "DisclosedDate" in cols
        # "Note" should NOT be in cols because it's not in the contract
        assert "Note" not in cols
