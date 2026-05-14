import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir="logs", service_name="edinet_provider"):
    """
    Setup Loguru with JSON structured logging.
    - Retention: Keeps current run and .prev run only (2-run cycle).
    - Error Isolation: ERROR level logs are duplicated to an isolated error.log.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    logger.remove()
    
    main_log = log_path / f"{service_name}.jsonl"
    error_log = log_path / "error.log"

    # Execution-based manual rotation (Keep last 2 runs: current and .prev)
    def rotate_log_cycle(target_path):
        try:
            if target_path.exists():
                suffix = ".prev.jsonl" if target_path.suffix == ".jsonl" else ".prev.log"
                prev_log = target_path.with_suffix(suffix)
                if prev_log.exists():
                    prev_log.unlink()
                target_path.rename(prev_log)
        except Exception as e:
            print(f"Warning: Failed to rotate {target_path.name}: {e}", file=sys.stderr)

    rotate_log_cycle(main_log)
    rotate_log_cycle(error_log)

    # 1. Main JSON Log (DEBUG and above)
    logger.add(
        str(main_log),
        serialize=True,
        level="DEBUG",
        backtrace=True,
        diagnose=True,
    )

    # 2. Isolated Error Log (ERROR and above)
    logger.add(
        str(error_log),
        serialize=True,
        level="ERROR",
        backtrace=True,
        diagnose=True,
    )

    # 3. Console (Human readable)
    log_format = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        format=log_format,
        level="INFO",
        colorize=True,
    )
    
    logger.info("Logging initialized: JSON structured and error isolation active (Retention=2).")
    return logger
