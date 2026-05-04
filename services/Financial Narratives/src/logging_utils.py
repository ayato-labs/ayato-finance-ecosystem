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

    # 実行ごとに新しいログファイルを作成し、最新3回分のみ保持する設定
    # {time} を含めることで、起動のたびに新しいファイルが生成される
    log_file_pattern = log_dir / f"{unit_name}_{{time:YYYYMMDD_HHmmss}}.log"

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
    # retention=2 により、最新の2ファイルのみを保持する
    logger.add(
        str(log_file_pattern),
        format="{message}",
        level=log_level,
        rotation="100 MB",
        retention=2,
        serialize=True,
        enqueue=True,
    )

    # 3. エラーログの隔離保存 (ERROR以上のみ)
    # 障害調査用に、エラーログは通常のログより長期間（10世代）保持する
    error_log_path = log_dir / "error.log"
    logger.add(
        str(error_log_path),
        format="{message}",
        level="ERROR",
        rotation="10 MB",
        retention=10,
        serialize=True,
        enqueue=True,
    )

    logger.info(
        f"Logging initialized | unit={unit_name} | run_id={run_id} | "
        f"pattern={log_file_pattern}"
    )
    return logger


def log_memory_usage(context: str = ""):
    """現在のプロセスのRAM使用量をログに出力する"""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    rss_mb = mem_info.rss / (1024 * 1024)
    logger.info(f"RAM Usage | context={context} | rss_mb={rss_mb:.2f}")
    return rss_mb
