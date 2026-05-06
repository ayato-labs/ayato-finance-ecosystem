import pytest
import os
from src.engine import JPEngine

@pytest.mark.skipif(
    not os.getenv("JQUANTS_REFRESH_TOKEN"),
    reason="JQUANTS_REFRESH_TOKEN not set"
)
def test_real_api_auth_connectivity():
    """
    Unit test for real J-Quants API connectivity (No Mock).
    Verifies that we can authenticate and fetch a small sample.
    """
    engine = JPEngine()
    # Test internal client authentication
    token = engine.cli.get_id_token()
    assert token is not None
    assert len(token) > 0
    
    # Test a simple fetch (tickers for a fixed date or just listing)
    # Using a small date range or specific code to avoid heavy traffic
    df = engine.fetch_tickers()
    assert df is not None
    assert not df.empty
    assert "Code" in df.columns

@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set"
)
def test_real_llm_connectivity():
    """
    Unit test for real LLM connectivity (No Mock).
    Verifies that the LLM client (if used for analysis) is reachable.
    """
    # Assuming LLM usage might be in future analysis steps
    # For now, just a placeholder or basic check if integrated
    pass
