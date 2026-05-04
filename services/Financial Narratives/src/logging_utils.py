import os
import sys
import uuid
from pathlib import Path

import psutil
from loguru import logger


def setup_logging(unit_name: str, run_id: str | None = None):
    """
    コンポーネントごとのロギング構成を初期化する。
    - コンソール: 色付き標準出力
    - ファイル: logs/{unit_name}.log (JSON形式)
    
    Args:
        unit_name: ログファイル名に使用する名前
        run_id: 実行セッションを識別するID。未指定時は新規生成。
    """
    # 既存のハンドラをクリア
    logger.remove()

    log_level = os.getenv("LOG_LEVEL", "INFO")
    run_id = run_id or str(uuid.uuid4())[:8]

    # ログ保存先ディレクトリの作成
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{unit_name}.log"

    # 全ログに run_id を付与する設定
    logger.configure(extra={"run_id": run_id, "unit": unit_name})

    # 1. コンソール出力 (人間用)
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[run_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, format=console_format, level=log_level, colorize=True, enqueue=True)

    # 2. ファイル出力 (JSON / 構造化ログ)
    # serialize=True にすると、ログの全項目がJSON形式で出力される
    logger.add(
        str(log_file),
        format="{message}",
        level=log_level,
        rotation="100 MB",
        retention="7 days",
        serialize=True,
        enqueue=True,
    )

    logger.info(f"Logging initialized | unit={unit_name} | run_id={run_id} | log_file={log_file}")
    return logger


def log_memory_usage(context: str = ""):
    """現在のプロセスのRAM使用量をログに出力する"""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    rss_mb = mem_info.rss / (1024 * 1024)
    logger.info(f"RAM Usage | context={context} | rss_mb={rss_mb:.2f}")
    return rss_mb
