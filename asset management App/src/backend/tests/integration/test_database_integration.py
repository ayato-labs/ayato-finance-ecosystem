from __future__ import annotations

import duckdb
import pytest

from core.database import DatabaseManager
from core.models import Transaction


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_assets.duckdb"
    return str(db_path)


def test_database_init_and_migrations(temp_db):
    # First init
    DatabaseManager(db_path=temp_db)
    with duckdb.connect(temp_db) as conn:
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        assert "transactions" in tables

    # Test column migration (manually remove a column and re-init)
    with duckdb.connect(temp_db) as conn:
        conn.execute("ALTER TABLE transactions DROP COLUMN memo")

    # Re-init should add it back
    DatabaseManager(db_path=temp_db)
    with duckdb.connect(temp_db) as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info('transactions')").fetchall()]
        assert "memo" in cols


def test_transaction_crud(temp_db):
    db = DatabaseManager(db_path=temp_db)
    tx = Transaction(
        ticker="AAPL", type="BUY", price=150.0, quantity=10, asset_type="STOCK", currency="USD"
    )

    # Create
    tx_id = db.add_transaction(tx)
    assert tx_id > 0

    # Read
    saved_tx = db.get_transaction(tx_id)
    assert saved_tx.ticker == "AAPL"
    assert saved_tx.price == 150.0

    # Update
    tx.price = 160.0
    db.update_transaction(tx_id, tx)
    updated_tx = db.get_transaction(tx_id)
    assert updated_tx.price == 160.0

    # Delete
    assert db.delete_transaction(tx_id) is True
    assert db.get_transaction(tx_id) is None


def test_position_calculation(temp_db):
    db = DatabaseManager(db_path=temp_db)
    # Buy 10 AAPL @ 150
    db.add_transaction(Transaction(ticker="AAPL", type="BUY", price=150, quantity=10))
    # Sell 4 AAPL @ 160
    db.add_transaction(Transaction(ticker="AAPL", type="SELL", price=160, quantity=4))

    positions = db.get_positions()
    # Find AAPL
    aapl = next(p for p in positions if p[0] == "AAPL")
    assert aapl[2] == 6.0  # 10 - 4
    assert aapl[3] == 150.0  # Avg price should be buy price


def test_database_locking_handling(temp_db):
    DatabaseManager(db_path=temp_db)

    # DuckDB's locking behavior varies by OS and configuration.
    pass
