import sys
from pathlib import Path

from loguru import logger

def rotate_logs(logs_dir: Path):
    """実行のたびにログをローテーション (run_1.log -> run_2.log)"""
    run_1 = logs_dir / "run_1.log"
    run_2 = logs_dir / "run_2.log"
    if run_1.exists():
        if run_2.exists():
            run_2.unlink()
        run_1.rename(run_2)

def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    rotate_logs(logs_dir)
    
    # 既存のロガーをクリア
    logger.remove()
    
    # JSON構造化ログ (run_1.log)
    logger.add(
        logs_dir / "run_1.log",
        format="{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level} | {message} | {extra}",
        serialize=True,
        level="DEBUG"
    )
    
    # エラー隔離用 (error.log)
    logger.add(
        logs_dir / "error.log",
        format="{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level} | {message} | {extra}",
        serialize=True,
        level="ERROR"
    )
    
    # コンソール出力
    logger.add(sys.stderr, level="INFO")

    logger.debug("Logging initialized successfully.")
