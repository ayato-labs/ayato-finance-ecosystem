# 🚀 Daily Stock Price Engine (2026 Edition)

A production-grade, high-performance financial data lake designed for the "Lean" investor. This engine synchronizes, cleans, and deduplicates the entire Japanese and US stock markets with extreme efficiency.

## 🌟 Key Features

- **Extreme Universe Coverage**: 
    - **Japan**: ~4,000 tickers via JPX Official.
    - **United States**: ~12,000 tickers via official NasdaqTrader directories.
- **High-Performance Architecture**:
    - **Storage**: Apache Parquet with Zstandard compression (Up to 90% space reduction).
    - **Analytics**: DuckDB-powered analytical views with automated deduplication.
    - **Concurrency**: Auto-scaling parallel sync (Optimized for Multi-core stability).
- **Hardened Testing**: 
    - 3-Tier Testing Architecture (Unit, Integration, System).
    - Chaos Testing (Resilience to DB locks and filesystem corruption).
- **Lean Philosophy**: 
    - Zero heavy dependencies. 
    - No expensive API keys required for market discovery.
    - 24-hour smart TTL caching for universe data.

## 🛠 Tech Stack

| Component | Technology |
| :--- | :--- |
| **Database** | SQLite (Metadata) + DuckDB (Analytics) + Parquet (Storage) |
| **API** | FastAPI + Uvicorn |
| **Logic** | Python 3.13 + Pandas + yfinance |
| **Test** | Pytest (Tiered Architecture) |

## 🚀 Quick Start

### 1. Installation
```powershell
uv pip install -e .
```

### 2. Synchronization
Sync specific tickers:
```powershell
uv run python main.py --sync AAPL 7203.T
```

Sync the entire US & Japan market:
```powershell
uv run python main.py --sync-market all
```

### 3. Start API Server
```powershell
uv run python main.py --api
```
Access the dashboard at `http://127.0.0.1:5005/`

### 4. Direct SQL Query
Run complex analytics against your local data lake:
```powershell
uv run python main.py --view AAPL --sql "SELECT Date, Close FROM {T} WHERE Close > 200"
```

## 🧪 Health & Resilience
The system is built to survive. To run the full health suite:
```powershell
uv run pytest tests/
```

---

> [!IMPORTANT]
> **Data Integrity**: This system uses a **Deduplication-on-Read** pattern. The raw Parquet files contain all history, while the `get_synced_view` logic ensures you only see the highest-fidelity, most recent record for any given Date/Ticker pair.
