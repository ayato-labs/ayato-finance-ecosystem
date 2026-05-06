import asyncio
import os
from src.batch_fetch import batch_fetch
from src.storage import FinancialNarrativeStorage

async def main():
    # Set environment variables from what we found
    os.environ["GOOGLE_API_KEY"] = "AIzaSyCVY39ROTOxZKcSWheahJjQ1Xi1UuNTY7U"
    user_agent = "MyFinancialApp-Demo user@example.com"
    
    ticker = "NVDA"
    logger_info = f"Running E2E for {ticker}..."
    print(logger_info)
    
    # 1. Fetch and Sync
    await batch_fetch([ticker], run_analysis=True)
    
    # 2. Check Results
    storage = FinancialNarrativeStorage()
    analysis = storage.get_analysis_by_ticker(ticker)
    
    if analysis:
        print("\n=== Analysis Result ===")
        print(f"Ticker: {analysis[0][1]}")
        print(f"Capex Summary: {analysis[0][2]}")
        print(f"R&D Summary: {analysis[0][3]}")
        print(f"Governance: {analysis[0][4]}")
        print(f"Sentiment: {analysis[0][6]}")
    else:
        print("\nNo analysis found in DB.")

if __name__ == "__main__":
    asyncio.run(main())
