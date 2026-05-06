import argparse
import time
from src.core.logging_config import setup_logging
from src.engine import JPEDINETEngine


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="EDINET Provider CLI")
    parser.add_argument("--ticker", type=str, help="Sync specific JP ticker (e.g. 7203)")
    parser.add_argument("--days", type=int, default=30, help="Days to look back")
    parser.add_argument("--api", action="store_true", help="Start API server")
    parser.add_argument("--port", type=int, default=5009)

    args = parser.parse_args()
    engine = JPEDINETEngine()

    if args.api:
        # To be implemented
        logger.info(f"API server starting on port {args.port}...")
        return

    session_id = f"edinet-sync-{int(time.time())}"

    if args.ticker:
        engine.sync_company(args.ticker, days=args.days, session_id=session_id)
        logger.info("Sync complete.")


if __name__ == "__main__":
    main()
