import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SEC EDGAR Requirements
    # Format: "Name <email@example.com>"
    SEC_IDENTITY: str = "FinancialAppAdmin <admin@example.com>"

    # Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    MASTER_DB_PATH: Path = DATA_DIR / "master.duckdb"
    FACTS_DB_PATH: Path = DATA_DIR / "facts.duckdb"
    NARRATIVES_DB_PATH: Path = DATA_DIR / "narratives.duckdb"
    # Legacy path for backward compatibility or temporary tasks
    DB_PATH: Path = FACTS_DB_PATH

    # API Configuration
    API_PORT: int = 5008

    # Performance & Storage
    DUCKDB_MEMORY_LIMIT: str = "2GB"
    DUCKDB_THREADS: int = 4
    ZSTD_COMPRESSION_LEVEL: int = 10

    @property
    def db_read_only(self) -> bool:
        return os.environ.get("DB_READ_ONLY", "false").lower() == "true"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
