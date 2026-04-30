import argparse
import logging
import sys

from src.services.market_sync import BatchSyncService

# Setup basic logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("sync_all")


def main():
    parser = argparse.ArgumentParser(description="Financial Figures System-wide Synchronizer")
    parser.add_argument(
        "--market",
        type=str,
        choices=["US", "JP", "ALL"],
        default="ALL",
        help="Target market (US, JP, or ALL)",
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of tickers per market (for partial sync)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print tickers without fetching data"
    )

    args = parser.parse_args()

    sync_service = BatchSyncService()

    try:
        if args.market in ["US", "ALL"]:
            print(f"\n{'=' * 20} Syncing US Market {'=' * 20}")
            sync_service.sync_market_full("US", limit=args.limit, dry_run=args.dry_run)

        if args.market in ["JP", "ALL"]:
            print(f"\n{'=' * 20} Syncing JP Market {'=' * 20}")
            sync_service.sync_market_full("JP", limit=args.limit, dry_run=args.dry_run)

        print("\nSync completed successfully.")
    except KeyboardInterrupt:
        print("\nSync interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Sync process aborted: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
