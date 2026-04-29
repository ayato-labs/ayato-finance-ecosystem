from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    アプリケーション全体の設定を管理するクラス。
    環境変数（.env）から読み込み、デフォルト値を保持する。
    """
    # API URLs
    price_api_url: str = "http://127.0.0.1:5005"
    financials_api_url: str = "http://127.0.0.1:5006"
    index_api_url: str = "http://127.0.0.1:5009"
    macro_api_url: str = "http://127.0.0.1:5010"
    forex_api_url: str = "http://127.0.0.1:5011"
    crypto_api_url: str = "http://127.0.0.1:5012"

    # Backend Server
    backend_host: str = "127.0.0.1"
    backend_port: int = 5007

    # Database
    db_path: str = "assets.duckdb"

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# シングルトンとしてインスタンスを生成
settings = Settings()
