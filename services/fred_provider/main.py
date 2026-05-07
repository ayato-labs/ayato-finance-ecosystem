import argparse
import threading

import duckdb
from dotenv import load_dotenv
from loguru import logger

from src.core.logging_config import setup_logging
from src.core.master_db_client import MasterDBClient
from src.ingestion.collector import FredCollector
from src.ingestion.writer import FredWriter

# .envの読み込み
load_dotenv()


def run_sync(symbols: list[str]):
    """シンクロナイゼーションプロセスの実行"""
    setup_logging()
    logger.info(f"Starting synchronization process for {len(symbols)} symbols.")

    try:
        collector = FredCollector()
        db_path = "data/fred.duckdb"
        writer = FredWriter(db_path)

        # 書込用スレッドの開始
        writer_thread = threading.Thread(
            target=writer.write_loop, args=(collector.data_queue,), daemon=True
        )
        writer_thread.start()

        # 収集の実行
        collector.run(symbols, "2024-01-01")

        # 完了待ち
        writer_thread.join(timeout=300)  # 5分のタイムアウト
        if writer_thread.is_alive():
            logger.warning("Writer thread did not finish within timeout.")

        # Master DBへの登録
        logger.info("Registering with Master DB...")
        conn = duckdb.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        conn.close()

        master_client = MasterDBClient()
        master_client.register_provider("fred_provider", db_path, "0.1.0", count)

        logger.info("Synchronization process completed successfully.")

    except Exception:
        logger.exception("Critical error during synchronization process")
        raise


def main():
    """エントリーポイント"""
    parser = argparse.ArgumentParser(description="FRED Provider CLI")
    subparsers = parser.add_subparsers(dest="command")

    # sync コマンド
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--symbols", nargs="+", default=["DFF", "UNRATE"])
    sync_parser.add_argument("--all-categories", action="store_true")

    # explore コマンド
    explore_parser = subparsers.add_parser("explore")
    explore_parser.add_argument("--category", type=int, required=True)

    args = parser.parse_args()

    if args.command == "sync":
        if args.all_categories:
            setup_logging()
            logger.info("All-categories sync requested. Discovering series from root...")
            try:
                collector = FredCollector()
                # ルートカテゴリー(0)からシリーズを探索
                symbols = collector.discover_series_by_category(0)
                if not symbols:
                    logger.warning("No symbols discovered in root category.")
                    return
                run_sync(symbols)
            except Exception:
                logger.exception("Failed to execute all-categories sync")
                sys.exit(1)
        else:
            run_sync(args.symbols)

    elif args.command == "explore":
        setup_logging()
        try:
            collector = FredCollector()
            series = collector.discover_series_by_category(args.category)
            print(f"Found {len(series)} series: {series}")
        except Exception:
            logger.exception(f"Failed to explore category {args.category}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    import sys

    main()
