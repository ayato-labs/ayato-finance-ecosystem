import io
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
    # Windows環境での文字化け対策 (UTF-8強制)
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except (AttributeError, io.UnsupportedOperation) as e:
            logger.debug(f"Encoding reconfiguration skipped: {e}")

    # 既存のハンドラをクリア
    logger.remove()

    log_level = os.getenv("LOG_LEVEL", "INFO")
    run_id = run_id or str(uuid.uuid4())[:8]

    # ログ保存先ディレクトリの作成
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 実行ごとに新しいログファイルを作成し、最新3回分のみ保持する設定
    log_file_pattern = log_dir / f"{unit_name}_{{time:YYYYMMDD_HHmmss}}.log"

    # 全ログに run_id を付与する設定
    logger.configure(extra={"run_id": run_id, "unit": unit_name})

    # 1. コンソール出力 (開発者用: 視認性重視)
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[run_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, format=console_format, level=log_level, colorize=True, enqueue=True)

    # 2. ファイル出力 (運用・分析用: 完全構造化JSON)
    # rotation="00:00" または 起動時ローテーション を模倣するため、常に新規ファイルを作成し、
    # retention=2 によって直近2回分のみを保持する。
    logger.add(
        str(log_file_pattern),
        level=log_level,
        serialize=True,     # JSON形式で出力
        enqueue=True,       # マルチプロセス安全
        rotation="1 day",   # またはファイルサイズ
        retention=2,        # 直近2世代のみ保持
        backtrace=True,
        diagnose=True,
    )

    # 3. エラーログの隔離保存 (重大な問題のみ)
    # Windowsのマルチプロセス環境でのPermissionErrorを防ぐため、
    # エラーログもユニットごとに分離して記録する。
    error_log_path = log_dir / f"error_{unit_name}.log"
    logger.add(
        str(error_log_path),
        level="ERROR",
        serialize=True,
        enqueue=True,
        rotation="10 MB",
        retention=5,
        backtrace=True,
        diagnose=True,
    )

    logger.info(
        f"Structured logging initialized | unit={unit_name} | run_id={run_id}"
    )
    return logger


def log_memory_usage(context: str = ""):
    """現在のプロセスのRAM使用量をログに出力する"""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    rss_mb = mem_info.rss / (1024 * 1024)
    logger.info(f"RAM Usage | context={context} | rss_mb={rss_mb:.2f}")
    return rss_mb
