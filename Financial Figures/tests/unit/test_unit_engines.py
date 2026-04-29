import pandas as pd
import pytest

from src.core.config import settings
from src.engines.jp_engine import JPEngine
from src.engines.us_engine import USEngine


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

    import duckdb

    with duckdb.connect(str(settings.DB_PATH_US)) as conn:
        res = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        assert res == 1


def test_jp_engine_ingest_facts_numeric_parsing(jp_engine):
    """Test that JP engine correctly handles non-numeric columns and missing values."""
    df = pd.DataFrame(
        [
            {
                "LocalCode": "7203",
                "Date": "2023-12-31",
                "NetSales": "1234.56",
                "Note": "This is a string",
                "Empty": None,
            }
        ]
    )

    import duckdb

    with duckdb.connect(str(settings.DB_PATH_JP)) as conn:
        # ENSURE CLEAN STATE
        conn.execute("DELETE FROM company_facts")
        jp_engine.ingest_facts("7203", df, "session-jp-unit")

        # Check if NetSales was ingested as numeric, but Note was ignored
        res = conn.execute("SELECT tag, value FROM company_facts").fetchall()
        tags = [r[0] for r in res]
        assert "NetSales" in tags
        assert "Note" not in tags
        assert len(tags) == 1
