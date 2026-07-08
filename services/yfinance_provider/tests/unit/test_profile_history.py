import json
import os
from unittest.mock import MagicMock

import pytest
from src.collector.engine import SyncEngine


@pytest.fixture
def sync_engine():
    db_manager = MagicMock()
    return SyncEngine(db_manager=db_manager)


def test_calculate_profile_hash(sync_engine):
    info1 = {
        "longName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "longBusinessSummary": "Summary 1",
    }
    info2 = {
        "longName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "longBusinessSummary": "Summary 1",
    }
    info3 = {
        "longName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "longBusinessSummary": "Summary 2",  # 変更あり
    }

    hash1 = sync_engine._calculate_profile_hash(info1)
    hash2 = sync_engine._calculate_profile_hash(info2)
    hash3 = sync_engine._calculate_profile_hash(info3)

    assert hash1 == hash2
    assert hash1 != hash3


def test_update_profile_history_new_file(sync_engine, tmp_path):
    profile_path = os.path.join(tmp_path, "AAPL.json")
    info = {"longName": "Apple Inc.", "sector": "Technology"}
    current_hash = "hash1"

    # 新規作成
    updated = sync_engine._update_profile_history(profile_path, info, current_hash)
    assert updated is True

    # 内容の確認
    with open(profile_path, encoding="utf-8") as f:
        history = json.load(f)
        assert len(history) == 1
        assert history[0]["hash"] == "hash1"
        assert history[0]["longName"] == "Apple Inc."


def test_update_profile_history_no_change(sync_engine, tmp_path):
    profile_path = os.path.join(tmp_path, "AAPL.json")
    info = {"longName": "Apple Inc.", "sector": "Technology"}
    current_hash = "hash1"

    # 1回目の書き込み
    sync_engine._update_profile_history(profile_path, info, current_hash)

    # 2回目の書き込み（変更なし）
    updated = sync_engine._update_profile_history(profile_path, info, current_hash)
    assert updated is False

    # 履歴は増えていないはず
    with open(profile_path, encoding="utf-8") as f:
        history = json.load(f)
        assert len(history) == 1


def test_update_profile_history_with_change(sync_engine, tmp_path):
    profile_path = os.path.join(tmp_path, "AAPL.json")
    info1 = {"longName": "Apple Inc.", "sector": "Technology"}
    info2 = {"longName": "Apple Inc.", "sector": "Technology", "industry": "New Industry"}

    # 1回目の書き込み
    sync_engine._update_profile_history(profile_path, info1, "hash1")

    # 2回目の書き込み（変更あり）
    updated = sync_engine._update_profile_history(profile_path, info2, "hash2")
    assert updated is True

    # 履歴が増えているはず
    with open(profile_path, encoding="utf-8") as f:
        history = json.load(f)
        assert len(history) == 2
        assert history[0]["hash"] == "hash1"
        assert history[1]["hash"] == "hash2"
        assert history[1]["industry"] == "New Industry"
