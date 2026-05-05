import sys
from pathlib import Path
from loguru import logger

# ログディレクトリの設定
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 既存のハンドラを削除
logger.remove()

# 標準出力用の設定
log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)
logger.add(sys.stdout, format=log_format)

# 通常のログファイルの設定（直近2回分）
logger.add(
    LOG_DIR / "app.log",
    rotation="2",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    serialize=True,
)

# エラーログの隔離保存の設定
logger.add(
    LOG_DIR / "error.log",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    serialize=True,
)


def get_logger():
    return logger
