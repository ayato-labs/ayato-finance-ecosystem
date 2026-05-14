import argparse
import time

from src.engine import JPEDINETEngine
from src.infra.logging_config import setup_logging


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="EDINET Ingestion CLI")
    parser.add_argument("--ticker", type=str, help="Sync specific JP ticker (e.g. 7203)")
    parser.add_argument("--days", type=int, default=30, help="Days to look back")
    parser.add_argument("--market", action="store_true", help="Sync full market")
    parser.add_argument("--backfill", action="store_true", help="Run backfill for missing data")
    parser.add_argument("--workers", type=int, default=5, help="Number of concurrent workers")

    args = parser.parse_args()
    engine = JPEDINETEngine()
    session_id = f"edinet-sync-{int(time.time())}"

    if args.backfill:
        engine.backfill_missing_data(max_workers=args.workers)
    elif args.market:
        engine.sync_market(days=args.days, session_id=session_id, max_workers=args.workers)
    elif args.ticker:
        engine.sync_company(
            args.ticker, days=args.days, session_id=session_id, max_workers=args.workers
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
