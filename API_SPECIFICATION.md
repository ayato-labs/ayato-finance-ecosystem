# Ayato Finance Ecosystem - API Specification 📈

This document provides a comprehensive overview of the APIs within the Ayato Finance Ecosystem. All services are built with Python (FastAPI/DuckDB) and are designed to run locally.

## 🚀 Ecosystem Overview

| Service Name | Port | Base URL | Primary Role |
| :--- | :--- | :--- | :--- |
| **Stock Price API** | 5005 | `http://localhost:5005` | US/JP OHLCV market data |
| **Financial Figures** | 5006 | `http://localhost:5006` | Standardized Financial Statements |
| **Asset Backend** | 5007 | `http://localhost:5007` | Portfolio aggregation & Alpha analysis |
| **Market Index API** | 5009 | `http://localhost:5009` | Global benchmarks (S&P 500, Nikkei 225) |
| **Macro Economic API** | 5010 | `http://localhost:5010` | Treasury yields, Fed Funds rates |
| **Forex API** | 5011 | `http://localhost:5011` | Real-time & historical exchange rates |
| **Crypto Price API** | 5012 | `http://localhost:5012` | Cryptocurrency OHLCV & Metadata |
| **Narratives API** | 5013 | `http://localhost:5013` | SEC qualitative data extraction (MD&A, Risks) |

---

## 1. Stock Price API (5005)
High-performance market data access leveraging DuckDB and Parquet.
**[Data Contract: `DailyPriceRecord`]**

### Endpoints
- **`GET /status`**
  - Returns database metrics (ticker count, data volume).
- **`GET /prices/{ticker}`**
  - Query parameters: `start_date`, `end_date` (YYYY-MM-DD).
  - Retrieves deduplicated OHLCV history.
- **`POST /sync/{ticker}`**
  - Query parameters: `days` (lookback period).
  - Triggers incremental sync from Yahoo Finance.
- **`POST /query`**
  - Body: `{"sql": "...", "limit": 100}`
  - Executes raw analytical SQL against the data lake. Use `{T}` to reference the parquet files.

---

## 2. Financial Figures API (5006)
Standardized financial database for US (SEC) and JP (EDINET) companies.
**[Data Contract: `FinancialFiguresRecord`]**

### Endpoints
- **`GET /tickers`**
  - Query parameters: `market` (US/JP), `search` (name/symbol), `limit`, `offset`.
  - Lists supported companies.
- **`GET /financials/{symbol}`**
  - Retrieves standardized financial facts (NetIncome, Revenue, etc.) mapped by AI logic.
- **`POST /sync`**
  - Triggers market-wide incremental sync.
- **`POST /sync/{symbol}`**
  - Forces sync for a specific ticker.
- **`GET /stats`**
  - Returns counts of tickers and facts in the DB.

---

## 3. Asset Backend API (5007)
The central orchestration layer for the Dashboard. Aggregates data from all other APIs.

### Endpoints
- **`GET /portfolio`**
  - Query parameters: `currency` (Default: JPY).
  - Returns full portfolio summary:
    - **Shadow Benchmark**: Real-time performance vs S&P 500 (matched to purchase dates).
    - **Alpha**: Excess return over the benchmark.
    - **Risk Metrics**: Sharpe Ratio, Volatility, Max Drawdown, Beta, Correlation.
    - **Macro Data**: Integrated 10Y Yields.
- **`GET /transactions`**
  - Lists all recorded trades.
- **`POST /transactions`**
  - Adds a new trade (Buy/Sell).
- **`PUT /transactions/{tx_id}`** / **`DELETE /transactions/{tx_id}`**
  - Manages existing transaction records.

---

## 4. Market Index API (5009)
Dedicated service for tracking global benchmarks.

### Endpoints
- **`GET /prices/{ticker}`**
  - Retrieves historical data for indices like `^GSPC` (S&P 500) or `^N225`.
- **`POST /sync/{ticker}`**
  - Synchronizes index data from Yahoo Finance.

---

## 5. Macro Economic API (5010)
Tracks critical economic indicators from FRED.
**[Data Contract: `MacroIndicatorRecord`]**

### Endpoints
- **`GET /indicators/{symbol}`**
  - Retrieves macro data for symbols like `DGS10` (10Y Yield) or `DFF` (Fed Funds Rate).
- **`POST /sync/{symbol}`**
  - Fetches latest data from FRED API.

---

## 6. Forex API (5011)
Historical and latest exchange rates against the USD hub.

### Endpoints
- **`GET /rates/{symbol}`**
  - Historical rate (1 Unit of Currency = X USD).
- **`GET /latest/{symbol}`**
  - Most recent exchange rate.
- **`POST /sync/{symbol}`**
  - Updates rate data.

---

## 7. Crypto Price API (5012)
Cryptocurrency market data and metadata.

### Endpoints
- **`GET /prices/{ticker}`**
  - Query parameters: `sync` (bool).
  - Returns OHLCV and metadata (Market Cap, Supply). Standardizes `-USD` tickers.

---

## 8. Financial Narratives API (5013)
SEC Qualitative data (MD&A, Risk Factors) extraction service.

### Endpoints
- **`GET /narratives/{ticker}`**
  - Retrieves raw extracted sections from SEC filings.
- **`POST /sync/{ticker}`**
  - Downloads latest SEC filings and parses them for qualitative sections.

---

## 🛠️ Usage Notes
- **Internal Integration**: Each service is decoupled. The Asset Backend (5007) is the primary client for other APIs.
- **Documentation**: Access Interactive Swagger UI at `http://localhost:<PORT>/docs` for any service.
- **Authentication**: Current local-first deployment uses open CORS and no auth for convenience.
