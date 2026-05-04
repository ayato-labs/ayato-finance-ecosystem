import os
import sys
from pathlib import Path

import psutil
from loguru import logger


def setup_logging(unit_name: str):
    """
    コンポーネントごとのロギング構成を初期化する。
    - コンソール: 色付き標準出力
    - ファイル: logs/{unit_name}.log (JSON形式)
    """
    # 既存のハンドラをクリア
    logger.remove()

    log_level = os.getenv("LOG_LEVEL", "INFO")

    # ログ保存先ディレクトリの作成
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{unit_name}.log"

    # 1. コンソール出力 (人間用)
    # run_id があれば表示し、なければスキップするフォーマット
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level> "
        "| <magenta>{extra}</magenta>"
    )
    logger.add(sys.stderr, format=console_format, level=log_level, colorize=True, enqueue=True)

    # 2. ファイル出力 (JSON / 構造化ログ)
    # serialize=True にすると、ログの全項目がJSON形式で出力される
    logger.add(
        str(log_file),
        format="{message}",  # serialize=True の場合は format は無視される
        level=log_level,
        rotation="100 MB",
        retention="7 days",
        serialize=True,
        enqueue=True,
    )

    logger.info(f"Logging initialized for unit: {unit_name} -> {log_file}")
    return logger


def log_memory_usage(context: str = ""):
    """現在のプロセスのRAM使用量をログに出力する"""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    rss_mb = mem_info.rss / (1024 * 1024)
    logger.info(f"RAM Usage [{context}]: {rss_mb:.2f} MB")
    return rss_mb
