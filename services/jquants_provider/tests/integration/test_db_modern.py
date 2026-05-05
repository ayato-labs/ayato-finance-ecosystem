import tempfile
from pathlib import Path
from src.core.schema import TABLE_SCHEMAS
from src.core.contracts import JPTickerContract, JPPriceContract, JPFactContract


def test_pydantic_sql_schema_consistency():
    """
    Data Contract Test:
    Ensure fields defined in Pydantic contracts exist in the SQL schema.
    """
    # 1. Check Tickers
    ticker_sql = TABLE_SCHEMAS["tickers"]["sql"].lower()
    for field in JPTickerContract.model_fields:
        assert field.lower() in ticker_sql, f"Field '{field}' missing in tickers SQL schema"

    # 2. Check Prices
    price_sql = TABLE_SCHEMAS["daily_prices"]["sql"].lower()
    for field in JPPriceContract.model_fields:
        if field == "ingested_at":
            continue
        assert field.lower() in price_sql, f"Field '{field}' missing in daily_prices SQL schema"

    # 3. Check Facts (Financials)
    fact_sql = TABLE_SCHEMAS["company_facts"]["sql"].lower()
    for field in JPFactContract.model_fields:
        if field == "ingested_at":
            continue
        assert field.lower() in fact_sql, f"Field '{field}' missing in company_facts SQL schema"


def test_catalog_shard_tracking(mocker):
    """
    Integration Test: Verify that catalog correctly tracks shard state.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_master = Path(tmpdir) / "test_master.duckdb"
        
        # Override catalog path
        mocker.patch("src.core.config.settings.MASTER_DB_PATH", test_master)
        from src.core.catalog import catalog_manager

        # 1. Update status
        catalog_manager.update_shard_status(
            shard_name="test_shard",
            table_name="test_table",
            last_session_id="session-1",
            last_date="20260505",
            record_count=100,
        )

        # 2. Retrieve and Verify
        status = catalog_manager.get_shard_status("test_shard", "test_table")
        assert status is not None
        assert status["last_session_id"] == "session-1"
        assert status["record_count"] == 100
