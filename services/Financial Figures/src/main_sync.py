import argparse

from dotenv import load_dotenv
from loguru import logger

from src.core.audit_manager import audit_manager
from src.core.logging import setup_logging
from src.services.market_sync import BatchSyncService

# Initialize logging
setup_logging()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Financial Figures Data Accumulation Runner")
    parser.add_argument(
        "--market",
        type=str,
        choices=["US", "JP", "BOTH"],
        default="BOTH",
        help="Market to sync",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Number of tickers per market (Default: None/Full)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Perform a dry run without saving data"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=True,
        help="Only sync tickers not updated recently",
    )
    parser.add_argument(
        "--no-incremental", action="store_false", dest="incremental", help="Force sync all tickers"
    )

    args = parser.parse_args()

    service = BatchSyncService()

    markets = ["US", "JP"] if args.market == "BOTH" else [args.market]

    limit_str = f"Limit: {args.limit}" if args.limit else "FULL MARKET"
    logger.info(f"=== Starting Data Accumulation Phase 2 ({limit_str} per market) ===")
    logger.info(f"Incremental Sync: {args.incremental}")

    for m in markets:
        try:
            logger.info(f"\n>>> SYNCING MARKET: {m}")
            service.sync_market_full(
                m, limit=args.limit, dry_run=args.dry_run, incremental=args.incremental
            )
            logger.info(f">>> COMPLETED MARKET: {m}")
        except Exception as e:
            logger.error(f"Failed to sync market {m}: {e}")

    logger.info("\n=== All Synchronization Tasks Completed ===")

    # Quick audit summary
    sync_stats = audit_manager.get_recent_sessions(limit=5)
    print("\n--- Recent Sync Sessions ---")
    for session in sync_stats:
        print(
            f"ID: {session.get('id')} | "
            f"Market: {session.get('market')} | "
            f"Status: {session.get('status')} | "
            f"Start: {session.get('start_time')}"
        )


if __name__ == "__main__":
    main()
