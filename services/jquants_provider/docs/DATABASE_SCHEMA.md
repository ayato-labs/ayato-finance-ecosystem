# Database Schema Documentation

*This document is automatically generated from the Schema-as-Code definition in `src/core/schema.py`.*

## Table of Contents
- [market_sections](#market-sections)
- [sectors](#sectors)
- [tickers](#tickers)
- [company_facts](#company-facts)
- [daily_prices](#daily-prices)
- [daily_indices](#daily-indices)
- [dividends](#dividends)

---

## market_sections

**Description:** Normalized market section names (Prime, Standard, etc.)

**Shard:** `master`

**Version:** 2

### Columns
| Column | Description |
| --- | --- |
| id | Internal ID for market section |
| name | Full name of the market section (e.g., Prime, Standard) |

### SQL Definition
```sql
CREATE TABLE IF NOT EXISTS market_sections (
                id UTINYINT PRIMARY KEY,
                name VARCHAR UNIQUE
            )
```

---

## sectors

**Description:** Normalized sector names (Electronics, Banking, etc.)

**Shard:** `master`

**Version:** 2

### Columns
| Column | Description |
| --- | --- |
| id | Internal ID for sector |
| name | Full name of the sector classification |

### SQL Definition
```sql
CREATE TABLE IF NOT EXISTS sectors (
                id UTINYINT PRIMARY KEY,
                name VARCHAR UNIQUE
            )
```

---

## tickers

**Description:** Master list of stock tickers with normalized metadata.

**Shard:** `master`

**Version:** 2

### SQL Definition
```sql
CREATE TABLE IF NOT EXISTS tickers (
                code VARCHAR PRIMARY KEY,
                name VARCHAR,
                market_section_id UTINYINT,
                sector_id UTINYINT,
                last_session_id VARCHAR
            )
```

---

## company_facts

**Description:** Financial statements with optimized storage types.

**Shard:** `financials`

**Version:** 2

### SQL Definition
```sql
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
```

---

## daily_prices

**Description:** Daily OHLCV data with high-precision storage.

**Shard:** `prices`

**Version:** 3

### Columns
| Column | Description |
| --- | --- |
| Date | Trading date |
| Code | Ticker symbol |
| Open/High/Low/Close | Stock prices (Adjusted/Unadjusted) |
| Volume | Trading volume (shares) |
| TurnoverValue | Total turnover in JPY |
| AdjustmentFactor | Cumulative adjustment factor |

### SQL Definition
```sql
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
```

---

## daily_indices

**Description:** Daily market index quotes.

**Shard:** `master`

**Version:** 1

### SQL Definition
```sql
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
```

---

## dividends

**Description:** Dividend payment records.

**Shard:** `financials`

**Version:** 1

### SQL Definition
```sql
CREATE TABLE IF NOT EXISTS dividends (
                AnnouncementDate DATE,
                Code VARCHAR,
                RecordDate DATE,
                DividendValue DECIMAL(12, 1),
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (Code, RecordDate, AnnouncementDate)
            )
```

---

## Catalog Manager (master.duckdb)

### shard_catalog

Central catalog for managing multiple DuckDB shard files.

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