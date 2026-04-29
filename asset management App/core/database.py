from __future__ import annotations

from pathlib import Path

import duckdb
from loguru import logger

from .models import AssetType, Transaction, TransactionType


class DatabaseManager:
    def __init__(self, db_path: str = "assets.duckdb"):
        self.db_path = Path(db_path)
        logger.info(f"Initializing DatabaseManager with path: {self.db_path.absolute()}")
        self._init_db()

    def _init_db(self):
        try:
            with duckdb.connect(str(self.db_path)) as conn:
                logger.info("Checking database schema and performing migrations if necessary...")
                tables = conn.execute("SHOW TABLES").fetchall()
                table_names = [t[0] for t in tables]

                if "transactions" in table_names:
                    cols = conn.execute("PRAGMA table_info('transactions')").fetchall()
                    col_names = [c[1] for c in cols]
                    if "date" in col_names and "timestamp" not in col_names:
                        logger.info("Migrating column 'date' to 'timestamp'...")
                        conn.execute("ALTER TABLE transactions RENAME COLUMN date TO timestamp")
                    if "memo" not in col_names:
                        logger.info("Adding missing column 'memo' to transactions table...")
                        conn.execute("ALTER TABLE transactions ADD COLUMN memo VARCHAR")
                    if "currency" not in col_names:
                        logger.info("Adding missing column 'currency' to transactions table...")
                        conn.execute("""
                            ALTER TABLE transactions ADD COLUMN currency VARCHAR DEFAULT 'USD'
                        """)

                    # Data cleanup: Ensure no NULL currencies exist
                    logger.info("Cleaning up NULL currencies in transactions table...")
                    conn.execute("UPDATE transactions SET currency = 'USD' WHERE currency IS NULL")

                logger.debug("Creating transactions table if not exists...")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY,
                        ticker VARCHAR,
                        type VARCHAR,
                        price DOUBLE,
                        quantity DOUBLE,
                        fee DOUBLE,
                        timestamp TIMESTAMP,
                        asset_type VARCHAR,
                        memo VARCHAR,
                        currency VARCHAR
                    );
                    CREATE SEQUENCE IF NOT EXISTS seq_transaction_id;
                """)
                logger.info("Database initialization completed successfully.")
        except Exception as e:
            logger.exception(f"Critical error during database initialization: {e}")
            raise

    def add_transaction(self, tx: Transaction) -> int:
        logger.info(f"Adding new transaction: {tx.ticker} {tx.transaction_type} {tx.quantity}")
        try:
            with duckdb.connect(str(self.db_path)) as conn:
                res = conn.execute(
                    """
                    INSERT INTO transactions (
                        id, ticker, type, price, quantity, fee, 
                        timestamp, asset_type, memo, currency
                    )
                    VALUES (nextval('seq_transaction_id'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    (
                        tx.ticker,
                        tx.transaction_type.value,
                        tx.price,
                        tx.quantity,
                        tx.fee,
                        tx.timestamp,
                        tx.asset_type.value,
                        tx.memo,
                        tx.currency,
                    ),
                ).fetchone()
                tx_id = res[0]
                logger.info(f"Transaction added successfully with ID: {tx_id}")
                return tx_id
        except Exception as e:
            logger.exception(f"Failed to add transaction for {tx.ticker}: {e}")
            raise

    def get_all_transactions(self) -> list[Transaction]:
        logger.debug("Fetching all transactions from database...")
        try:
            with duckdb.connect(str(self.db_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT id, ticker, type, price, quantity, fee, timestamp,
                           asset_type, memo, currency 
                    FROM transactions 
                    ORDER BY timestamp DESC
                """
                ).fetchall()
                transactions = [self._row_to_tx(row) for row in rows]
                logger.info(f"Successfully retrieved {len(transactions)} transactions.")
                return transactions
        except Exception as e:
            logger.exception(f"Error fetching transactions: {e}")
            raise

    def get_transaction(self, tx_id: int) -> Transaction | None:
        logger.debug(f"Fetching transaction with ID: {tx_id}")
        try:
            with duckdb.connect(str(self.db_path)) as conn:
                query = """
                    SELECT id, ticker, type, price, quantity, fee, timestamp,
                           asset_type, memo, currency 
                    FROM transactions WHERE id = ?
                """
                row = conn.execute(query, (tx_id,)).fetchone()
                if row:
                    tx = self._row_to_tx(row)
                    logger.info(f"Transaction {tx_id} found: {tx.ticker}")
                    return tx
                logger.warning(f"Transaction {tx_id} not found in database.")
                return None
        except Exception as e:
            logger.exception(f"Error fetching transaction {tx_id}: {e}")
            raise

    def get_positions(self):
        logger.info("Calculating current positions from transaction history...")
        try:
            with duckdb.connect(str(self.db_path)) as conn:
                query = """
                SELECT * FROM (
                    SELECT 
                        b.ticker, 
                        b.asset_type, 
                        b.buy_qty - COALESCE(s.sell_qty, 0) as current_qty,
                        b.total_cost / b.buy_qty as avg_price,
                        b.currency
                    FROM (
                        SELECT ticker, asset_type, COALESCE(currency, 'USD') as currency, 
                               SUM(quantity) as buy_qty, SUM(quantity * price + fee) as total_cost
                        FROM transactions WHERE type = 'BUY' 
                        GROUP BY ticker, asset_type, COALESCE(currency, 'USD')
                    ) b
                    LEFT JOIN (
                        SELECT ticker, asset_type, COALESCE(currency, 'USD') as currency, 
                               SUM(quantity) as sell_qty 
                        FROM transactions WHERE type = 'SELL' 
                        GROUP BY ticker, asset_type, COALESCE(currency, 'USD')
                    ) s ON b.ticker = s.ticker 
                        AND b.asset_type = s.asset_type 
                        AND b.currency = s.currency
                ) WHERE current_qty > 0
                """
                results = conn.execute(query).fetchall()
                logger.info(f"Calculated positions for {len(results)} assets.")
                return results
        except Exception as e:
            logger.exception(f"Error calculating positions: {e}")
            raise

    def delete_transaction(self, tx_id: int) -> bool:
        logger.info(f"Attempting to delete transaction with ID: {tx_id}")
        try:
            with duckdb.connect(str(self.db_path)) as conn:
                res = conn.execute(
                    "DELETE FROM transactions WHERE id = ? RETURNING id", (tx_id,)
                ).fetchone()
                success = res is not None
                if success:
                    logger.info(f"Transaction {tx_id} deleted successfully.")
                else:
                    logger.warning(f"Transaction {tx_id} could not be deleted (not found).")
                return success
        except Exception as e:
            logger.exception(f"Error deleting transaction {tx_id}: {e}")
            raise

    def update_transaction(self, tx_id: int, tx: Transaction) -> bool:
        logger.info(f"Attempting to update transaction {tx_id} for {tx.ticker}...")
        try:
            with duckdb.connect(str(self.db_path)) as conn:
                params = (
                    tx.ticker,
                    tx.transaction_type.value,
                    tx.price,
                    tx.quantity,
                    tx.fee,
                    tx.timestamp,
                    tx.asset_type.value,
                    tx.memo,
                    tx.currency,
                    tx_id,
                )
                logger.info(f"Executing SQL UPDATE with params: {params}")
                res = conn.execute(
                    """
                    UPDATE transactions SET 
                        ticker = ?, 
                        type = ?, 
                        price = ?, 
                        quantity = ?, 
                        fee = ?, 
                        timestamp = ?, 
                        asset_type = ?, 
                        memo = ?,
                        currency = ?
                    WHERE id = ?
                    RETURNING id
                """,
                    params,
                ).fetchone()
                success = res is not None
                if success:
                    logger.info(f"Transaction {tx_id} updated successfully.")
                else:
                    logger.warning(f"Transaction {tx_id} could not be updated (not found).")
                return success
        except Exception as e:
            logger.exception(f"Error updating transaction {tx_id}: {e}")
            raise

    def _row_to_tx(self, row) -> Transaction:
        return Transaction(
            id=row[0],
            ticker=row[1],
            transaction_type=TransactionType(row[2]),
            price=row[3],
            quantity=row[4],
            fee=row[5],
            timestamp=row[6],
            asset_type=AssetType(row[7]),
            memo=row[8],
            currency=row[9] if len(row) > 9 else "USD",
        )
