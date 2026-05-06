import sys
from loguru import logger

def setup_logging():
    # Remove default handler
    logger.remove()

    # App logs: JSON format, keep last 2 files
    logger.add(
        "logs/app.log",
        format="{message}",
        serialize=True,
        rotation="100 MB",
        retention=2,
        level="INFO"
    )

    # Error logs: Dedicated file for ERROR and above
    logger.add(
        "logs/error.log",
        format="{time} | {level} | {message} | {extra}",
        level="ERROR",
        backtrace=True,
        diagnose=True
    )

    # Console output for local development
    logger.add(sys.stderr, level="DEBUG")

    return logger
