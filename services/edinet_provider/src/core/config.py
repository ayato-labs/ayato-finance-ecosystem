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

    # Split Database Architecture (The Quad-Split with Master)
    @property
    def MASTER_DB_PATH(self) -> str | Path:
        """Single Source of Truth entry point."""
        if os.getenv("TESTING") == "true":
            return ":memory:"
        return self.DATA_DIR / "edinet_master.duckdb"

    @property
    def REGISTRY_DB_PATH(self) -> str | Path:
        """Metadata and Document Catalog storage."""
        if os.getenv("TESTING") == "true":
            return ":memory:"
        return self.DATA_DIR / "edinet_registry.duckdb"

    @property
    def FACTS_DB_PATH(self) -> str | Path:
        """Numerical financial data storage."""
        if os.getenv("TESTING") == "true":
            return ":memory:"
        return self.DATA_DIR / "edinet_facts.duckdb"

    @property
    def NARRATIVE_DB_PATH(self) -> str | Path:
        """Unstructured text data storage."""
        if os.getenv("TESTING") == "true":
            return ":memory:"
        return self.DATA_DIR / "edinet_narratives.duckdb"

    # API Configuration
    API_PORT: int = 5009

    # Performance & Storage
    DUCKDB_MEMORY_LIMIT: str = "4GB"
    ZSTD_COMPRESSION_LEVEL: int = 10

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
