"""Unit tests for logging configuration."""



from src.logging_config import setup_logger


class TestLoggingConfig:
    """logging_config モジュールのユニットテスト。"""

    def test_setup_logger_returns_logger(self):
        """ロガーインスタンス返却のテスト。"""
        from loguru import logger

        # ロガーが返されることを確認（ファイル出力なし）
        result = setup_logger(log_dir="nonexistent", app_name="test")
        assert result is logger

    def test_setup_logger_default_params(self):
        """デフォルトパラメータでのセットアップテスト。"""
        from loguru import logger

        result = setup_logger()
        assert result is logger

    def test_setup_logger_custom_app_name(self):
        """カスタムアプリケーション名でのセットアップテスト。"""
        from loguru import logger

        result = setup_logger(app_name="my_custom_app")
        assert result is logger

    def test_setup_logger_function_exists(self):
        """setup_logger関数が存在することの確認。"""
        assert callable(setup_logger)
