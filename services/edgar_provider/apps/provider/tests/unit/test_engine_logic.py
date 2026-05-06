import json

from edgar_core.config import settings
from edgar_provider.engine import USEngine, parse_company_facts_json


def test_parse_company_facts_json_valid():
    """
    Unit Test: Verify core parsing logic.
    No mocks.
    """
    sample = {
        "cik": "12345",
        "facts": {
            "us-gaap": {
                "Assets": {
                    "label": "Total Assets",
                    "units": {
                        "USD": [
                            {"val": 1000, "accn": "0001", "filed": "2024-01-01", "fy": 2023, "fp": "FY"}
                        ]
                    }
                }
            }
        }
    }
    ticker_map = {"0000012345": "TEST"}
    filings, facts = parse_company_facts_json("test.json", json.dumps(sample), ticker_map, "sid")
    
    assert len(filings) == 1
    assert filings[0][1] == "TEST"
    assert facts[0][3] == "Total Assets"
    assert facts[0][4] == 1000.0

def test_extract_section_regex():
    """
    Unit Test: Verify regex-based section extraction.
    No mocks.
    """
    engine = USEngine()
    text = "# Header\n## Item 1. Business\nContent 1\n## Item 1A. Risk\nContent 2"
    
    biz = engine._extract_section(text, [r"##\s+Item\s+1\.?\s+Business"])
    risk = engine._extract_section(text, [r"##\s+Item\s+1A\.?\s+Risk"])
    
    assert "Content 1" in biz
    assert "Business" in biz
    assert "Content 2" in risk
    assert "Business" not in risk
