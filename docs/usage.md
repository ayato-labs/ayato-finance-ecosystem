# Usage Guide

This guide covers the initial setup and daily operation of the ecosystem.

## 🛠️ Installation & Setup

### Prerequisites
- **Python 3.12+**
- **uv** (Package manager)
- **Node.js 18+** (For the Dashboard)

### Initial Ingestion
Before the dashboard can show data, you must sync the local databases:
1. Navigate to `daily_stock_price/` and run `run_sync.bat`.
2. Navigate to `Financial Figures/` and run `run_sync.bat`.

## 🔑 Environment Variables
Each module contains a `.env.example`. Copy these to `.env` and fill in your API keys:
- `JQUANTS_REFRESH_TOKEN`: Required for Japanese stock prices.
- `EDINET_API_KEY`: Required for statutory financials.
- `GEMINI_API_KEY`: Required for the AI-assisted ticker mapping.

## 🖥️ Launching the Ecosystem

Run the launcher at the project root:
```powershell
.\start_all_finance.bat
```
This will open 6 terminals:
1. **Asset Management Backend**: Port 5007
2. **Asset Management Frontend**: Port 5008
3. **Daily Stock Price**: Port 5005
4. **Financial Figures**: Port 5006
5. **Macro & Index API**: Port 5010
6. **Crypto Price API**: Port 5012

## 📊 Using the Dashboard
1. Open `http://localhost:5008`.
2. Navigate to the **"Add Transaction"** page to record your stock purchases.
3. The system will automatically calculate your **Alpha** and **Shadow Benchmark** performance.
