import argparse
import asyncio
import os

from edgar_core import setup_logger, EdgarStorage
from .fetcher import EdgarFetcher
from .parser import EdgarParser
from .pipeline import sync_recent_us_filings, process_us_tickers, repair_all_missing_facts

def main():
    setup_logger(log_dir="logs", app_name="edgar_provider")

    parser = argparse.ArgumentParser(description="SEC EDGAR Provider CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync filings from daily index")
    sync_parser.add_argument("--days", type=int, default=1, help="Number of days to look back")

    # Ticker command
    ticker_parser = subparsers.add_parser("ticker", help="Sync filings for specific tickers")
    ticker_parser.add_argument("tickers", nargs="+", help="Tickers to sync")
    ticker_parser.add_argument("--days", type=int, default=365, help="History depth in days")

    # Repair command
    subparsers.add_parser("repair-facts", help="Repair all filings missing financial facts")

    # Stats command
    subparsers.add_parser("stats", help="Show database statistics")

    args = parser.parse_args()

    user_agent = os.environ.get(
        "USER_AGENT", "edgar-provider/1.0 (contact: admin@example.com)"
    )
    fetcher = EdgarFetcher(user_agent=user_agent)
    parser_obj = EdgarParser()
    storage = EdgarStorage()

    if args.command == "sync":
        asyncio.run(sync_recent_us_filings(fetcher, parser_obj, storage, days=args.days))
    elif args.command == "ticker":
        asyncio.run(process_us_tickers(args.tickers, fetcher, parser_obj, storage, days=args.days))
    elif args.command == "repair-facts":
        asyncio.run(repair_all_missing_facts(storage))
    elif args.command == "stats":
        stats = storage.get_stats()
        print(f"Total filings: {stats['total_filings']}")
        for s in stats["ticker_stats"]:
            print(f"- {s['ticker']}: {s['count']} filings (Latest: {s['latest_filing']})")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
