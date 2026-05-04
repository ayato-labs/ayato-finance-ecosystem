import os

import duckdb

# Constants for testing
EXPECTED_PRICE_COUNT = 5


def test_full_sync_and_catalog_handshake(engine, temp_data_dir):
    """
    Integration: Fetcher -> Engine.sync_ticker -> FileSystem -> Catalog.
    Verifies that all components talk to each other correctly.
    """
    ticker = "HANDSHAKE_TEST"

    # Run the sync
    engine.sync_ticker(ticker)

    # 1. Verify file exists
    # Files are saved in year=YYYY/month=MM/batch_*.parquet
    # We can search recursively
    found_parquet = False
    for _root, _dirs, files in os.walk(str(temp_data_dir / "market_data")):
        for f in files:
            if f.endswith(".parquet"):
                found_parquet = True
                break
    assert found_parquet, "Parquet file should have been written"

    # 2. Verify Catalog entry
    paths = engine.catalog.get_paths(ticker)
    assert len(paths) == 1
    assert "batch_" in paths[0]

    # 3. Verify DuckDB can actually read the data via the view
    sql = engine.get_synced_view(ticker)
    db = duckdb.connect()
    # sql includes read_parquet([paths])
    df = db.query(sql).to_df()

    assert len(df) == EXPECTED_PRICE_COUNT
    # Verify core columns exist
    expected_cols = {
        "Date",
        "Ticker",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Source",
        "LoadTimestamp",
        "StockSplits",
    }
    assert expected_cols.issubset(set(df.columns))
