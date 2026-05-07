import os
import pytest
from src.infra.db import db_manager
from src.infra.config import settings

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
    
    if os.getenv("MASTER_DB_PATH", ":memory:") == ":memory:":
        db_manager._reset_memory_db()
        
    yield
    
    settings.DATA_DIR = original_data_dir


@pytest.fixture(autouse=True)
def reset_db_each_test():
    # Deprecated in favor of setup_test_env, but keeping it if others depend on it
    pass


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
