# J-Quants Provider Database Schema Definition

> [!IMPORTANT]
> This document is automatically generated from `src/core/schema.py`. Do not edit manually.

## Overview
This project uses DuckDB for historical data storage. Sharding is supported, and all shards are tracked via a central master catalog.

## Table Definitions

### `tickers`
- **Version**: 1
- **Description**: Master list of stock tickers and market sections.

#### SQL Schema
```sql
CREATE TABLE IF NOT EXISTS tickers (
code VARCHAR PRIMARY KEY,
name VARCHAR,
market_section VARCHAR,
sector VARCHAR,
last_session_id VARCHAR
)
```

### `company_facts`
- **Version**: 1
- **Description**: Financial statements and summaries (Income statements, BS, etc.)

#### SQL Schema
```sql
CREATE TABLE IF NOT EXISTS company_facts (
DisclosedDate DATE,
DisclosedTime VARCHAR,
LocalCode VARCHAR,
DisclosureNumber VARCHAR,
Type VARCHAR,
FiscalYear VARCHAR,
FiscalPeriod VARCHAR,
NetSales DOUBLE,
OperatingProfit DOUBLE,
OrdinaryProfit DOUBLE,
Profit DOUBLE,
EarningsPerShare DOUBLE,
TotalAssets DOUBLE,
NetAssets DOUBLE,
Equity DOUBLE,
EquityToAssetRatio DOUBLE,
BookValuePerShare DOUBLE,
CashFlowsFromOperatingActivities DOUBLE,
CashFlowsFromInvestingActivities DOUBLE,
CashFlowsFromFinancingActivities DOUBLE,
CashAndCashEquivalents DOUBLE,
session_id VARCHAR,
ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (LocalCode, DisclosedDate, DisclosureNumber)
)
```

### `daily_prices`
- **Version**: 1
- **Description**: Daily OHLCV data for all listed stocks.

#### SQL Schema
```sql
CREATE TABLE IF NOT EXISTS daily_prices (
Date DATE,
Code VARCHAR,
Open DOUBLE,
High DOUBLE,
Low DOUBLE,
Close DOUBLE,
Volume DOUBLE,
AdjustmentOpen DOUBLE,
AdjustmentHigh DOUBLE,
AdjustmentLow DOUBLE,
AdjustmentClose DOUBLE,
AdjustmentVolume DOUBLE,
TurnoverValue DOUBLE,
session_id VARCHAR,
ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (Code, Date)
)
```

### `daily_indices`
- **Version**: 1
- **Description**: Daily quotes for market indices (TOPIX, Nikkei 225, etc.)

#### SQL Schema
```sql
CREATE TABLE IF NOT EXISTS daily_indices (
Date DATE,
Code VARCHAR,
Open DOUBLE,
High DOUBLE,
Low DOUBLE,
Close DOUBLE,
session_id VARCHAR,
ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (Code, Date)
)
```

### `dividends`
- **Version**: 1
- **Description**: Historical dividend announcement and record dates.

#### SQL Schema
```sql
CREATE TABLE IF NOT EXISTS dividends (
AnnouncementDate DATE,
Code VARCHAR,
RecordDate DATE,
DividendValue DOUBLE,
session_id VARCHAR,
ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (Code, RecordDate, AnnouncementDate)
)
```

### `shard_catalog`
- **Version**: 1
- **Description**: Central catalog for managing multiple DuckDB shard files.

#### SQL Schema
```sql
CREATE TABLE IF NOT EXISTS shard_catalog (
shard_name VARCHAR PRIMARY KEY,
file_path VARCHAR,
schema_version INTEGER,
last_sync_at TIMESTAMP,
status VARCHAR,
records_count BIGINT DEFAULT 0,
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## Indices
The following indices are applied to optimize query performance:
```sql
CREATE INDEX IF NOT EXISTS idx_jp_tickers_symbol ON tickers (code)
CREATE INDEX IF NOT EXISTS idx_jp_facts_date ON company_facts (LocalCode, DisclosedDate)
CREATE INDEX IF NOT EXISTS idx_jp_prices_date ON daily_prices (Code, Date)
CREATE INDEX IF NOT EXISTS idx_jp_indices_date ON daily_indices (Code, Date)
```