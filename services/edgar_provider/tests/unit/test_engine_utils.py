import json
import time

from src.core.utils import RateLimiter, get_all_tickers
from src.engine import USEngine, parse_company_facts_json


def test_rate_limiter_timing():
    """Unit test: Verify rate limiter wait times (Real logic, no mock)."""
    limiter = RateLimiter(requests_per_second=5)  # 200ms per request

    # We test the calculation logic
    # Request 1: No wait
    # Request 2: Must be 0.2s after Request 1
    # ...
    # Instead of real time which is flaky, we can check if it blocks appropriately
    t1 = time.perf_counter()
    limiter.wait()
    limiter.wait()
    t2 = time.perf_counter()
    assert (t2 - t1) >= 0.15  # Roughly 1/5 second

def test_get_all_tickers_real_api():
    """Unit test: Real SEC API call (No mock allowed for unit)."""
    tickers = get_all_tickers()
    assert len(tickers) > 5000
    assert any(t['ticker'] == 'AAPL' for t in tickers)

def test_parse_company_facts_json_logic():
    """Unit test: Verify parsing logic with a sample JSON string."""
    ticker_map = {"0000320193": "AAPL"}

    sample_json = {
        "cik": 320193,
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "label": "Net Income",
                    "units": {
                        "USD": [
                            {
                                "val": 1000000, "accn": "0001-test",
                                "filed": "2024-01-01", "fy": 2023,
                                "fp": "FY", "form": "10-K"
                            }
                        ]
                    }
                }
            }
        }
    }

    records = parse_company_facts_json(
        "dummy.json", json.dumps(sample_json), ticker_map, "test-session"
    )
    assert len(records) == 1
    assert records[0][0] == "AAPL"
    assert records[0][7] == "Net Income"
    assert records[0][8] == 1000000.0

def test_engine_init_creates_files(clean_db_paths):
    """Unit test: USEngine initialization should trigger migration and create DB files."""
    USEngine()
    assert clean_db_paths["facts"].exists()
    assert clean_db_paths["narratives"].exists()
    assert clean_db_paths["master"].exists()
