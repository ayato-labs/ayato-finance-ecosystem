import pytest
from pathlib import Path
from src.engine import JPEngine


def test_shard_routing_master():
    engine = JPEngine()
    path = engine._get_shard_path("tickers")
    assert "jquants_master.duckdb" in str(path)

    path2 = engine._get_shard_path("market_sections")
    assert "jquants_master.duckdb" in str(path2)

def test_shard_routing_prices():
    """Verify prices shard routing."""
    engine = JPEngine()
    path = engine._get_shard_path("daily_prices")
    assert "jquants_prices.duckdb" in str(path)

def test_shard_routing_financials():
    """Verify financials shard routing."""
    engine = JPEngine()
    path = engine._get_shard_path("company_facts")
    assert "jquants_financials.duckdb" in str(path)
    
    path2 = engine._get_shard_path("dividends")
    assert "jquants_financials.duckdb" in str(path2)

def test_shard_routing_default_to_master():
    """Verify unknown tables default to master shard."""
    engine = JPEngine()
    path = engine._get_shard_path("unknown_table")
    assert "jquants_master.duckdb" in str(path)
