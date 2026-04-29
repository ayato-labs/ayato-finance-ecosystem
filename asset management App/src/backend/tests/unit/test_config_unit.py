from __future__ import annotations

import os
from unittest import mock

import pytest
from pydantic import ValidationError

from core.config import Settings


def test_settings_defaults():
    """
    デフォルト値が正しく設定されているか確認する。
    """
    # 環境変数をクリアした状態でインスタンス化
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.backend_port == 5007
        assert settings.db_path == "assets.duckdb"
        assert settings.price_api_url == "http://127.0.0.1:5005"
        assert settings.log_level == "INFO"


def test_settings_env_override():
    """
    環境変数が正しく優先されるか確認する。
    """
    env_vars = {
        "BACKEND_PORT": "9999",
        "PRICE_API_URL": "https://api.example.com",
        "LOG_LEVEL": "DEBUG",
    }
    with mock.patch.dict(os.environ, env_vars):
        settings = Settings(_env_file=None)
        assert settings.backend_port == 9999
        assert settings.price_api_url == "https://api.example.com"
        assert settings.log_level == "DEBUG"


def test_settings_invalid_type():
    """
    不正な型の環境変数が与えられた場合にエラーになるか確認する。
    """
    with mock.patch.dict(os.environ, {"BACKEND_PORT": "not-a-number"}), pytest.raises(
        ValidationError
    ):
        Settings(_env_file=None)


def test_settings_extra_fields_ignored():
    """
    定義されていない環境変数が無視されるか確認する。
    """
    with mock.patch.dict(os.environ, {"UNKNOWN_SETTING": "value"}):
        settings = Settings(_env_file=None)
        assert not hasattr(settings, "unknown_setting")
