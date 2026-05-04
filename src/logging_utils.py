import io
import sys
from pathlib import Path

from loguru import logger

from src.config import LOG_LEVEL


def setup_logging(name: str):
    """
    ロギングのセットアップ
    - logs/{name}.log に保存
    - コンソールに出力 (Windows環境での文字化け防止のためUTF-8を強制)
    """
    # Windows環境での文字化け対策: 標準出力と標準エラーをUTF-8に設定
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_path = log_dir / f"{name}.log"

    # 既存のハンドラをクリア（二重出力を防ぐ）
    logger.remove()

    # ファイル出力 (JSONフォーマット)
    logger.add(
        log_path,
        rotation="10 MB",
        retention="1 week",
        level=LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        encoding="utf-8",
    )

    # コンソール出力 (カラー)
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    logger.info(f"Logging initialized for {name} (level: {LOG_LEVEL}, file: {log_path})")
