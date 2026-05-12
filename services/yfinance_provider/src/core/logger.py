import os
import sys

from loguru import logger

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logger(service_name: str):
    # すでに設定済みの場合は既存のロガーを返す
    # loguruの内部状態をチェックし、ハンドラーが追加済みならスキップ
    if len(logger._core.handlers) > 0:
        return logger

    logger.remove()

    # 1. コンソール出力 (標準エラー)
    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, level="INFO", colorize=True, format=fmt)

    # 2. 実行ログ (JSON, 2世代/2実行分保持)
    # {time} を含めることで起動ごとにファイルが分かれ、retention=2で2世代管理される
    logger.add(
        os.path.join(LOG_DIR, f"{service_name}_{{time}}.json.log"),
        level="DEBUG",
        serialize=True,
        retention=2,
    )

    # 3. エラー隔離ログ (error.log)
    # 累積的に記録しつつ、エラーのみを抽出
    logger.add(
        os.path.join(LOG_DIR, "error.log"),
        level="ERROR",
        serialize=True,
        backtrace=True,
        diagnose=True,
    )

    return logger
