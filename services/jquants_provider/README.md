# J-Quants Provider

Standalone service for fetching and serving Japanese market data from J-Quants API.

## Features
- Ticker list synchronization.
- Financial statements (Figures) ingestion into DuckDB.
- FastAPI server for data access.

## Setup
1. Install dependencies:
   ```bash
   uv pip install -e .
   ```
2. Set environment variables in `.env`:
   - `JQUANTS_API_KEY` (V2) or `JQUANTS_REFRESH_TOKEN` (V1)

## Usage
- Sync tickers: `python main.py --sync-tickers`
- Sync specific ticker: `python main.py --ticker 7203`
- Start API: `python main.py --api --port 5007`
