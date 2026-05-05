import os
import pytest

# Ensure testing environment variable is set before any config imports
os.environ["TESTING"] = "true"

from src.core.db import db_manager
from src.engine import JPEDINETEngine


@pytest.fixture(scope="session")
def engine():
    """Shared engine instance for testing."""
    return JPEDINETEngine()


@pytest.fixture(scope="session")
def db():
    """Shared database manager."""
    return db_manager
