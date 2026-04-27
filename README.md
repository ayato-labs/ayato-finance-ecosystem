# Ayato Finance Ecosystem 📈

A high-performance, local-first financial data ecosystem built with Python, DuckDB, and Next.js. This project provides a modular infrastructure for professional-grade stock market analysis, macro-economic tracking, and portfolio management.

## 🏗️ Architecture

This is a **Monorepo** consisting of decoupled micro-services, each specialized in a specific financial domain:

- **[Asset Management App](./asset%20management%20App)**: Next.js + FastAPI dashboard for real-time portfolio tracking and risk analysis (Sharpe Ratio, Volatility, Max Drawdown).
- **[Daily Stock Price](./daily_stock_price)**: High-speed ingestion engine for historical and daily OHLCV data.
- **[Financial Figures](./Financial%20Figures)**: Statutory financial reporting (Income Statement, Balance Sheet, Cash Flow) tracking.
- **[Market Index API](./index)**: Dedicated service for tracking global benchmarks like S&P 500 and Nikkei 225.
- **[Macro Economic API](./macro)**: Tracks critical economic indicators such as 10Y Treasury Yields and Fed Funds Rates.

## 🌟 Flagship Features

### Shadow Benchmark & Alpha Analysis
Stay rational in any market. This ecosystem calculates a **"Parallel Universe Portfolio"** in real-time, showing exactly what your returns would be if you had invested in market benchmarks (like the S&P 500) at the exact same time as your individual stock purchases.
- **Hyper-Accurate Benchmarking**: Uses OHLC average prices `(O+H+L+C)/4` for the benchmark simulation at the moment of every transaction.
- **True Alpha Tracking**: Instantly see your performance relative to the market at both the portfolio and individual asset level.
- **Emotional Intelligence**: Built as a psychological shield—seeing your relative outperformance prevents panic-selling during broader market corrections.

## 🚀 Key Features

- **Local-First Intelligence**: Uses DuckDB and Parquet for extremely fast local queries without expensive cloud database costs.
- **Decoupled Design**: Each service runs independently via its own API, allowing for modular updates and high resilience.
- **Pro-Grade Analytics**: Real-time risk-free rate integration from Macro APIs for precise risk-adjusted performance metrics.
- **Beautiful UI**: Modern glassmorphism dashboard for clear visual insight into your assets.

## 🛠️ Getting Started

1. Clone the repository.
2. Run `start_all_finance.bat` (Windows) to launch the entire ecosystem in 6 dedicated terminals.
3. Access the dashboard at `http://localhost:5008`.

## ⚖️ Licensing

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. 

### Commercial Licensing
For corporate use, closed-source integration, or custom support, we offer a **Commercial License**. Please contact the author for details.

---
Created by an IT Engineer for the next generation of financial analysis.
