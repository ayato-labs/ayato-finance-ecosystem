from pathlib import Path

import pytest

from src.core.config import settings


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """Creates a temporary data directory for testing."""
    tmp_dir = tmp_path_factory.mktemp("data")
    return tmp_dir

@pytest.fixture(scope="function")
def clean_db_paths(test_data_dir):
    """Returns fresh DB paths in the temp directory."""
    paths = {
        "master": test_data_dir / "test_master.duckdb",
        "facts": test_data_dir / "test_facts.duckdb",
        "narratives": test_data_dir / "test_narratives.duckdb"
    }
    # Ensure they don't exist
    for p in paths.values():
        if p.exists():
            p.unlink()
    return paths

@pytest.fixture(autouse=True)
def mock_settings_paths(monkeypatch, clean_db_paths):
    """Overwrites production paths with test paths as Path objects."""
    from src.core.master_db import master_db
    master_db._initialized = False  # Reset for each test to handle temp dirs correctly

    monkeypatch.setattr(settings, "MASTER_DB_PATH", Path(clean_db_paths["master"]))
    monkeypatch.setattr(settings, "FACTS_DB_PATH", Path(clean_db_paths["facts"]))
    monkeypatch.setattr(settings, "NARRATIVES_DB_PATH", Path(clean_db_paths["narratives"]))
    monkeypatch.setattr(settings, "DB_PATH", Path(clean_db_paths["facts"]))
    # Also ensure DATA_DIR points to our temp dir
    monkeypatch.setattr(settings, "DATA_DIR", Path(clean_db_paths["facts"]).parent)
