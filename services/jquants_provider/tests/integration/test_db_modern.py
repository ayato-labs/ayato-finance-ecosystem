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
    test_master = Path("data/test_master.duckdb")
    if test_master.exists():
        test_master.unlink()

    # Override catalog path
    mocker.patch("src.core.config.settings.MASTER_DB_PATH", test_master)
    from src.core.catalog import CatalogManager

    local_catalog = CatalogManager(test_master)

    # 1. Register a shard
    local_catalog.update_shard_status(
        shard_name="test_shard",
        file_path="data/test_shard.duckdb",
        version=1,
        status="active",
        records_count=100,
    )

    # 2. Retrieve and Verify
    info = local_catalog.get_shard_info("test_shard")
    assert info is not None
    assert info["shard_name"] == "test_shard"
    assert info["records_count"] == 100
    assert info["schema_version"] == 1

    if test_master.exists():
        test_master.unlink()

    assert info["records_count"] == 100
    assert info["schema_version"] == 1

    if test_master.exists():
        test_master.unlink()
