from loguru import logger
from storage import FinancialNarrativeStorage
from batch_fetch import batch_fetch

def run_diagnostics():
    """DuckDB内のデータ状況を診断・表示する"""
    storage = FinancialNarrativeStorage()
    summary = storage.get_summary()
    
    if not summary:
        logger.warning("DuckDB is currently empty.")
        return

    print("\n" + "="*60)
    print(" FINANCIAL NARRATIVES - DATABASE DIAGNOSTICS")
    print("="*60)
    print(f"{'Ticker':<10} | {'Form':<8} | {'Filing Date':<12}")
    print("-" * 60)
    for row in summary:
        print(f"{row[0]:<10} | {row[1]:<8} | {str(row[2]):<12}")
    print("="*60 + "\n")

def main():
    # 1. データのバッチ取得（デモとして実行）
    logger.info("Starting financial narrative collection process...")
    batch_fetch()

    # 2. データベースの状況を確認
    run_diagnostics()

if __name__ == "__main__":
    main()
