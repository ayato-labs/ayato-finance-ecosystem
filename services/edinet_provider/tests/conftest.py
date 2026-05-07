import os
import pytest
from src.core.db import db_manager

# Ensure testing environment variable is set before any config imports
os.environ["TESTING"] = "true"


@pytest.fixture(autouse=True)
def reset_db_each_test():
    """
    Ensures each test starts with a fresh in-memory database
    to prevent cross-test contamination.
    """
    if os.getenv("MASTER_DB_PATH", ":memory:") == ":memory:":
        db_manager._reset_memory_db()
    yield


@pytest.fixture(scope="function")
def engine(reset_db_each_test):
    """
    Returns a fresh engine instance for each test.
    Depends on reset_db_each_test to ensure migrations run on a clean DB.
    """
    from src.engine import JPEDINETEngine

    return JPEDINETEngine()


@pytest.fixture(scope="session")
def db():
    """Shared database manager."""
    return db_manager
