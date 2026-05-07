import json
import sys
from pathlib import Path

from loguru import logger


def serialize(record):
    """recordオブジェクトをJSON文字列に変換する"""
    subset = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "file": record["file"].name,
        "line": record["line"],
        "extra": record["extra"],
    }
    if record["exception"]:
        subset["exception"] = record["exception"].format()
    return json.dumps(subset)


def json_formatter(record):
    """loguru用のJSONフォーマッター"""
    record["extra"]["serialized"] = serialize(record)
    return "{extra[serialized]}\n"


def rotate_logs(logs_dir: Path):
    """
    直近2回分の実行ログを保持する
    run_1.json (最新) -> run_2.json (前回)
    """
    run_1 = logs_dir / "run_1.json"
    run_2 = logs_dir / "run_2.json"

    if run_1.exists():
        if run_2.exists():
            run_2.unlink()
        run_1.rename(run_2)


def setup_logging():
    """
    構造化ログの設定
    - run_1.json: 最新の実行ログ (JSON)
    - error.log: 全エラーの隔離保存 (JSON)
    - stderr: 標準エラー出力 (通常のテキスト)
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    rotate_logs(logs_dir)

    # 既存のロガー設定をリセット
    logger.remove()

    # 1. 最新の実行ログ (JSON) - 直近2回ローテーションの片割れ
    logger.add(logs_dir / "run_1.json", format=json_formatter, level="DEBUG", encoding="utf-8")

    # 2. エラー隔離保存用 (JSON) - エラーのみを永続的に蓄積
    logger.add(logs_dir / "error.json", format=json_formatter, level="ERROR", encoding="utf-8")

    # 3. コンソール出力 (人間が読みやすい形式)
    log_format = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, format=log_format, level="INFO", colorize=True)

    logger.debug("Structured logging initialized.")
