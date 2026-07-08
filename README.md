# Ayato Finance Ecosystem 📈

**A high-performance, local-first financial data ecosystem for professional market analysis and portfolio management.**

## 🎯 Target Audience
- **Quantitative Researchers**: Who need zero-latency local access to normalized financial datasets.
- **Fintech Developers**: Looking for a modular, microservice-based architecture to build financial products.
- **Serious Individual Investors**: Who want institutional-grade benchmarking ("Shadow Portfolios") without expensive SaaS subscriptions.

## 💡 Problems We Solve
Financial analysis is often slowed down by fragmented APIs, high cloud costs, and the "emotional noise" of market volatility. Ayato solves this by:
1. **Unifying Data**: Seamlessly integrating stock prices, statutory financials (EDINET), and macro indicators into a single SQL interface (DuckDB).
2. **Eliminating Latency**: A "Local-First" architecture that processes millions of rows in milliseconds on your own machine.
3. **Rational Decision Making**: Providing real-time Alpha analysis and Shadow Benchmarking to keep investment decisions grounded in data, not emotions.

## 🏗️ Architecture & Docs
This is a **Monorepo** of decoupled services. For detailed design decisions and system limits, see:
- **[Architecture & Philosophy](./docs/architecture.md)** (Mandatory Reading)
- **[Quick Start & Usage](./docs/usage.md)**
- **[Operational Guide](./docs/operations.md)**

### Data Providers (under services/):
- **[yfinance_provider](./services/yfinance_provider)**: Historical prices, index benchmarks, cryptocurrency rates, forex rates, and qualitative corporate profiles.
- **[fred_provider](./services/fred_provider)**: Macroeconomic data indicators, treasury yields, and federal interest rates from FRED.
- **[edinet_provider](./services/edinet_provider)**: Statutory figures and corporate financial statements (FSA XBRL).
- **[edgar_provider](./services/edgar_provider)**: US statutory reporting data (SEC XBRL).
- **[jquants_provider](./services/jquants_provider)**: Quantitative market and trading data for Japanese equities.

## 🚀 Getting Started

1. Clone the repository.
2. Run `start_all_finance.bat` (Windows) to launch the ecosystem.
3. Access the dashboard at `http://localhost:5008`.

## ⚖️ Licensing & Commercial Use

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. 

**For commercial use, corporate deployment, or proprietary integrations, a Commercial License is required.**

- **[COMMERCIAL.md](./COMMERCIAL.md)**: Pricing, terms, and contact information.
- **[CONTRIBUTING.md](./CONTRIBUTING.md)**: Rules for contributing code and the mandatory CLA process.

---
*An open-source infrastructure for the next generation of financial intelligence.*
