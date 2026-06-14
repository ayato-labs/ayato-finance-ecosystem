import os

import pytest

from src.datalake.shared.infra.config import settings
from src.datalake.shared.infra.db import db_manager


# Ensure testing environment variable is set before any config imports
os.environ["TESTING"] = "true"


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path):
    """
    Sets up a clean environment for each test, including a temporary DATA_DIR.
    """
    # Override DATA_DIR to a temporary path
    original_data_dir = settings.DATA_DIR
    settings.DATA_DIR = tmp_path / "data"
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

    from src.datalake.shared.infra.rate_limit import edinet_rate_limit
    edinet_rate_limit._backoff_until = 0.0
    edinet_rate_limit._last_request_time = 0.0

    if os.getenv("MASTER_DB_PATH", ":memory:") == ":memory:":
        db_manager._reset_memory_db()

    yield

    settings.DATA_DIR = original_data_dir


@pytest.fixture(scope="function")
def engine():
    """
    Returns a fresh engine instance for each test.
    """
    from src.datalake.engine import JPEDINETEngine

    return JPEDINETEngine()


@pytest.fixture(scope="session")
def db():
    """Shared database manager."""
    return db_manager
