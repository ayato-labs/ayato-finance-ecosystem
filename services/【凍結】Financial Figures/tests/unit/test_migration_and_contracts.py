from datetime import date

import duckdb
import pytest
from pydantic import ValidationError

from src.core.contracts import JPFactContract, USFactContract
from src.core.migrations import MigrationManager


def test_migration_manager_idempotency(tmp_path):
    """
    Test that running migrations multiple times is safe and idempotent.
    """
    db_path = tmp_path / "idempotent.duckdb"
    shard_key = "jp"

    # 1st run
    MigrationManager.apply_migrations(db_path, shard_key)

    # 2nd run (should do nothing but check)
    MigrationManager.apply_migrations(db_path, shard_key)

    with duckdb.connect(str(db_path)) as conn:
        count = conn.execute("SELECT count(*) FROM _schema_version").fetchone()[0]
        # Should have tickers and company_facts registered
        assert count == 2


def test_migration_manager_schema_drift_protection(tmp_path):
    """
    Test how migration manager handles a corrupted or manually altered schema.
    """
    db_path = tmp_path / "drift.duckdb"
    shard_key = "jp"

    # Setup initial
    MigrationManager.apply_migrations(db_path, shard_key)

    # Manually drop a column to simulate drift
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("DROP INDEX IF EXISTS idx_jp_facts_date")
        conn.execute("ALTER TABLE company_facts DROP COLUMN NetSales")

    # Re-apply migrations: v1 is already recorded, so it won't fix it automatically
    # unless we increment version (v2). This confirms that currently it trusts the version table.
    MigrationManager.apply_migrations(db_path, shard_key)

    with duckdb.connect(str(db_path)) as conn:
        cols = conn.execute("DESCRIBE company_facts").df()["column_name"].tolist()
        # Expectation: Currently, it sees v1 is applied and skips.
        # This highlights a "meaningful" test result: we might need a "force" or "verify" mode.
        assert "NetSales" not in cols


def test_jp_contract_extreme_values():
    """
    Tough test for JP Data Contract: handle weird strings and malicious values.
    """
    base_data = {
        "DisclosedDate": date(2023, 3, 31),
        "DisclosedTime": "15:00",
        "LocalCode": "7203",
        "DisclosureNumber": "1",
        "Type": "Annual",
        "FiscalYear": "2023",
        "FiscalPeriod": "FY",
        "session_id": "test",
    }

    # 1. NaN as string (Common in messy CSVs)
    data_with_nan = base_data.copy()
    data_with_nan["NetSales"] = "NaN"
    contract = JPFactContract(**data_with_nan)
    assert contract.NetSales == "NaN"  # Pydantic allows str

    # 2. SQL Injection style in strings
    data_inj = base_data.copy()
    data_inj["LocalCode"] = "7203'; DROP TABLE company_facts;--"
    contract = JPFactContract(**data_inj)
    assert contract.LocalCode == "7203'; DROP TABLE company_facts;--"

    # 3. Invalid date type
    data_bad_date = base_data.copy()
    data_bad_date["DisclosedDate"] = "NotADate"
    with pytest.raises(ValidationError):
        JPFactContract(**data_bad_date)


def test_us_contract_numeric_overflow():
    """
    Verify US contract handles huge/messy values.
    """
    data = {
        "cik": "0000320193",
        "taxonomy": "us-gaap",
        "tag": "Assets",
        "label": "Total Assets",
        "unit": "USD",
        "value": 1.23e30,  # Huge value
        "end_date": date(2023, 9, 30),
        "accession_number": "0000320193-23-000106",
        "session_id": "test",
    }
    contract = USFactContract(**data)
    assert contract.value > 10**20

    # Type mismatch: value as string that isn't a number
    data["value"] = "abc"
    with pytest.raises(ValidationError):
        USFactContract(**data)
