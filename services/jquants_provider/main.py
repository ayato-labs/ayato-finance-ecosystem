import argparse
import sys
from loguru import logger
from src.core.logging import setup_logger
from src.engine import JPEngine

def main():
    parser = argparse.ArgumentParser(description="J-Quants Data Provider CLI")
    parser.add_argument("--sync-tickers", action="store_true", help="Sync listed company info")
    parser.add_argument("--sync-all", action="store_true", help="Sync statements for all tickers")
    parser.add_argument("--ticker", type=str, help="Sync specific ticker")
    
    args = parser.parse_args()
    setup_logger(log_dir="logs", app_name="jquants_provider")
    
    try:
        engine = JPEngine()
        
        if args.sync_tickers:
            engine.sync_tickers()
            
        if args.ticker:
            df = engine.fetch_statements(args.ticker)
            if not df.empty:
                engine.ingest_facts(args.ticker, df, "manual-sync")
                logger.success(f"Successfully synced {args.ticker}")
                
        if args.sync_all:
            # Get all tickers from DB
            import duckdb
            from src.engine import DuckDBManager
            with DuckDBManager.connect(engine.db_path) as conn:
                tickers = conn.execute("SELECT code FROM tickers").fetchall()
                tickers = [t[0] for t in tickers]
            
            logger.info(f"Syncing {len(tickers)} tickers...")
            for t in tickers:
                try:
                    df = engine.fetch_statements(t)
                    if not df.empty:
                        engine.ingest_facts(t, df, "auto-sync")
                except Exception:
                    logger.warning(f"Failed to sync {t}")
                    continue
                    
        if not any([args.sync_tickers, args.ticker, args.sync_all]):
            parser.print_help()

    except Exception:
        logger.exception("Critical error in J-Quants provider")
        sys.exit(1)

if __name__ == "__main__":
    main()
