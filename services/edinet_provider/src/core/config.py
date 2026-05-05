from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # EDINET API Requirements
    EDINET_API_KEY: str = ""
    
    # Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    DB_PATH: Path = DATA_DIR / "edinet.duckdb"

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
