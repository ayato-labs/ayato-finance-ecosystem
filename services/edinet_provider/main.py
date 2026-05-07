import argparse
import sys
import subprocess
from loguru import logger
from src.infra.logging_config import setup_logging


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="EDINET Provider - Unified Entry Point")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Ingest Command
    ingest_parser = subparsers.add_parser("ingest", help="Run ingestion CLI")
    ingest_parser.add_argument("--ticker", type=str, help="Sync specific JP ticker")
    ingest_parser.add_argument("--days", type=int, default=30, help="Days to look back")
    ingest_parser.add_argument("--market", action="store_true", help="Sync full market")
    ingest_parser.add_argument("--backfill", action="store_true", help="Run backfill")

    # API Command
    api_parser = subparsers.add_parser("api", help="Start API server")
    api_parser.add_argument("--port", type=int, default=5009)
    api_parser.add_argument("--host", type=str, default="0.0.0.0")

    args, unknown = parser.parse_known_args()

    if args.command == "ingest":
        # Forward to ingestion CLI
        from src.apps.ingestion.cli import main as ingestion_main

        sys.argv = [sys.argv[0]] + unknown
        if args.ticker:
            sys.argv.extend(["--ticker", args.ticker])
        if args.days:
            sys.argv.extend(["--days", str(args.days)])
        if args.market:
            sys.argv.append("--market")
        if args.backfill:
            sys.argv.append("--backfill")
        ingestion_main()

    elif args.command == "api":
        logger.info(f"Starting API server on {args.host}:{args.port}...")
        try:
            subprocess.run(
                [
                    "uvicorn",
                    "src.apps.api.server:app",
                    "--host",
                    args.host,
                    "--port",
                    str(args.port),
                    "--reload",
                ]
            )
        except KeyboardInterrupt:
            logger.info("API server stopped.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
