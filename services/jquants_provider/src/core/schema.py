"""
Schema definitions for J-Quants Provider.
This file is the Single Source of Truth (SSoT) for the database structure.
Optimized for Storage Efficiency (V2).
"""

TABLE_SCHEMAS = {
    "market_sections": {
        "description": "Normalized market section names (Prime, Standard, etc.)",
        "version": 2,
        "shard": "master",
        "sql": """
            CREATE TABLE IF NOT EXISTS market_sections (
                id UTINYINT PRIMARY KEY,
                name VARCHAR UNIQUE
            )
        """,
    },
    "sectors": {
        "description": "Normalized sector names (Electronics, Banking, etc.)",
        "version": 2,
        "shard": "master",
        "sql": """
            CREATE TABLE IF NOT EXISTS sectors (
                id UTINYINT PRIMARY KEY,
                name VARCHAR UNIQUE
            )
        """,
    },
    "tickers": {
        "description": "Master list of stock tickers with normalized metadata.",
        "version": 2,
        "shard": "master",
        "sql": """
            CREATE TABLE IF NOT EXISTS tickers (
                code VARCHAR PRIMARY KEY,
                name VARCHAR,
                market_section_id UTINYINT,
                sector_id UTINYINT,
                last_session_id VARCHAR
            )
        """,
    },
    "company_facts": {
        "description": "Financial statements with optimized storage types.",
        "version": 2,
        "shard": "financials",
        "sql": """
            CREATE TABLE IF NOT EXISTS company_facts (
                DisclosedDate DATE,
                DisclosedTime VARCHAR,
                LocalCode VARCHAR,
                DisclosureNumber VARCHAR,
                Type VARCHAR,
                FiscalYear VARCHAR,
                FiscalPeriod VARCHAR,
                NetSales DECIMAL(18, 1),
                OperatingProfit DECIMAL(18, 1),
                OrdinaryProfit DECIMAL(18, 1),
                Profit DECIMAL(18, 1),
                EarningsPerShare DECIMAL(12, 2),
                TotalAssets DECIMAL(18, 1),
                NetAssets DECIMAL(18, 1),
                EquityToAssetRatio DECIMAL(6, 3),
                BookValuePerShare DECIMAL(12, 2),
                CashFlowsFromOperatingActivities DECIMAL(18, 1),
                CashFlowsFromInvestingActivities DECIMAL(18, 1),
                CashFlowsFromFinancingActivities DECIMAL(18, 1),
                CashAndCashEquivalents DECIMAL(18, 1),
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (LocalCode, DisclosedDate, DisclosureNumber)
            )
        """,
    },
    "daily_prices": {
        "description": "Daily OHLCV data with high-precision storage.",
        "version": 3,
        "shard": "prices",
        "sql": """
            CREATE TABLE IF NOT EXISTS daily_prices (
                Date DATE,
                Code VARCHAR,
                Open DECIMAL(18, 1),
                High DECIMAL(18, 1),
                Low DECIMAL(18, 1),
                Close DECIMAL(18, 1),
                Volume BIGINT,
                AdjustmentOpen DECIMAL(18, 1),
                AdjustmentHigh DECIMAL(18, 1),
                AdjustmentLow DECIMAL(18, 1),
                AdjustmentClose DECIMAL(18, 1),
                AdjustmentVolume BIGINT,
                TurnoverValue DECIMAL(18, 1),
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (Code, Date)
            )
        """,
    },
    "daily_indices": {
        "description": "Daily market index quotes.",
        "version": 1,
        "shard": "master",
        "sql": """
            CREATE TABLE IF NOT EXISTS daily_indices (
                Date DATE,
                Code VARCHAR,
                Open DECIMAL(12, 1),
                High DECIMAL(12, 1),
                Low DECIMAL(12, 1),
                Close DECIMAL(12, 1),
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (Code, Date)
            )
        """,
    },
    "dividends": {
        "description": "Dividend payment records.",
        "version": 1,
        "shard": "financials",
        "sql": """
            CREATE TABLE IF NOT EXISTS dividends (
                AnnouncementDate DATE,
                Code VARCHAR,
                RecordDate DATE,
                DividendValue DECIMAL(12, 1),
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (Code, RecordDate, AnnouncementDate)
            )
        """,
    },
}

# Catalog Schema (for master.duckdb)
CATALOG_SCHEMA = {
    "shard_catalog": {
        "description": "Central catalog for managing multiple DuckDB shard files.",
        "version": 1,
        "sql": """
            CREATE TABLE IF NOT EXISTS shard_catalog (
                shard_name VARCHAR PRIMARY KEY,
                file_path VARCHAR,
                schema_version INTEGER,
                last_sync_at TIMESTAMP,
                status VARCHAR,
                records_count BIGINT DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
    }
}

INDEX_SCHEMAS = [
    "CREATE INDEX IF NOT EXISTS idx_jp_tickers_symbol ON tickers (code)",
    "CREATE INDEX IF NOT EXISTS idx_jp_facts_date ON company_facts (LocalCode, DisclosedDate)",
    "CREATE INDEX IF NOT EXISTS idx_jp_prices_date ON daily_prices (Code, Date)",
]

# Migration History Table (Internal)
MIGRATION_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS __migrations_history (
    table_name VARCHAR PRIMARY KEY,
    version INTEGER,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
