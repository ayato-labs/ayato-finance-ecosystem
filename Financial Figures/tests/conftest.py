import duckdb
import pytest

from src.core.config import settings


@pytest.fixture(scope="function", autouse=True)
def test_settings(tmp_path):
    """Override settings for testing with a guaranteed absolute temp path."""
    import uuid

    suffix = uuid.uuid4().hex[:8]
    test_data_dir = tmp_path / "data"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    settings.DATA_DIR = test_data_dir
    settings.DB_PATH_US = test_data_dir / "markets" / f"us_{suffix}.duckdb"
    settings.DB_PATH_JP = test_data_dir / "markets" / f"jp_{suffix}.duckdb"
    settings.DB_PATH_TRACEABILITY = test_data_dir / "audit" / f"traceability_{suffix}.duckdb"

    settings.DB_PATH_US.parent.mkdir(parents=True, exist_ok=True)
    settings.DB_PATH_TRACEABILITY.parent.mkdir(parents=True, exist_ok=True)

    # Update the global audit_manager instance to use the new path
    from src.core.audit_manager import audit_manager

    audit_manager._db_path_override = settings.DB_PATH_TRACEABILITY
    audit_manager._init_db()

    return settings


@pytest.fixture
def db_conn():
    """Provides a clean in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()
