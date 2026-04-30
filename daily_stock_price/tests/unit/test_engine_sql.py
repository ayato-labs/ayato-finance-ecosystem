
def test_engine_synced_view_sql_gen(engine):
    """Verify that get_synced_view generates a valid SQL string with correct placeholders."""
    # Register dummy path in catalog
    engine.catalog.register_many([("AAPL", "/dummy/path/batch_1.parquet", "price")])

    sql = engine.get_synced_view("AAPL")
    assert sql is not None

    # Check for core logic and schema flexibility (SELECT *)
    assert "SELECT *" in sql
    assert "EXCLUDE" in sql
    assert "row_num" in sql
    assert "WHERE Ticker = 'AAPL'" in sql

    # Check for deduplication logic
    assert "row_number()" in sql.lower()
    assert "PARTITION BY Date" in sql

    # Check for path inclusion
    assert "dummy/path/batch_1.parquet" in sql.replace("\\", "/")

def test_engine_empty_catalog_return(engine):
    """Verify that get_synced_view returns None for non-existent tickers."""
    sql = engine.get_synced_view("NON_EXISTENT")
    assert sql is None
