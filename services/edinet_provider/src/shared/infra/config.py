import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings and configuration.
    Values are loaded from environment variables or .env file.
    """

    # EDINET API Requirements
    EDINET_API_KEY: str = ""

    # Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"

    # Split Database Architecture (The Quad-Split with Master)
    @property
    def MASTER_DB_PATH(self) -> str | Path:
        """Single Source of Truth entry point."""
        env_val = os.getenv("MASTER_DB_PATH")
        if env_val:
            return env_val
        if os.getenv("TESTING") == "true":
            return ":memory:"
        return self.DATA_DIR / "edinet_master.duckdb"

    @property
    def REGISTRY_DB_PATH(self) -> str | Path:
        """Metadata and Document Catalog storage."""
        env_val = os.getenv("REGISTRY_DB_PATH")
        if env_val:
            return env_val
        if os.getenv("TESTING") == "true":
            return ":memory:"
        return self.DATA_DIR / "edinet_registry.duckdb"

    @property
    def FACTS_DB_PATH(self) -> str | Path:
        """Numerical financial data storage."""
        env_val = os.getenv("FACTS_DB_PATH")
        if env_val:
            return env_val
        if os.getenv("TESTING") == "true":
            return ":memory:"
        return self.DATA_DIR / "edinet_facts.duckdb"

    @property
    def NARRATIVE_DB_PATH(self) -> str | Path:
        """Unstructured text data storage."""
        env_val = os.getenv("NARRATIVE_DB_PATH")
        if env_val:
            return env_val
        if os.getenv("TESTING") == "true":
            return ":memory:"
        return self.DATA_DIR / "edinet_narratives.duckdb"

    # API Configuration
    API_PORT: int = 5009

    # Performance & Storage
    MEM_LIMIT_RATIO: float = 0.3  # Ratio of system RAM for DuckDB and Python process
    MEM_CRITICAL_THRESHOLD: float = 0.95  # Stop all ingestion if system RAM usage exceeds this
    MEM_CHECK_INTERVAL: int = 5  # Seconds between memory pressure checks
    ZSTD_COMPRESSION_LEVEL: int = 10

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
