import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SEC EDGAR Requirements
    SEC_IDENTITY: str = "FinancialAppAdmin <admin@example.com>"

    # Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    MASTER_DB_PATH: Path = DATA_DIR / "master.duckdb"
    FACTS_DB_PATH: Path = DATA_DIR / "facts.duckdb"
    NARRATIVES_DB_PATH: Path = DATA_DIR / "narratives.duckdb"
    DB_PATH: Path = FACTS_DB_PATH

    # API Configuration
    API_PORT: int = 5008

    # Performance & Storage (Defaults, can be overridden by ENV)
    # If not set in ENV, we calculate them dynamically
    DUCKDB_MEMORY_LIMIT: str | None = None
    DUCKDB_THREADS: int | None = None
    ZSTD_COMPRESSION_LEVEL: int = 10

    @property
    def db_memory_limit(self) -> str:
        if self.DUCKDB_MEMORY_LIMIT:
            return self.DUCKDB_MEMORY_LIMIT
        
        import psutil
        total_mem = psutil.virtual_memory().total
        # Use 40% of total RAM (leaving 60% for Python, OS, and buffers), minimum 2GB
        limit_gb = max(2, int((total_mem * 0.4) / (1024**3)))
        return f"{limit_gb}GB"

    @property
    def db_threads(self) -> int:
        if self.DUCKDB_THREADS:
            return self.DUCKDB_THREADS
        
        import os
        # Use physical core count (or half of logical if physical not available)
        return os.cpu_count() or 4

    @property
    def db_read_only(self) -> bool:
        return os.environ.get("DB_READ_ONLY", "false").lower() == "true"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
