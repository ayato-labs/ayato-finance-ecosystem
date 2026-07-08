import os
from pathlib import Path

# Resolve project root (finance/)
# This file is in services/yfinance_provider/src/core/config.py
PROJECT_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "yfinance" / "yfinance.duckdb"
DEFAULT_UNIVERSE_CACHE = PROJECT_ROOT / "data" / "yfinance" / "universe"


def get_db_path() -> str:
    """Returns the database path, allowing environment override."""
    path = os.getenv("YFINANCE_DB_PATH")
    if path:
        return path

    # Ensure parent directory exists
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return str(DEFAULT_DB_PATH)


def get_universe_cache_dir() -> str:
    """Returns the universe cache directory."""
    # Ensure directory exists
    DEFAULT_UNIVERSE_CACHE.mkdir(parents=True, exist_ok=True)
    return str(DEFAULT_UNIVERSE_CACHE)
